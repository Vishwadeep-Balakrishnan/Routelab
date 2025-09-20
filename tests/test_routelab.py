import json
from pathlib import Path

import pytest

from routelab import Route, RouteLabSession, ResponseSpec
from routelab.exceptions import ReplayMissError, SimulatedDropError, SimulatedTimeoutError


def test_mock_route_returns_json():
    session = RouteLabSession()
    session.add(Route.named("health").matching(path="/health").mock(ResponseSpec.json({"ok": True})))
    client = session.client()
    response = client.get("https://api.example.com/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_redirect_route_changes_target_url(tmp_path: Path):
    session = RouteLabSession(event_log_path=tmp_path / "events.jsonl")
    session.add(
        Route.named("redirect")
        .matching(host="example.com")
        .redirect("https://new.example.com")
        .mock(ResponseSpec.json({"ok": True}))
    )

    response = session.client().get("https://example.com/test")
    assert response.json() == {"ok": True}

    rows = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert rows[0]["url"].startswith("https://new.example.com/")


def test_drop_action_raises():
    session = RouteLabSession(seed=1)
    session.add(Route.named("dropper").matching(host="api.example.com").drop())
    with pytest.raises(SimulatedDropError):
        session.client().get("https://api.example.com/test")


def test_timeout_action_raises():
    session = RouteLabSession(seed=1)
    session.add(Route.named("slow").matching(host="api.example.com").timeout())
    with pytest.raises(SimulatedTimeoutError):
        session.client().get("https://api.example.com/test")


def test_record_and_replay_roundtrip(tmp_path: Path):
    cassette = tmp_path / "cassette.jsonl"
    session = RouteLabSession(recorder_path=cassette)
    session.add(Route.named("stub").matching(path="/users").mock(ResponseSpec.json({"users": [1, 2, 3]})))
    first = session.client().get("https://api.example.com/users")
    assert first.json() == {"users": [1, 2, 3]}

    replay = RouteLabSession(replay_path=cassette)
    replay.add(Route.named("replay-users").matching(path="/users").replay())
    second = replay.client().get("https://api.example.com/users")
    assert second.json() == {"users": [1, 2, 3]}


def test_replay_miss_errors(tmp_path: Path):
    cassette = tmp_path / "cassette.jsonl"
    cassette.write_text("")
    session = RouteLabSession(replay_path=cassette, replay_miss_policy="error")
    session.add(Route.named("replay-users").matching(path="/users").replay())
    with pytest.raises(ReplayMissError):
        session.client().get("https://api.example.com/users")
