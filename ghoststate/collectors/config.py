"""Configuration-metadata collector.

Collects environment-variable *presence*, never values, by delegating
every decision to `ghoststate.redaction`. This module intentionally does
not accept an allowlist of "safe" variables to leak values for — the
policy is collect metadata, not secrets, with no per-variable override.
"""

from __future__ import annotations

import os
from typing import Any

from ..redaction import redact_env


def collect_configuration_metadata(env: dict[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ) if env is None else dict(env)
    redacted = redact_env(source)
    return {
        "variable_count": len(redacted),
        "variables": redacted,
    }
