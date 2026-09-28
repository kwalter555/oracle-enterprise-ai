"""Native validation + REAL pinned OCI adapter, with transport mocked offline."""
import asyncio
import copy
import json
import socket
import threading
import unittest
from unittest.mock import patch

from test_litellm import FakeSDKSigner, fixture
import app
from fastapi import HTTPException
import runtime_checks as checks
from prepare import MODELS


def body(**extra):
    return dict(model=MODELS[0], messages=[{"role": "user", "content": "Test tool"}],
                tools=copy.deepcopy(checks.NATIVE_TOOLS), **extra)


def call(call_id="call_test", name=checks.NATIVE_TOOL, arguments='{"probe_code":"ORION-742"}'):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def reply(calls=None, reason="TOOL_CALLS", text=None):
    response = fixture(MODELS[0], False)
    payload = response.json()
    message = {"role": "ASSISTANT", "content": [] if text is None else [{"type": "TEXT", "text": text}]}
    if calls is not None:
        message["toolCalls"] = [{"type": "FUNCTION", "id": c["id"],
                                  "name": c["function"]["name"], "arguments": c["function"]["arguments"]}
                                 for c in calls]
    payload["chatResponse"]["choices"][0].update(message=message, finishReason=reason)
    import httpx
    return httpx.Response(200, json=payload, request=response.request)


