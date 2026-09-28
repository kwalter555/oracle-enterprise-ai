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
