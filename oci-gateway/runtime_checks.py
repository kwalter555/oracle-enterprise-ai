"""Checks executed INSIDE a container. No credentials or response text printed."""
import asyncio
import json
import urllib.error
import urllib.request
import uuid

NATIVE_MODELS = ("openai.gpt-oss-20b", "cohere.command-a-03-2025", "google.gemini-2.5-flash",
                 "google.gemini-2.5-pro", "meta.llama-3.3-70b-instruct")
NATIVE_TOOL = "gateway_native_probe"
NATIVE_LABELS = tuple("native / " + model + " / " + mode + " / " + phase
                      for model in NATIVE_MODELS for mode in ("chat", "stream")
                      for phase in ("tool_call", "tool_result"))
NATIVE_TOOLS = [{"type": "function", "function": {
    "name": NATIVE_TOOL,
    "description": "Synthetic gateway test. Accepts probe_code and returns a marker.",
    "parameters": {"type": "object", "properties": {"probe_code": {"type": "string",
                   "description": "Synthetic probe identifier"}}, "required": ["probe_code"]}}}]


def native_payload(value, stream):
    if not stream:
        return value
    message, calls, finish, done = {"role": "assistant", "content": ""}, {}, None, False
    for line in value.splitlines():
        if not line.startswith("data:"):
            continue
        if done:
            raise ValueError("DataAfterDone")
        data = line[5:].strip()
        if data == "[DONE]":
            done = True
            continue
        chunk = json.loads(data)
        if "error" in chunk:
            raise ValueError("StreamError")
        for choice in chunk.get("choices", []):
            if choice.get("index") != 0:
                raise ValueError("UnexpectedChoiceIndex")
            delta = choice.get("delta", {})
            message["content"] += delta.get("content") or ""
            for call in delta.get("tool_calls") or []:
                index = call.get("index")
                if type(index) is not int or index < 0 or index > 31:
                    raise ValueError("MissingToolCallIndex")
                target = calls.setdefault(index, {"id": "", "type": "function",
                                                  "function": {"name": "", "arguments": ""}})
                if call.get("id"):
                    if target["id"] and target["id"] != call["id"]:
                        raise ValueError("UnstableToolCallId")
                    target["id"] = call["id"]
                for field in ("name", "arguments"):
                    target["function"][field] += call.get("function", {}).get(field) or ""
            if choice.get("finish_reason"):
                if finish is not None or choice["finish_reason"] not in ("stop", "tool_calls"):
                    raise ValueError("InvalidNativeFinish")
                finish = choice["finish_reason"]
    if not done or finish is None:
        raise ValueError("IncompleteNativeStream")
    if calls:
        if sorted(calls) != list(range(len(calls))):
            raise ValueError("InvalidToolCallIndexes")
        message["tool_calls"] = [calls[i] for i in sorted(calls)]
    return {"choices": [{"message": message, "finish_reason": finish}]}


def validate_native_call(payload):
    choices = payload["choices"]
    if len(choices) != 1 or choices[0].get("finish_reason") != "tool_calls":
        raise ValueError("MissingNativeToolFinish")
    message = choices[0]["message"]
    calls = message.get("tool_calls", [])
    if len(calls) != 1 or calls[0].get("type") != "function" or not calls[0].get("id"):
        raise ValueError("InvalidNativeToolCall")
    fn = calls[0]["function"]
    if fn["name"] != NATIVE_TOOL or json.loads(fn["arguments"]) != {"probe_code": "ORION-742"}:
        raise ValueError("UnexpectedNativeToolCall")
    return {"role": "assistant", "content": message.get("content"), "tool_calls": calls}

PROMPT = [
    {"role": "system", "content": "Answer briefly. Test document: the project verification marker is OK-742."},
    {"role": "user", "content": "What is the project verification marker?"},
    {"role": "assistant", "content": "OK-742"},
    {"role": "user", "content": "Repeat only the verification marker from the test document."},
]


def validate_answer(content, finish):
    if not isinstance(content, str) or "OK-742" not in content:
        raise ValueError("MissingSyntheticAnswer")
    if finish != "stop":
        raise ValueError("IncompleteAnswer")


def validate_json(payload):
    choice = payload["choices"][0]
    validate_answer(choice["message"].get("content"), choice.get("finish_reason"))


def validate_sse(raw):
    content, finished, done = "", None, False
    for line in raw.splitlines():
        if not line.startswith("data:"):
            continue
        value = line[5:].strip()
        if value == "[DONE]":
            done = True
            break
        part = json.loads(value)
        if "error" in part:
            raise ValueError("StreamError")
        for choice in part.get("choices", []):
            content += choice.get("delta", {}).get("content") or ""
            if choice.get("finish_reason"):
                # A later synthetic stop must not hide an earlier truncation.
                if choice["finish_reason"] != "stop":
                    raise ValueError("IncompleteAnswer")
                finished = choice["finish_reason"]
    if not done:
        raise ValueError("MissingDone")
    validate_answer(content, finished)


def validate_embedding(payload):
    data = payload.get("data", [])
    if len(data) != 1 or len(data[0].get("embedding", [])) != 1536:
        raise ValueError("UnexpectedEmbeddingDimensions")


