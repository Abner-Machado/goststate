from ghoststate.investigation import investigate
from ghoststate.schema import Snapshot


def _snap(execution_id: str, schema_version: str = "1.0", **sections) -> Snapshot:
    return Snapshot(
        schema_version=schema_version, execution_id=execution_id, timestamp="t", label="", **sections
    )


def test_no_differences_is_reported_as_insufficient_evidence_not_a_guess():
    a = _snap("a", system={"os": "Linux"})
    b = _snap("b", system={"os": "Linux"})
    report = investigate(a, b)
    assert report.sufficient_evidence is False
    assert report.hypotheses == []


def test_only_low_relevance_changes_are_insufficient_evidence():
    a = _snap("a", dependencies={"python": {"packages": {"requests": "2.28.0"}}})
    b = _snap("b", dependencies={"python": {"packages": {"requests": "2.28.1"}}})
    report = investigate(a, b)
    assert report.sufficient_evidence is False
    assert "Insufficient" in report.note or "insufficient" in report.note


def test_high_relevance_change_yields_sufficient_evidence():
    a = _snap("a", git={"commit": "aaa"})
    b = _snap("b", git={"commit": "bbb"})
    report = investigate(a, b)
    assert report.sufficient_evidence is True
    assert report.hypotheses


def test_incompatible_schema_versions_refuse_to_compare():
    a = _snap("a", schema_version="1.0", system={"os": "Linux"})
    b = _snap("b", schema_version="2.0", system={"os": "Linux"})
    report = investigate(a, b)
    assert report.sufficient_evidence is False
    assert "incompatible" in report.note.lower()
    assert report.hypotheses == []
