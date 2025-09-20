from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def inspect_log(path: str) -> int:
    file_path = Path(path)
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 1

    rows = []
    with file_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))

    if not rows:
        print("No events found.")
        return 0

    hosts = Counter(row["host"] for row in rows)
    outcomes = Counter(row["outcome"] for row in rows)
    rules = Counter(row["rule_name"] or "<none>" for row in rows)
    actions = Counter(row["action"] or "<none>" for row in rows)
    avg_ms = sum(row["elapsed_ms"] for row in rows) / len(rows)

    print(f"events:   {len(rows)}")
    print(f"avg ms:   {avg_ms:.2f}")
    print(f"outcomes: {dict(outcomes)}")
    print(f"hosts:    {dict(hosts.most_common(5))}")
    print(f"rules:    {dict(rules.most_common(5))}")
    print(f"actions:  {dict(actions.most_common(5))}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="routelab")
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a routelab event log")
    inspect_parser.add_argument("path")

    args = parser.parse_args()

    if args.command == "inspect":
        return inspect_log(args.path)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
