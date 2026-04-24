# Routelab

Routelab is a Python library for intercepting outbound HTTP calls. It lets you rewrite requests, simulate failures, mock responses, record real traffic, replay it later, and keep a structured event log of what happened.

It is built around `httpx`.

## What it does

- match requests by host, method, path, headers, or query values
- add request and response hooks
- inject latency, drops, timeouts, or forced status codes
- redirect traffic to another base URL
- return mock responses without touching application code
- record real traffic to a JSONL cassette
- replay traffic from a cassette later
- write a JSONL event log for inspection

## Install

```bash
pip install -e .
```

For tests:

```bash
pip install -e .[dev]
```

## An example

```python
from routelab import Route, RouteLabSession, ResponseSpec

session = RouteLabSession(event_log_path="traffic.jsonl")

@session.before_request
def add_trace(req):
    req.headers["x-trace-id"] = "dev-123"
    return req

session.add(
    Route.named("healthcheck")
    .matching(path="/health")
    .mock(ResponseSpec.json({"ok": True}))
)

client = session.client()
response = client.get("https://api.example.com/health")
print(response.json())
```

## Routes

Routes are matched in order. The first matching route wins.

```python
from routelab import Route

route = (
    Route.named("vendor-delay")
    .matching(host="api.vendor.com", method="GET", path_prefix="/v1")
    .delay(1.25)
    .status(503, body="temporary failure", rate=0.2)
)
```

Available actions in this version:

- `delay(seconds)`
- `status(code, body=None, headers=None, rate=1.0)`
- `drop(rate=1.0)`
- `timeout(rate=1.0)`
- `redirect(base_url)`
- `mock(response)`
- `record()`
- `replay()`

## Recording and replay

Session-wide recording:

```python
from routelab import RouteLabSession

session = RouteLabSession(recorder_path="cassettes/vendor.jsonl")
client = session.client()
client.get("https://httpbin.org/get")
```

Replay from the same cassette later:

```python
session = RouteLabSession(replay_path="cassettes/vendor.jsonl", replay_miss_policy="error")
client = session.client()
client.get("https://httpbin.org/get")
```

Replay miss policies:

- `error`: raise an exception when no match is found
- `warn`: continue with a real request and annotate the event log
- `passthrough`: continue with a real request quietly

You can also attach replay or record behavior to a specific route instead of the whole session.

## Hooks

```python
@session.before_request
def inject_auth(req):
    req.headers["authorization"] = "Bearer local-token"
    return req

@session.after_response
def tag_response(req, resp):
    resp.headers["x-routelab"] = "1"
    return resp

@session.on_error
def log_failure(req, exc):
    print("request failed:", req.url, type(exc).__name__)
```

## Event log

If `event_log_path` is set, routelab writes one JSON object per request. The log includes the URL, matched rule, final action, status code, elapsed time, replay hits, and errors.

You can inspect it with the CLI:

```bash
routelab inspect traffic.jsonl
```

## Layout

```text
routelab/
  actions.py
  cli.py
  exceptions.py
  logging.py
  matcher.py
  models.py
  recorder.py
  redaction.py
  response.py
  rules.py
  session.py
```

## Notes

This version is sync-first and `httpx`-only. It is meant to be simple and easy to extend.
