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
