"""Offline gateway tests. Real provider network calls are prohibited."""
import ast
import asyncio
import copy
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch

os.environ.update(OCI_GATEWAY_KEY="a" * 64, OCI_REGION="eu-frankfurt-1",
                  OCI_COMPARTMENT_ID="offline-test", LITELLM_LOCAL_MODEL_COST_MAP="True",
                  DO_NOT_TRACK="1")
import app
from fastapi.testclient import TestClient
from fastapi import HTTPException
import prepare
import runtime_checks as checks


def response():
    return Mock(model_dump=Mock(return_value={"choices": [{"message": {"content": "OK-742"},
                                                         "finish_reason": "stop"}]}))


class GatewayTests(unittest.TestCase):
    def setUp(self):
        app.slots = threading.BoundedSemaphore(4)
        self.sdk = Mock()
        app.signer = app.RefreshingOCISigner(self.sdk)

    def body(self, model=prepare.MODELS[0], **extra):
        return dict(model=model, messages=checks.PROMPT, **extra)

    def test_allowlist_and_forwarding(self):
        for model in prepare.MODELS:
            with self.subTest(model=model), patch.object(app.litellm, "completion", return_value=response()) as call:
                checks.validate_json(app.chat_call(self.body(model)))
                kwargs = call.call_args.kwargs
                self.assertEqual(kwargs["model"], "oci/" + model)
                self.assertEqual(kwargs["oci_region"], "eu-frankfurt-1")
                self.assertEqual(kwargs["oci_compartment_id"], "offline-test")
                self.assertIs(kwargs["oci_signer"], app.signer)

    def test_model_policy_caps_and_timeouts(self):
        for model in prepare.MODELS:
            policy = app.CHAT_MODELS[model]
            with self.subTest(model=model), patch.object(app.litellm, "completion", return_value=response()) as call:
                app.chat_call(self.body(model))
                self.assertEqual(call.call_args.kwargs["max_tokens"], policy["default_tokens"])
                self.assertEqual(call.call_args.kwargs["timeout"], policy["timeout"])
                app.chat_call(self.body(model, max_tokens=100000))
                self.assertEqual(call.call_args.kwargs["max_tokens"], policy["max_tokens"])
                app.chat_call(self.body(model, max_completion_tokens=27, max_tokens=99))
                self.assertEqual(call.call_args.kwargs["max_tokens"], 27)

    def test_client_cannot_override_routing(self):
        with patch.object(app.litellm, "completion", return_value=response()) as call:
            app.chat_call(self.body(api_base="https://evil.invalid", api_key="secret",
                oci_region="wrong", oci_compartment_id="wrong", timeout=999, _gateway_timeout=999))
            kw = call.call_args.kwargs
            self.assertNotIn("api_base", kw)
            self.assertNotIn("api_key", kw)
            self.assertEqual(kw["timeout"], 90)
            self.assertEqual(kw["oci_region"], "eu-frankfurt-1")

    def test_rejects_invalid_inputs_before_inference(self):
        cases = [{"model": ["x"]}, {"model": "google.gemini-2.5-pro:v1.0"},
                 {"model": app.EMBED}, {"max_tokens": 0}, {"max_tokens": True},
                 {"max_tokens": -1}, {"max_tokens": "512"}, {"stream": "true"},
                 {"messages": []}, {"messages": [{"role": "tool", "content": "x"}]},
                 {"messages": [{"role": "user", "content": [{"type": "image_url"}]}]},
                 {"tools": [{"type": "function"}]}, {"functions": [{"name": "x"}]},
                 {"temperature": float("nan")}, {"temperature": True}, {"top_p": 2}]
        with patch.object(app.litellm, "completion") as call:
            for extra in cases:
                body = self.body()
                body.update(extra)
                with self.subTest(extra=extra), self.assertRaises(HTTPException) as exc:
                    app.chat_call(body)
                self.assertEqual(exc.exception.status_code, 400)
            call.assert_not_called()

    def test_http_auth_model_list_and_size_limit(self):
        with patch.object(app, "InstancePrincipalsSecurityTokenSigner", return_value=self.sdk):
            with TestClient(app.app) as client:
                self.assertEqual(client.get("/health").status_code, 200)
                self.assertEqual(client.get("/v1/models").status_code, 401)
                headers = {"Authorization": "Bearer " + "a" * 64}
                data = client.get("/v1/models", headers=headers).json()
                self.assertEqual([x["id"] for x in data["data"]], list(prepare.MODELS))
                self.assertEqual(client.post("/v1/chat/completions", headers=headers, content="!").status_code, 400)
                self.assertEqual(client.post("/v1/chat/completions", headers=headers,
                                            content="x" * 1000001).status_code, 413)

    def test_auth_retry_once_and_deepcopy(self):
        error = RuntimeError("secret provider body")
        error.status_code = 401
        method = Mock(side_effect=[error, "ok"])
        self.assertEqual(app.invoke(method), "ok")
        self.sdk.refresh_security_token.assert_called_once()
        self.assertEqual(method.call_count, 2)
        self.assertIs(copy.deepcopy(app.signer), app.signer)
        request = object()
        app.signer.do_request_sign(request, enforce_content_headers=True)
        self.sdk.assert_called_once_with(request, enforce_content_headers=True)

    def test_other_provider_errors_not_retried_and_sanitized(self):
        for status in (400, 429, 500):
            error = RuntimeError("sensitive-test-body")
            error.status_code = status
            with patch.object(app.litellm, "completion", side_effect=error) as call:
                with self.assertRaises(HTTPException) as exc:
                    app.chat_call(self.body())
                self.assertNotIn("sensitive", exc.exception.detail)
                self.assertEqual(exc.exception.status_code, 429 if status == 429 else 502)
                call.assert_called_once()
        self.assertEqual(app.slots._value, 4)

    def test_partial_stream_failure_is_visible_and_releases_slot(self):
        def broken():
            yield Mock(model_dump=Mock(return_value={"choices": [{"delta": {"content": "OK-742"}}]}))
            raise TypeError("sensitive-test-body")
        with patch.object(app.litellm, "completion", return_value=broken()):
            stream = app.chat_call(self.body(stream=True))
            raw = asyncio.run(checks.collect_stream(stream))
        self.assertIn("OCI stream failed", raw)
        self.assertNotIn("sensitive", raw)
        with self.assertRaises(ValueError):
            checks.validate_sse(raw)
        self.assertEqual(app.slots._value, 4)

    def test_busy_and_release_idempotent(self):
        releases = [app.acquire_slot() for _ in range(4)]
        with self.assertRaises(HTTPException) as exc:
            app.acquire_slot()
        self.assertEqual(exc.exception.status_code, 429)
        for release in releases:
            release()
            release()
        self.assertEqual(app.slots._value, 4)

    def test_embedding_is_unchanged_and_preserves_types(self):
        trees = [ast.parse(Path(__file__).with_name(n).read_text()) for n in ("baseline.py", "app.py")]
        definitions = [{n.name: ast.dump(n) for n in t.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                       for t in trees]
        for name in ("embedding_call", "embeddings", "authenticate", "acquire_slot"):
            self.assertEqual(definitions[0][name], definitions[1][name])
        for kind in ("search_document", "search_query"):
            payload = {"data": [{"embedding": [0.0] * 1536}]}
            with patch.object(app.litellm, "embedding", return_value=Mock(model_dump=Mock(return_value=payload))) as call:
                checks.validate_embedding(app.embedding_call({"model": app.EMBED, "input": "test", "input_type": kind}))
                self.assertEqual(call.call_args.kwargs["input_type"], kind)
                self.assertEqual(call.call_args.kwargs["model"], "oci/" + app.EMBED)

    def test_patch_is_exact_and_rejects_unknown_baseline(self):
        self.assertEqual(prepare.packaged_app(), Path(__file__).with_name("app.py").read_bytes())
        with self.assertRaises(ValueError):
            prepare.candidate(b"# another app\n")


class ValidatorTests(unittest.TestCase):
    GOOD = 'data: {"choices":[{"delta":{"content":"OK-742"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'

    def test_complete_stream(self):
        checks.validate_sse(self.GOOD)

    def test_invalid_streams(self):
        invalid = [self.GOOD.replace("[DONE]", "{}"), self.GOOD.replace("stop", "length"),
                   self.GOOD.replace("OK-742", ""), self.GOOD.replace('"stop"', 'null'),
                   self.GOOD.replace("data: [DONE]", 'data: {"error":{"message":"failure"}}\n\ndata: [DONE]')]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                checks.validate_sse(raw)

    def test_later_stop_cannot_hide_length(self):
        first = 'data: {"choices":[{"delta":{"content":"OK-742"},"finish_reason":"length"}]}\n\n'
        with self.assertRaisesRegex(ValueError, "IncompleteAnswer"):
            checks.validate_sse(first + self.GOOD)


if __name__ == "__main__":
    unittest.main()
