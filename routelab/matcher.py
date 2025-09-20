from __future__ import annotations

from dataclasses import dataclass, field

from routelab.models import OutboundRequest


@dataclass(slots=True)
class MatchSpec:
    host: str | None = None
    method: str | None = None
    path: str | None = None
    path_prefix: str | None = None
    query_contains: dict[str, str] = field(default_factory=dict)
    header_contains: dict[str, str] = field(default_factory=dict)

    def matches(self, request: OutboundRequest) -> bool:
        if self.host and request.host != self.host:
            return False
        if self.method and request.method.upper() != self.method.upper():
            return False
        if self.path and request.path != self.path:
            return False
        if self.path_prefix and not request.path.startswith(self.path_prefix):
            return False
        for key, value in self.query_contains.items():
            if value not in request.query.get(key, []):
                return False
        lowered_headers = {k.lower(): v for k, v in request.headers.items()}
        for key, value in self.header_contains.items():
            if lowered_headers.get(key.lower()) != value:
                return False
        return True
