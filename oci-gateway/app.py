"""Private OCI adapter: five text chat models and unchanged Cohere embeddings."""
import hmac
import json
import logging
import os
import re
import threading
from contextlib import asynccontextmanager

import litellm
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from oci.auth.signers import InstancePrincipalsSecurityTokenSigner
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

CHAT = "openai.gpt-oss-20b"  # Keep the existing default and compatibility checks.
# Exact allowlist; never infer a provider, URL or endpoint from client input.
# Limits below are demo output limits, not the models' full context windows.
# OCI Command A on-demand permits at most 4,000 output tokens.
# Gemini via OCI Frankfurt is externally processed by Google in the EU.
CHAT_MODELS = {
    CHAT: {"default_tokens": 1024, "max_tokens": 4096, "timeout": 90},
    "cohere.command-a-03-2025": {"default_tokens": 1024, "max_tokens": 4000, "timeout": 90},
    "google.gemini-2.5-flash": {"default_tokens": 4096, "max_tokens": 4096, "timeout": 180},
    "google.gemini-2.5-pro": {"default_tokens": 4096, "max_tokens": 4096, "timeout": 180},
    "meta.llama-3.3-70b-instruct": {"default_tokens": 1024, "max_tokens": 4096, "timeout": 90},
}
EMBED = "cohere.embed-v4.0"
KEY = os.environ.get("OCI_GATEWAY_KEY", "")
if not re.fullmatch(r"[0-9a-f]{64}", KEY):
    raise RuntimeError("OCI_GATEWAY_KEY must be a generated 64-character hex key")
REGION = os.environ["OCI_REGION"]
COMPARTMENT = os.environ["OCI_COMPARTMENT_ID"]
litellm.suppress_debug_info = True
litellm.set_verbose = False
litellm.telemetry = False
# Avoid optional Hugging Face tokenizer downloads when estimating Llama usage.
# Provider-reported usage is authoritative; local estimates use bundled tiktoken.
litellm.disable_hf_tokenizer_download = True
logging.getLogger("LiteLLM").setLevel(logging.CRITICAL)
logging.getLogger("LiteLLM Router").setLevel(logging.CRITICAL)
logger = logging.getLogger("oci-gateway")
slots = threading.BoundedSemaphore(4)
refresh_lock = threading.Lock()
signer = None


def install_oci_done_compat():
    """LiteLLM 1.101.0: recognize OCI's SSE sentinel without parsing it as JSON."""
    from litellm.llms.oci.chat.transformation import OCIStreamWrapper
    original = OCIStreamWrapper.chunk_creator
    if getattr(original, "_oci_done_compat", False):
        return

    def chunk_creator(self, chunk):
        if isinstance(chunk, str) and chunk.startswith("data:") and chunk[5:].strip() == "[DONE]":
            if not getattr(self, "_oci_done_has_finish", False):
                raise ValueError("OCI DONE received before a finish reason")
            # The parent iterator treats None as a skipped SSE control event.
            # Continue consuming: later parser/transport errors must still fail.
            return None
        result = original(self, chunk)
        if result is not None and any(getattr(c, "finish_reason", None) is not None
                                      for c in result.choices):
            self._oci_done_has_finish = True
        return result

    chunk_creator._oci_done_compat = True
    chunk_creator.__wrapped__ = original
    OCIStreamWrapper.chunk_creator = chunk_creator


install_oci_done_compat()


class RefreshingOCISigner:
    """Route LiteLLM signing through the SDK's public auto-refresh entry point."""

    def __init__(self, sdk_signer):
        self._sdk_signer = sdk_signer
        self._lock = threading.Lock()

    def __deepcopy__(self, memo):
        # LiteLLM deep-copies response metadata at stream completion. This
        # process-scoped, lock-protected credential provider must stay shared.
        # Copying its SDK state/locks is neither supported nor desirable.
        memo[id(self)] = self
        return self

    def do_request_sign(self, request, enforce_content_headers=False):
        # LiteLLM calls do_request_sign directly, bypassing SDK __call__.
        # __call__ synchronizes the token AND session key before signing.
        # Serialize signing/refresh only; inference requests remain concurrent.
        with self._lock:
            return self._sdk_signer(
                request, enforce_content_headers=enforce_content_headers
            )

    def refresh_security_token(self):
        with self._lock:
            self._sdk_signer.refresh_security_token()


