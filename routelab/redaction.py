from __future__ import annotations

import json
from typing import Any

DEFAULT_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "proxy-authorization",
}

DEFAULT_SENSITIVE_JSON_KEYS = {
    "password",
    "token",
    "secret",
    "api_key",
    "access_token",
    "refresh_token",
}


class Redactor:
    def __init__(
        self,
        sensitive_headers: set[str] | None = None,
        sensitive_json_keys: set[str] | None = None,
        replacement: str = "[REDACTED]",
    ) -> None:
        self.sensitive_headers = sensitive_headers or set(DEFAULT_SENSITIVE_HEADERS)
        self.sensitive_json_keys = sensitive_json_keys or set(DEFAULT_SENSITIVE_JSON_KEYS)
        self.replacement = replacement

    def redact_headers(self, headers: dict[str, str]) -> dict[str, str]:
        redacted: dict[str, str] = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_headers:
                redacted[key] = self.replacement
            else:
                redacted[key] = value
        return redacted

    def redact_bytes(self, content: bytes | None) -> bytes | None:
        if not content:
            return content
        try:
            decoded = json.loads(content.decode("utf-8"))
        except Exception:
            return content
        redacted = self._redact_json(decoded)
        return json.dumps(redacted, sort_keys=True).encode("utf-8")

    def _redact_json(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: self.replacement if key.lower() in self.sensitive_json_keys else self._redact_json(val)
                for key, val in value.items()
            }
        if isinstance(value, list):
            return [self._redact_json(item) for item in value]
        return value
