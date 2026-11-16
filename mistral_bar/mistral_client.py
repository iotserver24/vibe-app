import json

import requests

API_URL = "https://api.mistral.ai/v1/chat/completions"
TIMEOUT = 120


class MistralError(Exception):
    pass


def chat(api_key, model, messages, tools=None):
    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        raise MistralError(f"Network error: {e}") from e
    if resp.status_code != 200:
        try:
            detail = resp.json().get("message", resp.text[:300])
        except ValueError:
            detail = resp.text[:300]
        raise MistralError(f"API error {resp.status_code}: {detail}")
    return resp.json()


def chat_stream(api_key, model, messages, tools=None, on_delta=None):
    payload = {"model": model, "messages": messages, "stream": True}
    if tools:
        payload["tools"] = tools
    try:
        resp = requests.post(
            API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=(10, TIMEOUT),
            stream=True,
        )
    except requests.RequestException as e:
        raise MistralError(f"Network error: {e}") from e
    if resp.status_code != 200:
        try:
            detail = resp.json().get("message", resp.text[:300])
        except ValueError:
            detail = resp.text[:300]
        raise MistralError(f"API error {resp.status_code}: {detail}")

    content_parts = []
    tool_calls = {}
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data = line[6:]
        if data.strip() == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue
        choices = chunk.get("choices") or []
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        piece = delta.get("content")
        if isinstance(piece, list):
            piece = "".join(p.get("text", "") for p in piece if isinstance(p, dict))
        if isinstance(piece, str) and piece:
            content_parts.append(piece)
            if on_delta:
                on_delta(piece)
        for tc in delta.get("tool_calls") or []:
            idx = tc.get("index", 0)
            slot = tool_calls.setdefault(idx, {"id": "", "name": "", "arguments": ""})
            if tc.get("id"):
                slot["id"] = tc["id"]
            fn = tc.get("function") or {}
            if fn.get("name"):
                slot["name"] = fn["name"]
            if fn.get("arguments"):
                slot["arguments"] += fn["arguments"]

    message = {"role": "assistant", "content": "".join(content_parts)}
    if tool_calls:
        message["tool_calls"] = [
            {
                "id": s["id"],
                "type": "function",
                "function": {"name": s["name"], "arguments": s["arguments"]},
            }
            for _, s in sorted(tool_calls.items())
        ]
    return message


def extract_reply(message):
    if message.get("tool_calls"):
        return None
    content = message.get("content") or ""
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict)]
        content = "".join(parts)
    return content.strip()


def extract_tool_calls(message):
    return message.get("tool_calls") or []