@asynccontextmanager
async def lifespan(app):
    global signer
    try:
        sdk_signer = await run_in_threadpool(InstancePrincipalsSecurityTokenSigner)
        signer = RefreshingOCISigner(sdk_signer)
    except Exception:
        raise RuntimeError("OCI instance authentication failed during startup") from None
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


def authenticate(request):
    actual = request.headers.get("authorization", "").encode()
    expected = ("Bearer " + KEY).encode()
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(401, "Unauthorized")


async def read_body(request):
    authenticate(request)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 1_000_000:
            raise HTTPException(413, "Request exceeds demo size limit")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        raise HTTPException(400, "Invalid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(400, "Expected JSON object")
    return body


def upstream_error(error):
    # Never return provider bodies, auth headers, prompts or secrets.
    code = getattr(error, "status_code", None)
    logger.warning("Provider failure: %s status=%s", type(error).__name__, code)
    return HTTPException(429 if code == 429 else 502,
                         "OCI request failed; inspect sanitized gateway logs")


def invoke(method, **kwargs):
    settings = dict(oci_signer=signer, oci_region=REGION,
                    oci_compartment_id=COMPARTMENT,
                    timeout=kwargs.pop("_gateway_timeout", 90), num_retries=0)
    try:
        return method(**kwargs, **settings)
    except Exception as error:
        if getattr(error, "status_code", None) != 401:
            raise
        # Retry only a rejected authentication request, never a partial stream.
        with refresh_lock:
            signer.refresh_security_token()
        return method(**kwargs, **settings)


def acquire_slot():
    if not slots.acquire(blocking=False):
        raise HTTPException(429, "Demo is busy; please retry shortly")
    released = False
    lock = threading.Lock()

    def release():
        nonlocal released
        with lock:
            if not released:
                slots.release()
                released = True
    return release


@app.get("/health")
def health():
    # Readiness of the adapter, not an inference/OCI availability test.
    return JSONResponse({"status": "ok" if signer is not None else "starting"},
                        status_code=200 if signer is not None else 503)


@app.get("/v1/models")
def models(request: Request):
    authenticate(request)
    # Only chat models belong in the chat selector. Embeddings use a separate URL.
    return {"object": "list", "data": [
        {"id": model, "object": "model", "created": 0, "owned_by": "oci"}
        for model in CHAT_MODELS
    ]}


"""Inserted into app.py by prepare.py; uses the existing gateway globals.

Native tool turns are deliberately buffered. OCI tool-call deltas in the pinned
LiteLLM adapter do not provide stable indexes/IDs for progressive arguments.
No tools are executed here: execution/authorization remains in Open WebUI/MCP.
"""
from contextvars import ContextVar
import uuid

_native_context = ContextVar("oci_native_context", default=False)
_cohere_choice = ContextVar("oci_cohere_choice", default=None)


def native_require(condition, detail):
    if not condition:
        raise HTTPException(400, detail)


def native_name(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) is not None


def native_json_object(value):
    try:
        parsed = json.loads(value, parse_constant=lambda _: None)
        # Reject NaN/Infinity rather than silently accepting invalid JSON.
        json.dumps(json.loads(value), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        return False
    return isinstance(parsed, dict)


def native_options(body, model):
    native_require(not body.get("functions") and body.get("function_call") is None,
                   "Deprecated functions/function_call are not supported")
    tools = body.get("tools")
    native_require(tools is None or isinstance(tools, list), "tools must be a list")
    tools = tools or []
    choice = body.get("tool_choice")
    parallel = body.get("parallel_tool_calls")
    native_require(model in CHAT_MODELS, "Native model is not allowed")
    native_require(len(tools) <= 32, "Demo supports at most 32 tools")
    clean, names = [], set()
    for tool in tools:
        native_require(isinstance(tool, dict) and tool.get("type") == "function",
                       "Only function tools are supported")
        fn = tool.get("function")
        native_require(isinstance(fn, dict), "Invalid function definition")
        name = fn.get("name")
        native_require(native_name(name) and name not in names, "Invalid or duplicate tool name")
        names.add(name)
        description = fn.get("description", "")
        native_require(isinstance(description, str) and len(description) <= 8192,
                       "Invalid tool description")
        native_require(fn.get("strict") in (None, False), "Strict schema mode is not supported")
        schema = fn.get("parameters", {"type": "object", "properties": {}})
        native_require(isinstance(schema, dict) and schema.get("type") == "object",
                       "Tool parameters must be an object schema")
        # Do not resolve remote references or accept non-JSON values. The OCI
        # adapter may simplify schemas; strict schema conformance is not promised.
        def safe_schema(node, depth=0):
            native_require(depth <= 24, "Tool schema nesting exceeds demo limit")
            if isinstance(node, dict):
                native_require("$ref" not in node and "$dynamicRef" not in node,
                               "Schema references are not supported in this demo")
                for child in node.values(): safe_schema(child, depth + 1)
            elif isinstance(node, list):
                for child in node: safe_schema(child, depth + 1)
        safe_schema(schema)
        try:
            encoded = json.dumps(schema, allow_nan=False)
        except (TypeError, ValueError, RecursionError):
            raise HTTPException(400, "Invalid JSON schema") from None
        native_require(len(encoded) <= 32768, "Tool schema exceeds demo limit")
        clean.append({"type": "function", "function": {
            "name": name, "description": description, "parameters": schema}})
    native_require(parallel is None or type(parallel) is bool, "parallel_tool_calls must be boolean")
    # The pinned OCI adapter cannot enforce single-call mode. Never silently
    # promise parallel_tool_calls=False. Omitted/True allows a bounded call list.
    native_require(parallel is not False, "parallel_tool_calls=False is not supported by this OCI adapter")
    native_require(bool(clean) or choice in (None, "none"), "tool_choice requires tools")
    if isinstance(choice, dict):
        fn = choice.get("function")
        native_require(choice.get("type") == "function" and isinstance(fn, dict), "Invalid tool_choice")
        name = fn.get("name")
        native_require(isinstance(name, str) and name in names, "Selected tool is not defined")
        choice = {"type": "function", "function": {"name": name}}
    else:
        native_require(choice in (None, "auto", "none", "required"), "Invalid tool_choice")
    options = {"tools": clean, "tool_choice": choice or "auto"} if clean else {}
    if model.startswith("cohere."):
        native_require(choice in (None, "auto", "none"),
                       "Cohere supports automatic tool selection or none, not forced tool_choice")
        history = body.get("messages")
        if isinstance(history, list) and any(isinstance(m, dict) and
                (m.get("tool_calls") or m.get("role") == "tool") for m in history):
            native_require(bool(clean), "Cohere tool history requires tool definitions")
    return options


def native_messages(messages, model):
    native_require(isinstance(messages, list) and 1 <= len(messages) <= 100,
                   "Expected 1 to 100 messages")
    clean, pending, used = [], set(), set()
    has_history = False
    for message in messages:
        native_require(isinstance(message, dict), "Invalid message")
        role, content = message.get("role"), message.get("content")
        calls = message.get("tool_calls")
        native_require(role in ("system", "user", "assistant", "tool"), "Unsupported message role")
        native_require(not message.get("function_call"), "Deprecated function messages are not supported")
        if role == "tool":
            native_require(model in CHAT_MODELS, "Native model is not allowed")
            call_id = message.get("tool_call_id")
            native_require(isinstance(call_id, str) and call_id in pending and isinstance(content, str),
                           "Tool result must match an unresolved tool call and contain text")
            native_require(not calls, "Tool result cannot contain tool_calls")
            pending.remove(call_id)
            clean.append({"role": "tool", "content": content, "tool_call_id": call_id})
            has_history = True
            continue
        native_require(not pending, "Missing tool results before next message")
        native_require(message.get("tool_call_id") is None, "Unexpected tool_call_id")
        if calls is not None and calls != []:
            native_require(model in CHAT_MODELS and role == "assistant", "Only assistant messages may call tools")
            native_require(isinstance(calls, list) and 1 <= len(calls) <= 32, "Invalid tool call list")
            native_require(content is None or isinstance(content, str), "Invalid assistant tool-call content")
            validated = []
            for call in calls:
                native_require(isinstance(call, dict) and call.get("type") == "function", "Invalid tool call")
                call_id, fn = call.get("id"), call.get("function")
                native_require(isinstance(call_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,200}", call_id)
                               and call_id not in used, "Invalid or duplicate tool call id")
                native_require(isinstance(fn, dict) and native_name(fn.get("name")), "Invalid called function")
                args = fn.get("arguments")
                native_require(isinstance(args, str) and len(args) <= 32768 and native_json_object(args),
                               "Tool arguments must be a JSON object string")
                validated.append({"id": call_id, "type": "function", "function": {
                    "name": fn["name"], "arguments": args}})
                pending.add(call_id)
                used.add(call_id)
            clean.append({"role": "assistant", "content": content, "tool_calls": validated})
            has_history = True
        else:
            native_require(isinstance(content, str), "Demo accepts text-only messages")
            clean.append({"role": role, "content": content})
    native_require(not pending, "All assistant tool calls need tool results")
    return clean, has_history


def cohere_continuation(messages):
    """OCI/Cohere v1 continuation: complete history plus latest toolResults.

    Input has already passed native_messages. Keep the latest user and mixed
    assistant text exactly once; merge parallel results by call ID, not position.
    """
    history, calls = [], {}
    for message in messages:
        role = message["role"]
        if role == "system":
            continue  # The pinned adapter already places these in preambleOverride.
        if role == "tool":
            result = {"call": calls[message["tool_call_id"]],
                      "outputs": [{"output": message["content"]}]}
            if history and history[-1]["role"] == "TOOL":
                history[-1]["toolResults"].append(result)
            else:
                history.append({"role": "TOOL", "toolResults": [result]})
        else:
            entry = {"role": "USER" if role == "user" else "CHATBOT",
                     "message": message.get("content") or ""}
            if message.get("tool_calls"):
                entry["toolCalls"] = []
                for call in message["tool_calls"]:
                    converted = {"name": call["function"]["name"],
                                 "parameters": json.loads(call["function"]["arguments"])}
                    calls[call["id"]] = converted
                    entry["toolCalls"].append(converted)
            history.append(entry)
    if not history or history[-1]["role"] != "TOOL":
        raise ValueError("Cohere continuation needs trailing tool results")
    return history[:-1], history[-1]["toolResults"]


def native_cohere_citations(payload):
    """Normalize the OCI citation alias for pinned LiteLLM, without dropping data.

    Keep all response validation in place. Never invent IDs, accept conflicting
    aliases or modify the caller's raw response. Scoped to native Cohere only.
    """
    raw = payload.get("chatResponse", {})
    citations = raw.get("citations")
    if not isinstance(citations, list):
        return payload  # The original schema still validates missing/null/types.
    converted, changed = [], False
    for citation in citations:
        if isinstance(citation, dict) and "documentIds" in citation:
            ids = citation["documentIds"]
            if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
                raise ValueError("Invalid OCI citation identifiers")
            if "document_ids" in citation and citation["document_ids"] != ids:
                raise ValueError("Conflicting OCI citation identifiers")
            citation = dict(citation, document_ids=list(ids))
            changed = True
        converted.append(citation)
    if not changed:
        return payload
    return dict(payload, chatResponse=dict(raw, citations=converted))


def install_native_compat():
    """Scoped fixes: raw finish validation and mixed text/tool history.

    Active only within native_completion(), never for other models/plain chat.
    No streaming-parser monkeypatch is added: native turns are buffered.
    """
    import litellm.llms.oci.chat.transformation as transformation
    if getattr(transformation.handle_generic_response, "_native_compat", False):
        return
    original_response = transformation.handle_generic_response
    original_cohere_response = transformation.handle_cohere_response
    original_messages = transformation.adapt_messages_to_generic_oci_standard
    original_request = transformation.OCIChatConfig.transform_request

    def transform_request(self, model, messages, optional_params, litellm_params, headers):
        data = original_request(self, model, messages, optional_params, litellm_params, headers)
        request = data.get("chatRequest", {})
        if (_native_context.get() and request.get("apiFormat") == "COHERE"
                and messages and messages[-1].get("role") == "tool"):
            history, results = cohere_continuation(messages)
            if not request.get("tools"):
                raise ValueError("Cohere continuation needs tool definitions")
            request.update(message="", chatHistory=history, toolResults=results)
            # With results, single-step asks for a final answer, not another tool.
            # native_response independently rejects any call when choice is none.
            request["isForceSingleStep"] = _cohere_choice.get() == "none"
        return data

    def handle_response(json_data, model, model_response, raw_response):
        if not _native_context.get():
            return original_response(json_data, model, model_response, raw_response)
        choices = json_data.get("chatResponse", {}).get("choices", [])
        if len(choices) != 1:
            raise ValueError("Invalid OCI native choices")
        reason = choices[0].get("finishReason")
        reasons = {"stop": "stop", "COMPLETE": "stop", "tool_calls": "tool_calls",
                   "TOOL_CALL": "tool_calls", "TOOL_CALLS": "tool_calls"}
        if reason not in reasons:
            # Includes truncation and provider failures: never execute partial tools.
            raise ValueError("Incomplete OCI native response")
        response = original_response(json_data, model, model_response, raw_response)
        response.choices[0].finish_reason = reasons[reason]
        return response

    def handle_cohere_response(json_response, model, model_response, raw_response):
        if not _native_context.get():
            return original_cohere_response(json_response, model, model_response, raw_response)
        reason = json_response.get("chatResponse", {}).get("finishReason")
        reasons = {"COMPLETE": "stop", "stop": "stop", "TOOL_CALL": "tool_calls",
                   "TOOL_CALLS": "tool_calls", "tool_calls": "tool_calls"}
        if reason not in reasons:
            raise ValueError("Incomplete OCI Cohere native response")
        normalized = native_cohere_citations(json_response)
        response = original_cohere_response(normalized, model, model_response, raw_response)
        response.choices[0].finish_reason = reasons[reason]
        # Cohere has no provider call IDs. Its LiteLLM fallback is content-derived,
        # which collides when the same function/arguments are used on a later turn.
        for call in response.choices[0].message.tool_calls or []:
            call.id = "call_" + uuid.uuid4().hex
        return response

    def adapt_messages(messages):
        result = original_messages(messages)
        if _native_context.get():
            from litellm.types.llms.oci import OCITextContentPart
            if len(result) != len(messages):
                raise ValueError("OCI message conversion lost a message")
            for source, converted in zip(messages, result):
                if source.get("tool_calls") and source.get("content"):
                    converted.content = [OCITextContentPart(text=source["content"])]
        return result

    handle_response._native_compat = True
    transformation.handle_generic_response = handle_response
    transformation.handle_cohere_response = handle_cohere_response
    transformation.adapt_messages_to_generic_oci_standard = adapt_messages
    transformation.OCIChatConfig.transform_request = transform_request


install_native_compat()


def native_completion(**kwargs):
    # COHERE requests have no toolChoice field in this pinned API adapter.
    # Keep definitions whenever there is tool history. Withholding them makes
    # OCI reject the history. Final-result none uses isForceSingleStep instead.
    selection = None
    if kwargs.get("model", "").startswith("oci/cohere."):
        selection = kwargs.pop("tool_choice", None)
        history = any(m.get("tool_calls") or m.get("role") == "tool"
                      for m in kwargs.get("messages", []))
        if selection == "none" and not history:
            kwargs.pop("tools", None)
        elif selection not in (None, "auto", "none"):
            raise ValueError("Unsupported Cohere tool choice")
    token = _native_context.set(True)
    choice_token = _cohere_choice.set(selection)
    try:
        return litellm.completion(**kwargs)
    finally:
        _cohere_choice.reset(choice_token)
        _native_context.reset(token)


def native_response(payload, options):
    """Validate before exposing any executable tool call to the client."""
    choices = payload.get("choices", [])
    if len(choices) != 1:
        raise ValueError("Invalid native response")
    choice = choices[0]
    message = choice.get("message", {})
    calls = message.get("tool_calls") or []
    allowed = {tool["function"]["name"] for tool in options.get("tools", [])}
    selection = options.get("tool_choice", "none")
    reason = choice.get("finish_reason")
    if calls:
        if reason not in ("stop", "tool_calls") or selection == "none" or len(calls) > 32:
            raise ValueError("Invalid native tool response")
        # Reuse input validation, with synthetic result messages, without executing.
        native_messages([dict(message, role="assistant")] + [
            {"role": "tool", "tool_call_id": c.get("id"), "content": ""} for c in calls], CHAT)
        for call in calls:
            name = call["function"]["name"]
            if name not in allowed or (isinstance(selection, dict) and name != selection["function"]["name"]):
                raise ValueError("Unexpected tool in response")
        choice["finish_reason"] = "tool_calls"
    elif reason != "stop" or selection == "required" or isinstance(selection, dict):
        raise ValueError("Expected native tool response missing")
    message.setdefault("content", None)
    return payload


def native_sse(payload):
    """A complete, validated native turn delivered as OpenAI-compatible SSE."""
    choice = payload["choices"][0]
    message = choice["message"]
    metadata = {k: payload[k] for k in ("id", "created", "model") if k in payload}
    metadata["object"] = "chat.completion.chunk"
    delta = {"role": "assistant"}
    if message.get("content") is not None:
        delta["content"] = message["content"]
    if message.get("tool_calls"):
        delta["tool_calls"] = [dict(call, index=i) for i, call in enumerate(message["tool_calls"])]
    yield "data: " + json.dumps(dict(metadata, choices=[{"index": 0, "delta": delta,
                                                        "finish_reason": None}]), ensure_ascii=False) + "\n\n"
    final = dict(metadata, choices=[{"index": 0, "delta": {}, "finish_reason": choice["finish_reason"]}])
    if "usage" in payload:
        final["usage"] = payload["usage"]
    yield "data: " + json.dumps(final, ensure_ascii=False) + "\n\n"
    yield "data: [DONE]\n\n"


def chat_call(body):
    model = body.get("model")
    if not isinstance(model, str) or model not in CHAT_MODELS:
        raise HTTPException(400, "Chat model is not allowed")
    policy = CHAT_MODELS[model]
    options = native_options(body, model)
    messages, tool_history = native_messages(body.get("messages"), model)
    native = bool(options or tool_history)
    stream = body.get("stream", False)
    if not isinstance(stream, bool):
        raise HTTPException(400, "stream must be a boolean")
    tokens = body.get("max_completion_tokens")
    if tokens is None:
        tokens = body.get("max_tokens")
    if tokens is None:
        tokens = policy["default_tokens"]
    if type(tokens) is not int or tokens < 1:
        raise HTTPException(400, "Invalid token limit")
    kwargs = dict(model="oci/" + model, messages=messages, stream=False if native else stream,
                  max_tokens=min(tokens, policy["max_tokens"]),
                  _gateway_timeout=policy["timeout"])
    # Do not forward arbitrary URL, credentials, provider or routing parameters.
    kwargs.update(options)
    for name, lower, upper in (("temperature", 0, 2), ("top_p", 0, 1)):
        value = body.get(name)
        if value is not None:
            if type(value) not in (int, float) or not lower <= value <= upper:
                raise HTTPException(400, "Invalid sampling parameter")
            kwargs[name] = value
    release = acquire_slot()
    try:
        result = invoke(native_completion if native else litellm.completion, **kwargs)
    except Exception as error:
        release()
        raise upstream_error(error) from None
    if native:
        try:
            payload = native_response(result.model_dump(exclude_none=True), options)
        except Exception as error:
            raise upstream_error(error) from None
        finally:
            release()
        if stream:
            return StreamingResponse(native_sse(payload), media_type="text/event-stream",
                                     headers={"Cache-Control": "no-cache"})
        return payload
    if not stream:
        try:
            return result.model_dump(exclude_none=True)
        finally:
            release()

    def events():
        try:
            for chunk in result:
                payload = chunk.model_dump(exclude_none=True)
                yield "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
            yield "data: [DONE]\n\n"
        except Exception as error:
            upstream_error(error)
            yield 'data: {"error":{"message":"OCI stream failed","type":"upstream_error"}}\n\n'
            yield "data: [DONE]\n\n"
        finally:
            try:
                close = getattr(result, "close", None)
                if callable(close):
                    close()
            finally:
                release()
    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"},
                             background=BackgroundTask(release))


@app.post("/v1/chat/completions")
async def chat(request: Request):
    return await run_in_threadpool(chat_call, await read_body(request))


def embedding_call(body):
    if body.get("model") != EMBED:
        raise HTTPException(400, "Embedding model is not allowed")
    texts = body.get("input")
    texts = [texts] if isinstance(texts, str) else texts
    if (not isinstance(texts, list) or not 1 <= len(texts) <= 96
            or any(not isinstance(text, str) or not text.strip() for text in texts)):
        raise HTTPException(400, "Expected 1 to 96 non-empty texts")
    kind = body.get("input_type", "search_document")
    if kind not in ("search_document", "search_query"):
        raise HTTPException(400, "Unsupported input_type")
    if body.get("encoding_format", "float") != "float":
        raise HTTPException(400, "Only float embeddings are supported")
    if body.get("dimensions", 1536) != 1536:
        raise HTTPException(400, "This demo uses 1536 dimensions")
    release = acquire_slot()
    try:
        result = invoke(litellm.embedding, model="oci/" + EMBED,
                        input=texts, input_type=kind)
        payload = result.model_dump(exclude_none=True)
        if len(payload["data"]) != len(texts) or any(
                len(item["embedding"]) != 1536 for item in payload["data"]):
            raise ValueError("Unexpected embedding dimensions")
        return payload
    except Exception as error:
        raise upstream_error(error) from None
    finally:
        release()


@app.post("/v1/embeddings")
async def embeddings(request: Request):
    return await run_in_threadpool(embedding_call, await read_body(request))
