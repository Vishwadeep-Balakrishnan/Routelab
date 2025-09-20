from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from routelab.models import Event


class EventLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: Event) -> None:
        if not self.path:
            return
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")