class NativeTests(unittest.TestCase):
    def setUp(self):
        app.slots = threading.BoundedSemaphore(4)
        app.signer = app.RefreshingOCISigner(FakeSDKSigner())
        network = patch.object(socket.socket, "connect", side_effect=AssertionError("Network prohibited"))
        network.start()
        self.addCleanup(network.stop)

    def exercise(self, request, response):
        with patch("litellm.llms.custom_httpx.http_handler.HTTPHandler.post", return_value=response) as transport:
            result = app.chat_call(request)
            if request.get("stream"):
                result = checks.native_payload(asyncio.run(checks.collect_stream(result)), True)
            transport.assert_called_once()
            data = transport.call_args.kwargs["data"]
            data = json.loads(data) if isinstance(data, (str, bytes)) else data
        self.assertEqual(app.slots._value, 4)
        return result, data

    def test_native_roundtrip_chat_and_buffered_stream(self):
        for stream in (False, True):
            with self.subTest(stream=stream):
                request = body(stream=stream, tool_choice={"type": "function", "function": {"name": checks.NATIVE_TOOL}})
                result, sent = self.exercise(request, reply([call()], text="Checking now."))
                assistant = checks.validate_native_call(result)
                chat = sent["chatRequest"]
                self.assertFalse(chat["isStream"])
                self.assertEqual(chat["toolChoice"], {"type": "FUNCTION", "name": checks.NATIVE_TOOL})
                self.assertEqual(chat["tools"][0]["name"], checks.NATIVE_TOOL)
                self.assertEqual(sent["compartmentId"], "offline-test")
                self.assertEqual(assistant["content"], "Checking now.")
                request["messages"] += [assistant, {"role": "tool", "tool_call_id": "call_test", "content": "MARKER-ABC"}]
                request["tool_choice"] = "none"
                result, sent = self.exercise(request, reply(reason="COMPLETE", text="MARKER-ABC"))
                self.assertIn("MARKER-ABC", result["choices"][0]["message"]["content"])
                messages = sent["chatRequest"]["messages"]
                self.assertEqual(messages[-1]["role"], "TOOL")
                self.assertEqual(messages[-1]["toolCallId"], "call_test")
                self.assertEqual(messages[-2]["toolCalls"][0]["id"], "call_test")
                self.assertEqual(messages[-2]["content"][0]["text"], "Checking now.")
                self.assertEqual(sent["chatRequest"]["toolChoice"], {"type": "NONE"})

    def test_history_without_tools_can_produce_final_text(self):
        request = body()
        request.pop("tools")
        request["messages"] += [{"role": "assistant", "content": None, "tool_calls": [call()]},
                                {"role": "tool", "tool_call_id": "call_test", "content": "OK"}]
        result, sent = self.exercise(request, reply(reason="stop", text="OK"))
        self.assertNotIn("tools", sent["chatRequest"])
        self.assertEqual(result["choices"][0]["finish_reason"], "stop")

    def test_parallel_calls_have_unique_indexes_and_preserve_ids(self):
        request = body(stream=True, parallel_tool_calls=True)
        result, sent = self.exercise(request, reply([call("call_a"), call("call_b")]))
        calls = result["choices"][0]["message"]["tool_calls"]
        self.assertEqual([c["id"] for c in calls], ["call_a", "call_b"])
        self.assertNotIn("parallel_tool_calls", sent["chatRequest"])

    def test_finish_reason_variants_and_missing_provider_id(self):
        for reason in ("TOOL_CALL", "TOOL_CALLS", "tool_calls", "COMPLETE", "stop"):
            result, _ = self.exercise(body(), reply([call("")], reason=reason))
            checks.validate_native_call(result)

    def test_provider_failure_never_exposes_executable_partial_calls(self):
        cases = [reply([call()], reason=r) for r in ("MAX_TOKENS", "length", "ERROR", "CANCELLED", None)]
        cases += [reply([call(arguments="{")]), reply([call(name="NOT_ALLOWED")]),
                  reply([call("dup"), call("dup")]), reply(reason="TOOL_CALLS", text="No call")]
        for response in cases:
            with self.subTest(response=response.json()), patch(
                    "litellm.llms.custom_httpx.http_handler.HTTPHandler.post", return_value=response):
                with self.assertRaises(HTTPException) as caught:
                    app.chat_call(body(stream=True))
                self.assertEqual(caught.exception.status_code, 502)
                self.assertEqual(app.slots._value, 4)
                self.assertFalse(app._native_context.get())

    def test_tool_choice_none_and_required_are_enforced(self):
        for selection, response in [("none", reply([call()])), ("required", reply(reason="stop", text="No call"))]:
            with patch("litellm.llms.custom_httpx.http_handler.HTTPHandler.post", return_value=response):
                with self.assertRaises(HTTPException) as caught:
                    app.chat_call(body(tool_choice=selection))
                self.assertEqual(caught.exception.status_code, 502)

    def test_invalid_input_rejected_before_provider_call(self):
        assistant = {"role": "assistant", "content": None, "tool_calls": [call()]}
        cases = [dict(tools={}), dict(tool_choice="unknown"), dict(tool_choice={"type": "function", "function": {"name": "other"}}),
                 dict(tools=[], tool_choice="required"), dict(parallel_tool_calls=False), dict(parallel_tool_calls="true"),
                 dict(functions=[{"name": "old"}]), dict(function_call="auto"),
                 dict(messages=[assistant]), dict(messages=[assistant, {"role": "user", "content": "skip result"}]),
                 dict(messages=[{"role": "tool", "tool_call_id": "orphan", "content": "x"}]),
                 dict(messages=[{"role": "user", "content": "x", "tool_calls": [call()]}]),
                 dict(messages=[{"role": "assistant", "content": None, "tool_calls": [call(arguments="NaN")]}]),
                 dict(messages=[{"role": "assistant", "content": None, "tool_calls": [call(arguments='{"x":NaN}')]}])]
        for mutate in (lambda fn: fn.update(name="bad name"), lambda fn: fn.update(strict=True),
                       lambda fn: fn.update(parameters={"type": "object", "$ref": "https://evil.invalid"}),
                       lambda fn: fn.update(parameters={"type": "array"})):
            tools = copy.deepcopy(checks.NATIVE_TOOLS)
            mutate(tools[0]["function"])
            cases.append(dict(tools=tools))
        cases.append(dict(tools=checks.NATIVE_TOOLS * 2))
        with patch.object(app.litellm, "completion") as provider:
            for extra in cases:
                request = body()
                request.update(extra)
                with self.subTest(extra=extra), self.assertRaises(HTTPException) as caught:
                    app.chat_call(request)
                self.assertEqual(caught.exception.status_code, 400)
            provider.assert_not_called()

    def test_native_tools_blocked_on_unknown_models(self):
        with patch.object(app.litellm, "completion") as provider:
            for model in ("unknown", app.EMBED):
                request = body()
                request["model"] = model
                with self.assertRaises(HTTPException) as caught:
                    app.chat_call(request)
                self.assertEqual(caught.exception.status_code, 400)
            provider.assert_not_called()

    def test_routing_and_extra_message_fields_are_not_forwarded(self):
        request = body(api_base="https://evil.invalid", api_key="DO-NOT-SEND", oci_region="wrong")
        request["messages"][0]["provider_specific_fields"] = {"api_key": "DO-NOT-SEND"}
        result, sent = self.exercise(request, reply([call()]))
        checks.validate_native_call(result)
        self.assertNotIn("DO-NOT-SEND", json.dumps(sent))

    def test_context_is_thread_local_and_resets_after_exception(self):
        token = app._native_context.set(True)
        seen = []
        thread = threading.Thread(target=lambda: seen.append(app._native_context.get()))
        thread.start()
        thread.join()
        app._native_context.reset(token)
        self.assertEqual(seen, [False])
        with patch.object(app.litellm, "completion", side_effect=RuntimeError("private")):
            with self.assertRaises(RuntimeError): app.native_completion()
        self.assertFalse(app._native_context.get())

    def test_install_idempotent(self):
        import litellm.llms.oci.chat.transformation as transformation
        handler = transformation.handle_generic_response
        app.install_native_compat()
        self.assertIs(handler, transformation.handle_generic_response)


if __name__ == "__main__":
    unittest.main()
