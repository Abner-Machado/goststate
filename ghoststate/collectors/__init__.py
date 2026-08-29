"""Collectors observe one dimension of the execution environment each.

Every collector function has the signature `() -> dict[str, Any]` and
must never raise: a collector that cannot observe something records why
under a `"_warning"` key instead of crashing the whole capture. This is
what lets `ghoststate capture` degrade gracefully on unsupported
platforms instead of producing an empty, useless snapshot.
"""
