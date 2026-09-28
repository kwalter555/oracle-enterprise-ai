"""All five real pinned OCI adapters, synthetic HTTP responses only."""
import asyncio
import ast
import copy
import json
from pathlib import Path
import socket
import threading
import unittest
from unittest.mock import patch

import httpx
import app
import runtime_checks as checks
from fastapi import HTTPException
from prepare import MODELS
from test_native import call, reply, body
from test_litellm import fixture, FakeSDKSigner


def provider_reply(model, calls=None, reason="COMPLETE", text=""):
    if model.startswith("cohere."):
        payload = fixture(model, False).json()
        result = payload["chatResponse"]
        result.update(text=text, finishReason=reason)
        if calls:
            result["toolCalls"] = [{"name": c["function"]["name"],
                                    "parameters": json.loads(c["function"]["arguments"])} for c in calls]
    else:
        payload = reply(calls=calls, reason=reason, text=text).json()
        payload["modelId"] = model
    return httpx.Response(200, json=payload, request=httpx.Request("POST", "https://example.invalid"))


class AllModelTests(unittest.TestCase):
    def setUp(self):
        app.slots = threading.BoundedSemaphore(4)
        app.signer = app.RefreshingOCISigner(FakeSDKSigner())
        network = patch.object(socket.socket, "connect", side_effect=AssertionError("Network prohibited"))
        network.start()
        self.addCleanup(network.stop)

    def request(self, model, messages, *, stream=False, selection="auto", calls=None, text="", reason="COMPLETE"):
        request = {"model": model, "messages": messages, "stream": stream, "max_tokens": 4000,
                   "tools": copy.deepcopy(checks.NATIVE_TOOLS), "tool_choice": selection}
        with patch("litellm.llms.custom_httpx.http_handler.HTTPHandler.post",
                   return_value=provider_reply(model, calls, reason, text)) as transport:
            result = app.chat_call(request)
            if stream:
                result = checks.native_payload(asyncio.run(checks.collect_stream(result)), True)
            transport.assert_called_once()
            data = transport.call_args.kwargs["data"]
            data = json.loads(data) if isinstance(data, (str, bytes)) else data
            url = transport.call_args.kwargs.get("url") or transport.call_args.args[0]
            self.assertIn("inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com", url)
        self.assertEqual(data["servingMode"], {"servingType": "ON_DEMAND", "modelId": model})
        self.assertEqual(data["compartmentId"], "offline-test")
        self.assertFalse(data["chatRequest"]["isStream"])
        self.assertEqual(app.slots._value, 4)
        self.assertFalse(app._native_context.get())
        return result, data["chatRequest"]

    def test_all_five_roundtrip_arguments_results_and_two_transport_modes(self):
        for model in MODELS:
            for stream in (False, True):
                with self.subTest(model=model, stream=stream):
                    messages = [{"role": "system", "content": "Use the tool result."},
                                {"role": "user", "content": "Find ORION-742."}]
                    result, sent = self.request(model, messages, stream=stream, calls=[call()])
                    assistant = checks.validate_native_call(result)
                    if model.startswith("cohere."):
                        self.assertEqual(sent["apiFormat"], "COHERE")
                        self.assertNotIn("toolChoice", sent)
                        param = sent["tools"][0]["parameterDefinitions"]["probe_code"]
                        self.assertEqual(param["type"], "str")
                        self.assertTrue(param["isRequired"])
                    else:
                        self.assertEqual(sent["toolChoice"], {"type": "AUTO"})
                        self.assertEqual(sent["tools"][0]["parameters"]["required"], ["probe_code"])
                    messages += [assistant, {"role": "tool", "tool_call_id": assistant["tool_calls"][0]["id"],
                                             "content": '{"marker":"SECRET-SYNTHETIC-42"}'}]
                    result, sent = self.request(model, messages, stream=stream, selection="none", text="SECRET-SYNTHETIC-42")
                    self.assertEqual(result["choices"][0]["message"]["content"], "SECRET-SYNTHETIC-42")
                    if model.startswith("cohere."):
                        self.assertNotIn("toolChoice", sent)
                        self.assertTrue(sent["tools"])
                        self.assertTrue(sent["isForceSingleStep"])
                        self.assertEqual(sent["message"], "")
                        self.assertEqual([m["role"] for m in sent["chatHistory"]], ["USER", "CHATBOT"])
                        tool_result = sent["toolResults"][0]
                        self.assertEqual(tool_result["call"]["name"], checks.NATIVE_TOOL)
                        self.assertEqual(tool_result["call"]["parameters"], {"probe_code": "ORION-742"})
                        self.assertIn("SECRET-SYNTHETIC-42", tool_result["outputs"][0]["output"])
                    else:
                        self.assertEqual(sent["toolChoice"], {"type": "NONE"})
                        self.assertEqual(sent["messages"][-1]["toolCallId"], assistant["tool_calls"][0]["id"])

    def test_cohere_repeated_same_call_has_new_id_and_valid_history(self):
        model = MODELS[1]
        messages = [{"role": "user", "content": "Find ORION-742"}]
        first, _ = self.request(model, messages, calls=[call()])
        assistant = checks.validate_native_call(first)
        messages += [assistant, {"role": "tool", "tool_call_id": assistant["tool_calls"][0]["id"], "content": "test"},
                     {"role": "assistant", "content": "Done"}, {"role": "user", "content": "Check again"}]
        second, _ = self.request(model, messages, calls=[call()])
        second_assistant = checks.validate_native_call(second)
        self.assertNotEqual(assistant["tool_calls"][0]["id"], second_assistant["tool_calls"][0]["id"])
        messages += [second_assistant, {"role": "tool", "tool_call_id": second_assistant["tool_calls"][0]["id"], "content": "test2"}]
        self.request(model, messages, selection="none", text="test2")

    def test_parameterless_health_style_tools_on_all_models(self):
        tools = copy.deepcopy(checks.NATIVE_TOOLS)
        tools[0]["function"]["parameters"] = {"type": "object", "properties": {}}
        with patch.object(checks, "NATIVE_TOOLS", tools):
            for model in MODELS:
                result, sent = self.request(model, [{"role": "user", "content": "Check health"}], calls=[call(arguments="{}")])
                self.assertEqual(json.loads(result["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]), {})
                if model.startswith("cohere."):
                    self.assertEqual(sent["tools"][0]["parameterDefinitions"], {})

    def test_cohere_parallel_tool_results_keep_name_and_parameters(self):
        model = MODELS[1]
        messages = [{"role": "user", "content": "Find two projects"}]
        result, _ = self.request(model, messages, stream=True, calls=[call(), call(arguments='{"probe_code":"ATLAS-315"}')])
        assistant = result["choices"][0]["message"]
        messages += [assistant] + [{"role": "tool", "tool_call_id": c["id"], "content": "result"+str(i)}
                                   for i, c in enumerate(assistant["tool_calls"])]
        _, sent = self.request(model, messages, selection="none", text="Both done")
        results = sent["toolResults"]
        self.assertEqual(len(results), 2)
        self.assertEqual([r["call"]["parameters"]["probe_code"] for r in results], ["ORION-742", "ATLAS-315"])

    def test_cohere_continuation_auto_and_none_preserve_mixed_text_and_latest_user(self):
        for selection in ("auto", "none"):
            for stream in (False, True):
                messages = [{"role": "system", "content": "Use the result"},
                            {"role": "user", "content": "Earlier question"},
                            {"role": "assistant", "content": "Earlier answer"},
                            {"role": "user", "content": "Find ORION-742"},
                            {"role": "assistant", "content": "Checking now", "tool_calls": [call()]},
                            {"role": "tool", "tool_call_id": "call_test", "content": "result42"}]
                _, sent = self.request(MODELS[1], messages, selection=selection, stream=stream, text="result42")
                self.assertEqual(sent["message"], "")
                self.assertEqual([m["message"] for m in sent["chatHistory"]],
                                 ["Earlier question", "Earlier answer", "Find ORION-742", "Checking now"])
                self.assertEqual(sent["preambleOverride"], "Use the result")
                self.assertEqual(sent["isForceSingleStep"], selection == "none")
                self.assertTrue(sent["tools"])
                self.assertEqual(sent["toolResults"][0]["outputs"], [{"output": "result42"}])
                self.assertIsNone(app._cohere_choice.get())

    def test_cohere_multiple_tool_cycles_only_latest_results_at_top_level(self):
        messages = [{"role": "user", "content": "First question"},
                    {"role": "assistant", "content": "Plan", "tool_calls": [call("one")]},
                    {"role": "tool", "tool_call_id": "one", "content": "old result"},
                    {"role": "assistant", "content": "Next step", "tool_calls": [call("two")]},
                    {"role": "tool", "tool_call_id": "two", "content": "latest result"}]
        _, sent = self.request(MODELS[1], messages, selection="none", text="Done")
        self.assertEqual([m["role"] for m in sent["chatHistory"]], ["USER", "CHATBOT", "TOOL", "CHATBOT"])
        self.assertEqual(sent["chatHistory"][2]["toolResults"][0]["outputs"], [{"output": "old result"}])
        self.assertEqual(sent["toolResults"][0]["outputs"], [{"output": "latest result"}])

    def test_cohere_none_without_history_omits_tools(self):
        _, sent = self.request(MODELS[1], [{"role": "user", "content": "Hi"}], selection="none", text="Hi")
        self.assertNotIn("tools", sent)
        self.assertNotIn("toolResults", sent)
        self.assertNotIn("isForceSingleStep", sent)

    def test_cohere_history_without_definitions_rejected_before_provider(self):
        request = {"model": MODELS[1], "messages": [{"role": "user", "content": "Test"},
            {"role": "assistant", "content": None, "tool_calls": [call()]},
            {"role": "tool", "tool_call_id": "call_test", "content": "result"}]}
        with patch.object(app.litellm, "completion") as provider, self.assertRaises(HTTPException) as exc:
            app.chat_call(request)
        self.assertEqual(exc.exception.status_code, 400)
        provider.assert_not_called()

    def test_cohere_none_continuation_blocks_unwanted_next_call(self):
        messages = [{"role": "user", "content": "Test"},
                    {"role": "assistant", "content": None, "tool_calls": [call()]},
                    {"role": "tool", "tool_call_id": "call_test", "content": "result"}]
        with self.assertRaises(HTTPException) as exc:
            self.request(MODELS[1], messages, selection="none", calls=[call()])
        self.assertEqual(exc.exception.status_code, 502)
        self.assertIsNone(app._cohere_choice.get())

    def test_raw_failure_or_truncation_blocked_for_every_model(self):
        for model in MODELS:
            for reason in ("ERROR", "MAX_TOKENS", "length", None):
                with self.subTest(model=model, reason=reason), self.assertRaises(HTTPException) as exc:
                    self.request(model, [{"role": "user", "content": "Test"}], calls=[call()], reason=reason)
                self.assertEqual(exc.exception.status_code, 502)

    def test_cohere_forced_choice_rejected_not_silently_ignored(self):
        for selection in ("required", {"type": "function", "function": {"name": checks.NATIVE_TOOL}}):
            with patch.object(app.litellm, "completion") as transport:
                with self.assertRaises(HTTPException) as exc:
                    request = body(tool_choice=selection)
                    request["model"] = MODELS[1]
                    app.chat_call(request)
                self.assertEqual(exc.exception.status_code, 400)
                transport.assert_not_called()

    def test_unexpected_tool_cannot_be_executed_on_any_model(self):
        for model in MODELS:
            for selection in ("auto", "none"):
                with self.subTest(model=model, selection=selection), self.assertRaises(HTTPException) as exc:
                    self.request(model, [{"role": "user", "content": "Test"}], selection=selection,
                                 calls=[call(name="UNAPPROVED_TOOL")])
                self.assertEqual(exc.exception.status_code, 502)

    def test_non_native_gateway_code_is_unchanged(self):
        definitions = []
        for filename in ("baseline.py", "app.py"):
            tree = ast.parse(Path(__file__).with_name(filename).read_text())
            definitions.append({node.name: ast.dump(node) for node in tree.body
                                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))})
        for name in ("chat_call", "chat", "models", "health", "read_body", "invoke",
                     "RefreshingOCISigner", "lifespan", "install_oci_done_compat",
                     "embedding_call", "embeddings", "authenticate", "acquire_slot"):
            self.assertEqual(definitions[0][name], definitions[1][name], name)

    def citation_request(self, citations, stream=False, reason="COMPLETE", calls=None):
        response = provider_reply(MODELS[1], calls=calls, reason=reason, text="MARKER-42")
        payload = response.json()
        payload["chatResponse"]["citations"] = citations
        response = httpx.Response(200, json=payload, request=response.request)
        request = {"model": MODELS[1], "stream": stream, "max_tokens": 4000,
                   "tools": copy.deepcopy(checks.NATIVE_TOOLS), "tool_choice": "none",
                   "messages": [{"role": "user", "content": "Read marker"},
                       {"role": "assistant", "content": "Checking", "tool_calls": [call()]},
                       {"role": "tool", "tool_call_id": "call_test", "content": "MARKER-42"}]}
        with patch("litellm.llms.custom_httpx.http_handler.HTTPHandler.post", return_value=response) as post:
            result = app.chat_call(request)
            if stream:
                result = checks.native_payload(asyncio.run(checks.collect_stream(result)), True)
            post.assert_called_once()
        return result

    def test_cohere_oci_citation_alias_json_and_sse(self):
        from oci.generative_ai_inference.models import Citation
        self.assertEqual(Citation().attribute_map["document_ids"], "documentIds")
        for stream in (False, True):
            for alias in ("documentIds", "document_ids"):
                with self.subTest(stream=stream, alias=alias):
                    result = self.citation_request([
                        {"start": 0, "end": 9, "text": "MARKER-42", alias: ["doc-1"]}], stream)
                    self.assertEqual(result["choices"][0]["message"]["content"], "MARKER-42")
                    self.assertEqual(result["choices"][0]["finish_reason"], "stop")

    def test_cohere_citation_normalization_preserves_raw_and_other_fields(self):
        raw = {"chatResponse": {"text": "unchanged", "usage": {"promptTokens": 12},
               "citations": [{"start": 0, "end": 1, "text": "u", "documentIds": ["d"]},
                             {"start": 1, "end": 2, "text": "n", "document_ids": ["e"]}]}}
        before = copy.deepcopy(raw)
        result = app.native_cohere_citations(raw)
        self.assertEqual(raw, before)
        self.assertEqual(result["chatResponse"]["citations"][0]["document_ids"], ["d"])
        self.assertEqual(result["chatResponse"]["citations"][1], raw["chatResponse"]["citations"][1])
        self.assertEqual(result["chatResponse"]["usage"], raw["chatResponse"]["usage"])
        self.assertEqual(result["chatResponse"]["text"], "unchanged")

    def test_cohere_invalid_citations_still_rejected(self):
        base = {"start": 0, "end": 1, "text": "x"}
        cases = [[base], [dict(base, documentIds=None)], [dict(base, documentIds="d")],
                 [dict(base, documentIds=[1])], [dict(base, documentIds=["d"], document_ids=["other"])],
                 [{"start": 0, "end": 1, "documentIds": ["d"]}], ["not a citation"]]
        for citations in cases:
            with self.subTest(citations=citations), self.assertRaises(HTTPException) as exc:
                self.citation_request(citations, stream=True)
            self.assertEqual(exc.exception.status_code, 502)
            self.assertEqual(app.slots._value, 4)

    def test_cohere_valid_alias_does_not_bypass_finish_or_tool_guards(self):
        citations = [{"start": 0, "end": 1, "text": "x", "documentIds": ["d"]}]
        for reason, calls in (("MAX_TOKENS", None), ("ERROR", None), ("COMPLETE", [call()])):
            with self.subTest(reason=reason, calls=calls), self.assertRaises(HTTPException) as exc:
                self.citation_request(citations, stream=True, reason=reason, calls=calls)
            self.assertEqual(exc.exception.status_code, 502)

    def test_cohere_citation_empty_and_matching_aliases(self):
        for citations in (None, [], [{"start": 0, "end": 1, "text": "x", "documentIds": ["d"], "document_ids": ["d"]}]):
            self.assertEqual(self.citation_request(citations)["choices"][0]["finish_reason"], "stop")

    def test_sql_demo_static_safety_not_oracle_compilation(self):
        folder = Path(__file__).with_name("adb-readonly-demo")
        function_sql = (folder / "01-create-function.sql").read_text()
        executable = "\n".join(line for line in function_sql.splitlines() if not line.lstrip().startswith("--")).upper()
        for forbidden in ("CREATE OR REPLACE", "EXECUTE IMMEDIATE", "DBMS_SQL", "INSERT INTO",
                          "DELETE FROM", "UPDATE ", "GRANT ", "COMMIT", "UTL_HTTP"):
            self.assertNotIn(forbidden, executable)
        self.assertIn("AUTHID CURRENT_USER", executable)
        self.assertIn("WHERE PROJECT_CODE = L_CODE", executable)
        self.assertIn("SYNTHETIC_DEMO", executable)
        registration = (folder / "02-register-tool.sql").read_text()
        self.assertNotIn('"tool_type":"SQL"', registration)
        self.assertIn('"function":"WEBUI_PROJECT_LOOKUP"', registration)


if __name__ == "__main__":
    unittest.main()
