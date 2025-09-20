from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Iterable

import httpx

from routelab.actions import Action, RecordAction, ReplayAction
from routelab.exceptions import ReplayMissError, RouteLabError
from routelab.logging import EventLogger
from routelab.models import Event, OutboundRequest, OutboundResponse
from routelab.recorder import Recorder, Replayer
from routelab.redaction import Redactor
from routelab.rules import Route

BeforeHook = Callable[[OutboundRequest], OutboundRequest | None]
AfterHook = Callable[[OutboundRequest, OutboundResponse], OutboundResponse | None]
ErrorHook = Callable[[OutboundRequest, Exception], None]


@dataclass(slots=True)
class RouteContext:
    session: "RouteLabSession"
    request: OutboundRequest
    record_requested: bool = False
    replay_hit: bool = False

    def make_response(self, status_code: int, content: bytes = b"", headers: dict[str, str] | None = None) -> OutboundResponse:
        return OutboundResponse(status_code=status_code, headers=headers or {}, content=content)

    def replay_lookup(self) -> OutboundResponse | None:
        if not self.session.replayer:
            return None
        result = self.session.replayer.lookup(self.request)
        if result is not None:
            self.replay_hit = True
        return result


class RouteLabClient:
    def __init__(self, session: "RouteLabSession") -> None:
        self._session = session

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        return self._session.request(method, url, **kwargs)

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)


class RouteLabSession:
    def __init__(
        self,
        *,
        seed: int | None = None,
        recorder_path: str | None = None,
        replay_path: str | None = None,
        replay_miss_policy: str = "error",
        event_log_path: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.routes: list[Route] = []
        self.before_hooks: list[BeforeHook] = []
        self.after_hooks: list[AfterHook] = []
        self.error_hooks: list[ErrorHook] = []
        self.random = random.Random(seed)
        self.redactor = Redactor()
        self.recorder = Recorder(recorder_path, self.redactor) if recorder_path else None
        self.replayer = Replayer(replay_path, self.redactor) if replay_path else None
        self.replay_miss_policy = replay_miss_policy
        self.event_logger = EventLogger(event_log_path)
        self.timeout = timeout
        self._http = httpx.Client(timeout=timeout)

    def add(self, route: Route) -> Route:
        self.routes.append(route)
        return route

    def extend(self, routes: Iterable[Route]) -> None:
        self.routes.extend(routes)

    def client(self) -> RouteLabClient:
        return RouteLabClient(self)

    def enable_recording(self, path: str) -> None:
        self.recorder = Recorder(path, self.redactor)

    def enable_replay(self, path: str, miss_policy: str = "error") -> None:
        self.replayer = Replayer(path, self.redactor)
        self.replay_miss_policy = miss_policy

    def before_request(self, func: BeforeHook) -> BeforeHook:
        self.before_hooks.append(func)
        return func

    def after_response(self, func: AfterHook) -> AfterHook:
        self.after_hooks.append(func)
        return func

    def on_error(self, func: ErrorHook) -> ErrorHook:
        self.error_hooks.append(func)
        return func

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        content: bytes | str | None = None,
        json: object | None = None,
        timeout: float | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        request_content = self._prepare_content(content=content, json_body=json)
        if params:
            url = str(httpx.URL(url, params=params))
        req = OutboundRequest(
            method=method.upper(),
            url=url,
            headers=dict(headers or {}),
            content=request_content,
            timeout=timeout or self.timeout,
        )

        for hook in self.before_hooks:
            maybe_req = hook(req)
            if maybe_req is not None:
                req = maybe_req

        matched_route = self._find_matching_route(req)
        context = RouteContext(session=self, request=req)

        started = time.perf_counter()
        action_name: str | None = None
        try:
            outbound = self._execute(req, matched_route, context)
            for hook in self.after_hooks:
                maybe_resp = hook(req, outbound)
                if maybe_resp is not None:
                    outbound = maybe_resp
            elapsed_ms = (time.perf_counter() - started) * 1000
            self._emit_event(
                req,
                matched_route,
                action_name=context.request.extensions.get("final_action"),
                response=outbound,
                elapsed_ms=elapsed_ms,
                outcome="ok",
                replay_hit=context.replay_hit,
            )
            return self._to_httpx_response(req, outbound)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            for hook in self.error_hooks:
                hook(req, exc)
            self._emit_event(
                req,
                matched_route,
                action_name=context.request.extensions.get("final_action"),
                response=None,
                elapsed_ms=elapsed_ms,
                outcome="error",
                error=exc,
                replay_hit=context.replay_hit,
            )
            raise

    def _execute(self, req: OutboundRequest, route: Route | None, context: RouteContext) -> OutboundResponse:
        synthetic_response: OutboundResponse | None = None
        if route:
            for action in route.actions:
                if not isinstance(action, Action):
                    continue
                if not action.applies(self.random):
                    continue
                req.extensions["final_action"] = action.kind
                result = action.apply(context)
                if isinstance(action, ReplayAction):
                    if result is not None:
                        synthetic_response = result
                        break
                    if self.replay_miss_policy == "error":
                        raise ReplayMissError(f"No replay match found for {req.method} {req.url}")
                    if self.replay_miss_policy == "warn":
                        req.extensions["replay_warning"] = True
                    continue
                if result is None:
                    continue
                synthetic_response = result
                break

        if synthetic_response is None:
            response = self._send_real_request(req)
        else:
            response = synthetic_response

        should_record = context.record_requested or self.recorder is not None
        if should_record and self.recorder and not context.replay_hit:
            self.recorder.record(req, response)

        return response

    def _send_real_request(self, req: OutboundRequest) -> OutboundResponse:
        response = self._http.request(
            method=req.method,
            url=req.url,
            headers=req.headers,
            content=req.content,
            timeout=req.timeout,
        )
        headers = {k: v for k, v in response.headers.items()}
        return OutboundResponse(status_code=response.status_code, headers=headers, content=response.content)

    def _find_matching_route(self, req: OutboundRequest) -> Route | None:
        for route in self.routes:
            if route.matches(req):
                return route
        return None

    def _to_httpx_response(self, req: OutboundRequest, outbound: OutboundResponse) -> httpx.Response:
        request = httpx.Request(method=req.method, url=req.url, headers=req.headers, content=req.content)
        return httpx.Response(
            status_code=outbound.status_code,
            headers=outbound.headers,
            content=outbound.content,
            request=request,
        )

    def _prepare_content(self, *, content: bytes | str | None, json_body: object | None) -> bytes | None:
        if json_body is not None:
            import json

            return json.dumps(json_body).encode("utf-8")
        if isinstance(content, str):
            return content.encode("utf-8")
        return content

    def _emit_event(
        self,
        req: OutboundRequest,
        route: Route | None,
        action_name: str | None,
        response: OutboundResponse | None,
        elapsed_ms: float,
        outcome: str,
        error: Exception | None = None,
        replay_hit: bool = False,
    ) -> None:
        event = Event(
            timestamp=datetime.now(UTC).isoformat(),
            method=req.method,
            url=req.url,
            host=req.host,
            path=req.path,
            rule_name=route.name,
            action=action_name,
            status_code=response.status_code if response else None,
            elapsed_ms=round(elapsed_ms, 3),
            outcome=outcome,
            error_type=type(error).__name__ if error else None,
            replay_hit=replay_hit,
            metadata=req.extensions.copy(),
        )
        self.event_logger.emit(event)
