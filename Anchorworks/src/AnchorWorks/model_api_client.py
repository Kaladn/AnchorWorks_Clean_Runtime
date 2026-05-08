from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelApiClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout_seconds: int = 90,
    ) -> None:
        self.api_key = api_key if api_key is not None else (
            os.getenv("ANCHORWORKS_MODEL_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        )
        self.base_url = (base_url or os.getenv("ANCHORWORKS_MODEL_API_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        self.default_model = default_model or os.getenv("ANCHORWORKS_MODEL_API_MODEL") or "gpt-4.1-mini"
        self.timeout_seconds = int(os.getenv("ANCHORWORKS_MODEL_API_TIMEOUT", str(timeout_seconds)) or timeout_seconds)

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "configured": bool(self.api_key),
            "base_url": self.base_url,
            "default_model": self.default_model,
            "endpoint": f"{self.base_url}/chat/completions",
        }

    def chat(self, messages: list[dict[str, str]], *, model: str | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise ValueError("external model API key is not configured")
        target_model = (model or self.default_model or "").strip()
        if not target_model:
            raise ValueError("external model name is required")

        endpoint = f"{self.base_url}/chat/completions"
        payload = {
            "model": target_model,
            "messages": messages,
        }
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ValueError(f"external model API failed: {exc.code} {detail}") from exc
        except URLError as exc:
            raise ValueError(f"external model API unavailable: {exc.reason}") from exc

        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ValueError("external model API returned no choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first, dict) else {}
        content = message.get("content") if isinstance(message, dict) else ""
        response_text = _content_to_text(content).strip()
        if not response_text:
            raise ValueError("external model API returned an empty response")

        return {
            "response": response_text,
            "provider": "external_api",
            "model": data.get("model") or target_model,
            "requested_model": target_model,
            "endpoint": endpoint,
            "response_id": data.get("id"),
            "finish_reason": first.get("finish_reason"),
        }


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return ""
