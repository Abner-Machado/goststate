from ghoststate.schema import Snapshot, is_schema_compatible, new_execution_id


def _make_snapshot(**overrides) -> Snapshot:
    base = dict(
        schema_version="1.0",
        execution_id="abc123",
        timestamp="2026-01-01T00:00:00+00:00",
        label="test",
        system={"os": "Linux"},
    )
    base.update(overrides)
    return Snapshot(**base)


def test_round_trip_json_is_lossless():
    snap = _make_snapshot(network={"ipv6_loopback_bind": True})
    restored = Snapshot.from_json(snap.to_json())
    assert restored.to_dict() == snap.to_dict()


def test_to_json_is_deterministic_regardless_of_dict_order():
    a = _make_snapshot(system={"os": "Linux", "kernel": "6.8"})
    b = _make_snapshot(system={"kernel": "6.8", "os": "Linux"})
    assert a.to_json() == b.to_json()


def test_from_dict_ignores_unknown_fields_forward_compat():
    data = _make_snapshot().to_dict()
    data["some_future_field"] = "value from a newer schema"
    restored = Snapshot.from_dict(data)
    assert restored.execution_id == "abc123"


def test_sections_excludes_identity_fields():
    snap = _make_snapshot()
    sections = snap.sections()
    assert "execution_id" not in sections
    assert "timestamp" not in sections
    assert "system" in sections


def test_new_execution_id_is_hex_and_unique():
    a, b = new_execution_id(), new_execution_id()
    assert a != b
    assert all(c in "0123456789abcdef" for c in a)


def test_schema_compatibility_same_major():
    assert is_schema_compatible("1.0")
    assert is_schema_compatible("1.7")


def test_schema_compatibility_different_major():
    assert not is_schema_compatible("2.0")
