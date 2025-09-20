from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from routelab.models import OutboundRequest, OutboundResponse
from routelab.redaction import Redactor


class Recorder:
    def __init__(self, path: str | Path, redactor: Redactor | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.redactor = redactor or Redactor()

    def record(self, request: OutboundRequest, response: OutboundResponse) -> None:
        entry = {
            "fingerprint": fingerprint_request(request, self.redactor),
            "request": serialize_request(request, self.redactor),
            "response": serialize_response(response, self.redactor),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")


class Replayer:
    def __init__(self, path: str | Path, redactor: Redactor | None = None) -> None:
        self.path = Path(path)
        self.redactor = redactor or Redactor()
        self._index = self._load()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}
        if not self.path.exists():
            return index
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                entry = json.loads(line)
                index.setdefault(entry["fingerprint"], []).append(entry)
        return index

    def lookup(self, request: OutboundRequest) -> OutboundResponse | None:
        fp = fingerprint_request(request, self.redactor)
        matches = self._index.get(fp, [])
        if not matches:
            return None
        entry = matches[0]
        resp = entry["response"]
        return OutboundResponse(
            status_code=resp["status_code"],
            headers=resp.get("headers", {}),
            content=resp.get("content", "").encode("utf-8"),
        )


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    sorted_query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)), doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, sorted_query, ""))


SELECTED_HEADERS = ["accept", "content-type"]


def fingerprint_request(request: OutboundRequest, redactor: Redactor | None = None) -> str:
    redactor = redactor or Redactor()
    normalized = {
        "method": request.method.upper(),
        "url": normalize_url(request.url),
        "headers": {k.lower(): v for k, v in redactor.redact_headers(request.headers).items() if k.lower() in SELECTED_HEADERS},
        "body_sha256": hashlib.sha256(redactor.redact_bytes(request.content) or b"").hexdigest(),
    }
    encoded = json.dumps(normalized, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def serialize_request(request: OutboundRequest, redactor: Redactor) -> dict[str, Any]:
    return {
        "method": request.method.upper(),
        "url": normalize_url(request.url),
        "headers": redactor.redact_headers(request.headers),
        "content": (redactor.redact_bytes(request.content) or b"").decode("utf-8", errors="replace"),
    }


def serialize_response(response: OutboundResponse, redactor: Redactor) -> dict[str, Any]:
    return {
        "status_code": response.status_code,
        "headers": redactor.redact_headers(response.headers),
        "content": (redactor.redact_bytes(response.content) or b"").decode("utf-8", errors="replace"),
    }
