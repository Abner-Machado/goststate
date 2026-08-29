#!/usr/bin/env python3
"""Toy target application used by `ghoststate demo`.

This file has NO dependency on the ghoststate package — it represents
"the user's application" being investigated, exactly as GhostState would
be pointed at any real service. It reads `behavior.json` from its
current working directory and starts a cache backend. Only the "valid"
backend is implemented; anything else is a startup failure — a small,
honest stand-in for "worked yesterday, broke today because something in
the checked-out state changed."
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SUPPORTED_BACKENDS = {"valid"}


def main() -> int:
    config_path = Path("behavior.json")
    if not config_path.exists():
        print("STARTUP FAILED: behavior.json not found in current directory", file=sys.stderr)
        return 1

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"STARTUP FAILED: invalid behavior.json: {exc}", file=sys.stderr)
        return 1

    backend = config.get("cache_backend")
    if backend not in SUPPORTED_BACKENDS:
        print(f"STARTUP FAILED: unsupported cache_backend {backend!r}", file=sys.stderr)
        return 1

    print(f"STARTED OK: cache_backend={backend}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
