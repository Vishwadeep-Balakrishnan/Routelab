from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse


@dataclass(slots=True)
class OutboundRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes | None = None
    timeout: float | None = None
    extensions: dict[str, Any] = field(default_factory=dict)

    @property
    def parsed(self):
        return urlparse(self.url)

    @property
    def host(self) -> str:
        return self.parsed.netloc

    @property
    def path(self) -> str:
        return self.parsed.path or "/"

    @property
    def query(self) -> dict[str, list[str]]:
        return parse_qs(self.parsed.query, keep_blank_values=True)

    def with_url(self, new_url: str) -> "OutboundRequest":
        self.url = new_url
        return self


@dataclass(slots=True)
class OutboundResponse:
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    content: bytes = b""

    def text(self, encoding: str = "utf-8") -> str:
        return self.content.decode(encoding, errors="replace")

    def json(self) -> Any:
        import json

        return json.loads(self.content.decode("utf-8"))


@dataclass(slots=True)
class Event:
    timestamp: str
    method: str
    url: str
    host: str
    path: str
    rule_name: str | None
    action: str | None
    status_code: int | None
    elapsed_ms: float
    outcome: str
    error_type: str | None = None
    replay_hit: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
