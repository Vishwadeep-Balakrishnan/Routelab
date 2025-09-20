from __future__ import annotations

from dataclasses import dataclass, field

from routelab.actions import (
    DelayAction,
    DropAction,
    MockAction,
    RecordAction,
    RedirectAction,
    ReplayAction,
    StatusAction,
    TimeoutAction,
)
from routelab.matcher import MatchSpec
from routelab.response import ResponseSpec


@dataclass(slots=True)
class Route:
    name: str | None = None
    match_spec: MatchSpec = field(default_factory=MatchSpec)
    actions: list[object] = field(default_factory=list)

    @classmethod
    def named(cls, name: str) -> "Route":
        return cls(name=name)

    @classmethod
    def match(
        cls,
        host: str | None = None,
        method: str | None = None,
        path: str | None = None,
        path_prefix: str | None = None,
        query_contains: dict[str, str] | None = None,
        header_contains: dict[str, str] | None = None,
    ) -> "Route":
        route = cls()
        return route.matching(
            host=host,
            method=method,
            path=path,
            path_prefix=path_prefix,
            query_contains=query_contains,
            header_contains=header_contains,
        )

    def matching(
        self,
        host: str | None = None,
        method: str | None = None,
        path: str | None = None,
        path_prefix: str | None = None,
        query_contains: dict[str, str] | None = None,
        header_contains: dict[str, str] | None = None,
    ) -> "Route":
        self.match_spec = MatchSpec(
            host=host,
            method=method,
            path=path,
            path_prefix=path_prefix,
            query_contains=query_contains or {},
            header_contains=header_contains or {},
        )
        return self

    def delay(self, seconds: float) -> "Route":
        self.actions.append(DelayAction(seconds=seconds))
        return self

    def status(
        self,
        status_code: int,
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
        rate: float = 1.0,
    ) -> "Route":
        self.actions.append(StatusAction(status_code=status_code, body=body, headers=headers or {}, rate=rate))
        return self

    def drop(self, rate: float = 1.0) -> "Route":
        self.actions.append(DropAction(rate=rate))
        return self

    def timeout(self, rate: float = 1.0) -> "Route":
        self.actions.append(TimeoutAction(rate=rate))
        return self

    def redirect(self, base_url: str) -> "Route":
        self.actions.append(RedirectAction(base_url=base_url))
        return self

    def mock(self, response: ResponseSpec) -> "Route":
        self.actions.append(MockAction(response=response))
        return self

    def record(self) -> "Route":
        self.actions.append(RecordAction())
        return self

    def replay(self) -> "Route":
        self.actions.append(ReplayAction())
        return self

    def matches(self, request) -> bool:
        return self.match_spec.matches(request)
