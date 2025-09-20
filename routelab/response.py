from __future__ import annotations

import json
from dataclasses import dataclass, field

from routelab.models import OutboundResponse


@dataclass(slots=True)
class ResponseSpec:
    status_code: int
    content: bytes = b""
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def json(
        cls,
        payload: object,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> "ResponseSpec":
        merged_headers = {"content-type": "application/json"}
        if headers:
            merged_headers.update(headers)
        return cls(
            status_code=status_code,
            content=json.dumps(payload).encode("utf-8"),
            headers=merged_headers,
        )

    @classmethod
    def text(
        cls,
        payload: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> "ResponseSpec":
        merged_headers = {"content-type": "text/plain; charset=utf-8"}
        if headers:
            merged_headers.update(headers)
        return cls(status_code=status_code, content=payload.encode("utf-8"), headers=merged_headers)

    def to_outbound(self) -> OutboundResponse:
        return OutboundResponse(status_code=self.status_code, headers=dict(self.headers), content=self.content)
