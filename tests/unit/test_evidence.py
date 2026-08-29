from ghoststate.diff import diff_snapshots
from ghoststate.evidence import EvidenceStatus, build_hypotheses, mark_experiment_result
from ghoststate.schema import Snapshot


def _snap(execution_id: str, **sections) -> Snapshot:
    return Snapshot(
        schema_version="1.0", execution_id=execution_id, timestamp="t", label="", **sections
    )


def test_no_changes_produces_no_hypotheses():
    a = _snap("a", system={"os": "Linux"})
    b = _snap("b", system={"os": "Linux"})
    result = diff_snapshots(a, b)
    assert build_hypotheses(result) == []


def test_every_hypothesis_has_nonempty_evidence():
    a = _snap("a", network={"ipv6_loopback_bind": False}, git={"commit": "aaa"})
    b = _snap("b", network={"ipv6_loopback_bind": True}, git={"commit": "bbb"})
    result = diff_snapshots(a, b)
    hypotheses = build_hypotheses(result)
    assert hypotheses
    for h in hypotheses:
        assert len(h.evidence) > 0


def test_hypotheses_are_ranked_by_descending_confidence():
    a = _snap(
        "a",
        network={"ipv6_loopback_bind": False, "localhost_resolves_aaaa": False},
        dependencies={"python": {"packages": {"requests": "2.28.0"}}},
    )
    b = _snap(
        "b",
        network={"ipv6_loopback_bind": True, "localhost_resolves_aaaa": True},
        dependencies={"python": {"packages": {"requests": "2.31.0"}}},
    )
    result = diff_snapshots(a, b)
    hypotheses = build_hypotheses(result)
    percents = [h.confidence_percent for h in hypotheses]
    assert percents == sorted(percents, reverse=True)
    assert hypotheses[0].section == "network"  # two HIGH facts should outrank one LOW fact


def test_confidence_never_reaches_100_percent():
    # even a large number of correlated HIGH/CRITICAL facts must stay below 100:
    # correlation is never treated as absolute certainty.
    a = _snap(
        "a",
        network={"ipv6_loopback_bind": False, "localhost_resolves_aaaa": False, "localhost_resolves_a": False},
        git={"commit": "aaa"},
        containers={"running_in_container": False},
    )
    b = _snap(
        "b",
        network={"ipv6_loopback_bind": True, "localhost_resolves_aaaa": True, "localhost_resolves_a": True},
        git={"commit": "bbb"},
        containers={"running_in_container": True},
    )
    result = diff_snapshots(a, b)
    hypotheses = build_hypotheses(result)
    assert all(h.confidence_percent < 100 for h in hypotheses)


def test_language_defaults_to_proposed_never_confirmed():
    a = _snap("a", git={"commit": "aaa"})
    b = _snap("b", git={"commit": "bbb"})
    result = diff_snapshots(a, b)
    (hypothesis,) = build_hypotheses(result)
    assert hypothesis.status == EvidenceStatus.PROPOSED
    assert "confirm" not in hypothesis.language.lower()


def test_mark_experiment_result_is_the_only_path_to_confirmed_language():
    a = _snap("a", git={"commit": "aaa"})
    b = _snap("b", git={"commit": "bbb"})
    result = diff_snapshots(a, b)
    (hypothesis,) = build_hypotheses(result)

    mark_experiment_result(hypothesis, supports=True)
    assert hypothesis.status == EvidenceStatus.SUPPORTED_BY_EXPERIMENT
    assert hypothesis.language == "confirmed by experiment"


def test_mark_experiment_result_refuted_never_says_confirmed():
    a = _snap("a", git={"commit": "aaa"})
    b = _snap("b", git={"commit": "bbb"})
    result = diff_snapshots(a, b)
    (hypothesis,) = build_hypotheses(result)

    mark_experiment_result(hypothesis, supports=False)
    assert hypothesis.status == EvidenceStatus.REFUTED_BY_EXPERIMENT
    assert "confirm" not in hypothesis.language.lower()
