from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlparse

from routelab.exceptions import SimulatedDropError, SimulatedTimeoutError
from routelab.response import ResponseSpec

if TYPE_CHECKING:
    from routelab.models import OutboundRequest, OutboundResponse
    from routelab.session import RouteContext


class Action:
    kind = "action"

    def applies(self, rng: random.Random) -> bool:
        return True

    def apply(self, context: "RouteContext") -> Any:
        raise NotImplementedError


@dataclass(slots=True)
class DelayAction(Action):
    seconds: float
    kind: str = "delay"

    def apply(self, context: "RouteContext") -> None:
        time.sleep(self.seconds)


@dataclass(slots=True)
class StatusAction(Action):
    status_code: int
    body: str | bytes | None = None
    headers: dict[str, str] = field(default_factory=dict)
    rate: float = 1.0
    kind: str = "status"

    def applies(self, rng: random.Random) -> bool:
        return rng.random() <= self.rate

    def apply(self, context: "RouteContext") -> "OutboundResponse":
        content = self.body.encode("utf-8") if isinstance(self.body, str) else (self.body or b"")
        return context.make_response(self.status_code, content=content, headers=self.headers)


@dataclass(slots=True)
class DropAction(Action):
    rate: float = 1.0
    kind: str = "drop"

    def applies(self, rng: random.Random) -> bool:
        return rng.random() <= self.rate

    def apply(self, context: "RouteContext") -> None:
        raise SimulatedDropError(f"Simulated drop for {context.request.method} {context.request.url}")


@dataclass(slots=True)
class TimeoutAction(Action):
    rate: float = 1.0
    kind: str = "timeout"

    def applies(self, rng: random.Random) -> bool:
        return rng.random() <= self.rate

    def apply(self, context: "RouteContext") -> None:
        raise SimulatedTimeoutError(f"Simulated timeout for {context.request.method} {context.request.url}")


@dataclass(slots=True)
class RedirectAction(Action):
    base_url: str
    kind: str = "redirect"

    def apply(self, context: "RouteContext") -> None:
        req = context.request
        parsed = urlparse(req.url)
        new_url = urljoin(self.base_url.rstrip("/") + "/", parsed.path.lstrip("/"))
        if parsed.query:
            new_url = f"{new_url}?{parsed.query}"
        req.with_url(new_url)


@dataclass(slots=True)
class MockAction(Action):
    response: ResponseSpec
    kind: str = "mock"

    def apply(self, context: "RouteContext") -> "OutboundResponse":
        return self.response.to_outbound()


@dataclass(slots=True)
class RecordAction(Action):
    kind: str = "record"

    def apply(self, context: "RouteContext") -> None:
        context.record_requested = True


@dataclass(slots=True)
class ReplayAction(Action):
    kind: str = "replay"

    def apply(self, context: "RouteContext") -> "OutboundResponse | None":
        return context.replay_lookup()
