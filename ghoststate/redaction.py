"""Redaction policy: collect metadata, never secrets.

This module is the single choke point every collector must go through
before an environment-variable-shaped value leaves the process. The
policy is intentionally conservative: a variable is treated as sensitive
unless it is provably not, never the other way around.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

# Name patterns that mark a variable as sensitive regardless of its value.
# Matched case-insensitively against the *name* only.
_SENSITIVE_NAME_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"secret",
        r"token",
        r"password",
        r"passwd",
        r"api[_-]?key",
        r"private[_-]?key",
        r"access[_-]?key",
        r"auth",
        r"credential",
        r"cookie",
        r"session[_-]?id",
        r"client[_-]?secret",
        r"encryption[_-]?key",
        r"^aws_",
        r"connection[_-]?string",
        r"dsn$",
        r"_url$",  # DATABASE_URL, REDIS_URL etc. often embed credentials
    ]
]

# Value patterns that mark a variable as sensitive even if the name looks
# innocuous (e.g. a variable literally named "X" holding a live API key).
_SENSITIVE_VALUE_PATTERNS = [
    re.compile(pattern)
    for pattern in [
        r"sk-[A-Za-z0-9]{20,}",  # OpenAI/Anthropic-style secret keys
        r"sk_live_[A-Za-z0-9]{10,}",  # Stripe live secret key
        r"AKIA[0-9A-Z]{16}",  # AWS access key id
        r"ghp_[A-Za-z0-9]{30,}",  # GitHub personal access token
        r"xox[baprs]-[A-Za-z0-9-]{10,}",  # Slack token
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",  # JWT
    ]
]


class VariableClass(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"


@dataclass(frozen=True)
class RedactionDecision:
    name: str
    classification: VariableClass
    sensitive: bool
    reason: str


def is_sensitive_name(name: str) -> bool:
    return any(pattern.search(name) for pattern in _SENSITIVE_NAME_PATTERNS)


def is_sensitive_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS)


def classify_variable(name: str, value: str | None) -> RedactionDecision:
    """Classify a single environment variable for safe collection.

    The returned decision NEVER carries the raw value. Callers must not
    attempt to recover it from this module — that is by design, not an
    oversight.
    """
    if value is None:
        return RedactionDecision(
            name=name,
            classification=VariableClass.ABSENT,
            sensitive=False,
            reason="variable not set",
        )

    if is_sensitive_name(name):
        return RedactionDecision(
            name=name,
            classification=VariableClass.PRESENT,
            sensitive=True,
            reason="name matches known secret pattern",
        )

    if is_sensitive_value(value):
        return RedactionDecision(
            name=name,
            classification=VariableClass.PRESENT,
            sensitive=True,
            reason="value matches known secret-shaped pattern",
        )

    return RedactionDecision(
        name=name,
        classification=VariableClass.PRESENT,
        sensitive=False,
        reason="no secret pattern matched",
    )


def redact_env(env: dict[str, str]) -> dict[str, str]:
    """Turn a raw environment mapping into a collection-safe view.

    Every value is discarded. Only presence/absence survives. This
    function is deliberately incapable of returning a secret: it never
    reads `value` into the output, only into pattern matching used to
    decide metadata about it.
    """
    result: dict[str, str] = {}
    for name, value in env.items():
        decision = classify_variable(name, value)
        result[name] = decision.classification.value
    return result