async def collect_stream(result):
    parts = []
    async for part in result.body_iterator:
        parts.append(part.decode() if isinstance(part, bytes) else part)
    return "".join(parts)


def run_checks(models, inference=False, module=None, key=None, base="http://oci-gateway:4000"):
    """module => candidate in isolated process; otherwise HTTP from Open WebUI."""
    checks = []
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def http(path, body=None, authenticated=True, stream=False):
        headers = {"Content-Type": "application/json"}
        if authenticated:
            headers["Authorization"] = "Bearer " + key
        req = urllib.request.Request(base + path, headers=headers,
            data=None if body is None else json.dumps(body).encode())
        with opener.open(req, timeout=210) as response:
            if response.status != 200:
                raise ValueError("UnexpectedHTTPStatus")
            if stream:
                if "text/event-stream" not in response.headers.get("Content-Type", ""):
                    raise ValueError("UnexpectedContentType")
                return response.read().decode("utf-8")
            return json.load(response)

    def check(label, action):
        try:
            action()
            checks.append({"check": label, "ok": True})
        except Exception as error:
            status = getattr(error, "status_code", None)
            if status is None:
                status = getattr(error, "code", getattr(error, "status", None))
            if not isinstance(status, int):
                status = None
            checks.append({"check": label, "ok": False,
                           "error_type": type(error).__name__, "status": status})
            return False
        return True

    def require(value):
        if not value:
            raise ValueError("CheckFailed")

    if module is None:
        check("health_from_open_webui", lambda: require(http("/health").get("status") == "ok"))

        def unauthorized():
            try:
                http("/v1/models", authenticated=False)
            except urllib.error.HTTPError as error:
                require(error.code == 401)
                return
            raise ValueError("MissingAuthentication")

        def allowlist():
            try:
                http("/v1/chat/completions", {"model": "NOT-ALLOWED", "messages": PROMPT})
            except urllib.error.HTTPError as error:
                require(error.code == 400)
                return
            raise ValueError("MissingAllowlist")

        check("unauthorized_401", unauthorized)
        check("unapproved_model_400", allowlist)
        check("model_list", lambda: require(
            [x["id"] for x in http("/v1/models")["data"]] == list(models)))
        if not all(x["ok"] for x in checks):
            return {"ok": False, "checks": checks}

    if inference:
        for model in models:
            for stream in (False, True):
                def chat(model=model, stream=stream):
                    body = {"model": model, "messages": PROMPT, "stream": stream,
                            "max_tokens": 4096 if model.startswith("google.") else 512}
                    if module is None:
                        result = http("/v1/chat/completions", body, stream=stream)
                    else:
                        result = module.chat_call(body)
                        if stream:
                            result = asyncio.run(collect_stream(result))
                    if stream:
                        validate_sse(result)
                    else:
                        validate_json(result)
                check(model + (" / stream" if stream else " / chat"), chat)
        for kind in ("search_document", "search_query"):
            def embed(kind=kind):
                body = {"model": "cohere.embed-v4.0", "input": ["Test ORION OK-742."],
                        "input_type": kind}
                result = (module.embedding_call(body) if module is not None else
                          http("/v1/embeddings", body))
                validate_embedding(result)
            check("embedding / " + kind, embed)
        for native_model in NATIVE_MODELS:
            for stream in (False, True):
                label = "native / " + native_model + " / " + ("stream" if stream else "chat")
                messages = [{"role": "system", "content":
                             "Test only. First call the requested tool with probe_code ORION-742. "
                             "Then report the exact marker returned by the tool. Do not invent a marker."},
                            {"role": "user", "content": "Call " + NATIVE_TOOL + " with probe_code ORION-742 now."}]
                state = {}

                def native_request(body):
                    result = module.chat_call(body) if module is not None else http(
                        "/v1/chat/completions", body, stream=stream)
                    if module is not None and stream:
                        result = asyncio.run(collect_stream(result))
                    return native_payload(result, stream)

                def first_turn():
                    body = {"model": native_model, "messages": messages, "stream": stream,
                            "max_tokens": 4000, "tools": NATIVE_TOOLS,
                            "tool_choice": "auto"}
                    state["assistant"] = validate_native_call(native_request(body))

                if check(label + " / tool_call", first_turn):
                    def second_turn():
                        marker = "NATIVE-" + uuid.uuid4().hex[:16]
                        assistant = state["assistant"]
                        # This is a locally fabricated test result, NOT an MCP/ADB call.
                        tool_result = {"role": "tool", "tool_call_id": assistant["tool_calls"][0]["id"],
                                       "content": json.dumps({"status": "OK", "marker": marker})}
                        body = {"model": native_model, "messages": messages + [assistant, tool_result],
                                "stream": stream, "max_tokens": 4000, "tools": NATIVE_TOOLS,
                                "tool_choice": "none"}
                        result = native_request(body)["choices"][0]
                        require(result.get("finish_reason") == "stop" and
                                marker in (result["message"].get("content") or "") and
                                not result["message"].get("tool_calls"))
                    check(label + " / tool_result", second_turn)
    return {"ok": bool(checks) and all(x["ok"] for x in checks), "checks": checks}
