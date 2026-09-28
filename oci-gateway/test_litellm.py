"""Real LiteLLM 1.101.0 adapters; only OCI HTTP transport/signing are mocked."""
import asyncio
import json
import os
import socket
import unittest
from unittest.mock import patch

os.environ.update(OCI_GATEWAY_KEY="a" * 64, OCI_REGION="eu-frankfurt-1",
                  OCI_COMPARTMENT_ID="offline-test", LITELLM_LOCAL_MODEL_COST_MAP="True",
                  DO_NOT_TRACK="1")
import httpx
import app
import runtime_checks as checks
from prepare import MODELS


class FakeSDKSigner:
    def __call__(self, request, enforce_content_headers=False):
        request.headers["authorization"] = "offline-signature"
        return request

    def refresh_security_token(self):
        pass


def fixture(model, stream):
    cohere = model.startswith("cohere.")
    headers = {"content-type": "application/json"}
    if stream:
        headers["content-type"] = "text/event-stream"
        if cohere:
            parts = [{"apiFormat": "COHERE", "text": "OK-742"},
                     {"apiFormat": "COHERE", "text": "OK-742", "chatHistory": [], "finishReason": "COMPLETE"}]
        else:
            parts = [{"index": 0, "message": {"role": "ASSISTANT", "content": [{"type": "TEXT", "text": "OK-742"}]}},
                     {"index": 0, "finishReason": "stop"}]
        text = "".join("data: " + json.dumps(p) + "\n\n" for p in parts)
    else:
        if cohere:
            result = {"apiFormat": "COHERE", "text": "OK-742", "finishReason": "COMPLETE"}
        else:
            result = {"apiFormat": "GENERIC", "timeCreated": "2026-09-21T12:00:00Z",
                      "choices": [{"index": 0, "message": {"role": "ASSISTANT",
                                   "content": [{"type": "TEXT", "text": "OK-742"}]}, "finishReason": "stop"}],
                      "usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15}}
        text = json.dumps({"modelId": model, "modelVersion": "1.0", "chatResponse": result})
    return httpx.Response(200, text=text, headers=headers,
                          request=httpx.Request("POST", "https://example.invalid/"))


class RealAdapterTests(unittest.TestCase):
    def setUp(self):
        app.signer = app.RefreshingOCISigner(FakeSDKSigner())
        # A missed mock must fail locally instead of reaching any real service.
        self.network = patch.object(socket.socket, "connect", side_effect=AssertionError("Network prohibited"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def exercise(self, model, stream):
        with patch("litellm.llms.custom_httpx.http_handler.HTTPHandler.post",
                   return_value=fixture(model, stream)) as transport:
            result = app.chat_call({"model": model, "messages": checks.PROMPT, "stream": stream})
            if stream:
                raw = asyncio.run(checks.collect_stream(result))
                checks.validate_sse(raw)
            else:
                checks.validate_json(result)
            transport.assert_called_once()
            kw = transport.call_args.kwargs
            data = kw.get("data", kw.get("json"))
            if isinstance(data, (str, bytes)):
                data = json.loads(data)
            self.assertEqual(data["servingMode"], {"servingType": "ON_DEMAND", "modelId": model})
            self.assertEqual(data["compartmentId"], "offline-test")
            request = data["chatRequest"]
            self.assertEqual(request["apiFormat"], "COHERE" if model.startswith("cohere.") else "GENERIC")
            self.assertIn("OK-742", json.dumps(request))
            url = kw.get("url") or transport.call_args.args[0]
            self.assertIn("inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com", url)
            self.assertEqual(app.slots._value, 4)

    def test_gpt_chat(self): self.exercise(MODELS[0], False)
    def test_gpt_stream(self): self.exercise(MODELS[0], True)
    def test_cohere_chat(self): self.exercise(MODELS[1], False)
    def test_cohere_stream(self): self.exercise(MODELS[1], True)
    def test_flash_chat(self): self.exercise(MODELS[2], False)
    def test_flash_stream(self): self.exercise(MODELS[2], True)
    def test_pro_chat(self): self.exercise(MODELS[3], False)
    def test_pro_stream(self): self.exercise(MODELS[3], True)
    def test_llama_chat(self): self.exercise(MODELS[4], False)
    def test_llama_stream(self): self.exercise(MODELS[4], True)

    def stream_fixture(self, raw, model=MODELS[4]):
        reply = httpx.Response(200, text=raw, headers={"content-type": "text/event-stream"},
                               request=httpx.Request("POST", "https://example.invalid/"))
        with patch("litellm.llms.custom_httpx.http_handler.HTTPHandler.post", return_value=reply):
            result = app.chat_call({"model": model, "messages": checks.PROMPT, "stream": True})
            output = asyncio.run(checks.collect_stream(result))
        self.assertEqual(app.slots._value, 4)
        return output

    def test_done_sentinel_all_five_models(self):
        for model in MODELS:
            with self.subTest(model=model):
                checks.validate_sse(self.stream_fixture(fixture(model, True).text + "data: [DONE]\n\n", model))

    def test_original_parser_reproduces_confirmed_failure(self):
        from litellm.llms.oci.chat.transformation import OCIStreamWrapper
        original = OCIStreamWrapper.chunk_creator.__wrapped__
        with patch.object(OCIStreamWrapper, "chunk_creator", original):
            raw = self.stream_fixture(fixture(MODELS[4], True).text + "data: [DONE]\n\n")
        self.assertIn("OCI stream failed", raw)
        with self.assertRaisesRegex(ValueError, "StreamError"):
            checks.validate_sse(raw)

    def test_done_before_finish_is_not_success(self):
        raw = self.stream_fixture('data: {"index":0,"message":{"role":"ASSISTANT","content":[{"type":"TEXT","text":"OK-742"}]}}\n\ndata: [DONE]\n\n')
        with self.assertRaisesRegex(ValueError, "StreamError"): checks.validate_sse(raw)

    def test_invalid_json_after_finish_not_hidden(self):
        raw = self.stream_fixture(fixture(MODELS[4], True).text + "data: invalid\n\n")
        with self.assertRaisesRegex(ValueError, "StreamError"): checks.validate_sse(raw)

    def test_invalid_json_after_done_not_hidden(self):
        raw = self.stream_fixture(fixture(MODELS[4], True).text + "data: [DONE]\n\ndata: invalid\n\n")
        with self.assertRaisesRegex(ValueError, "StreamError"): checks.validate_sse(raw)

    def test_near_match_done_not_suppressed(self):
        raw = self.stream_fixture(fixture(MODELS[4], True).text + "data: [DONE] unexpected\n\n")
        with self.assertRaisesRegex(ValueError, "StreamError"): checks.validate_sse(raw)

    def test_done_with_surrounding_whitespace(self):
        raw = self.stream_fixture(fixture(MODELS[4], True).text + "data:  [DONE] \r\n\r\n")
        checks.validate_sse(raw)

    def test_length_finish_is_not_success(self):
        raw = self.stream_fixture(fixture(MODELS[4], True).text.replace('"stop"', '"MAX_TOKENS"') + "data: [DONE]\n\n")
        with self.assertRaisesRegex(ValueError, "IncompleteAnswer"): checks.validate_sse(raw)

    def test_compat_install_is_idempotent(self):
        from litellm.llms.oci.chat.transformation import OCIStreamWrapper
        installed = OCIStreamWrapper.chunk_creator
        app.install_oci_done_compat()
        app.install_oci_done_compat()
        self.assertIs(installed, OCIStreamWrapper.chunk_creator)


if __name__ == "__main__":
    unittest.main()
