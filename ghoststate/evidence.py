"""Evidence Engine: turns diff facts into hypotheses with disciplined language.

Design contract (see docs/ARCHITECTURE.md for the full rationale):
  - Every hypothesis is backed by a non-empty list of concrete PropertyDiff
    facts. There is no code path that can produce a hypothesis with zero
    evidence.
  - Confidence is a *documented heuristic*, never a statistical estimate.
    The formula lives in `_score_group` below, in plain sight, precisely
    so nobody can accuse this of "inventing a percentage."
  - Epistemic language escalates only through `EvidenceStatus`: a
    hypothesis is PROPOSED until a real Experiment records a verdict
    against it. Only then can it become SUPPORTED_BY_EXPERIMENT — never
    a bare "confirmed" produced by the diff/evidence layer alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .diff import ChangeStatus, DiffResult, PropertyDiff, Relevance

_RELEVANCE_WEIGHT = {
    Relevance.NONE: 0,
    Relevance.LOW: 1,
    Relevance.MEDIUM: 3,
    Relevance.HIGH: 7,
    Relevance.CRITICAL: 12,
}

_CORRELATION_BONUS = 5  # applied once if >=2 HIGH-or-above facts co-occur in a group
_SATURATION_CONSTANT = 10  # shapes the score->percent curve; see _score_to_percent


class EvidenceStatus(str, Enum):
    PROPOSED = "PROPOSED"
    SUPPORTED_BY_EXPERIMENT = "SUPPORTED_BY_EXPERIMENT"
    REFUTED_BY_EXPERIMENT = "REFUTED_BY_EXPERIMENT"


@dataclass
class Hypothesis:
    id: str
    section: str
    summary: str
    evidence: list[PropertyDiff]
    confidence_percent: int
    confidence_bucket: str  # LOW / MEDIUM / HIGH
    status: EvidenceStatus = EvidenceStatus.PROPOSED
    language: str = "suggests"  # observed / correlated with / consistent with / suggests / confirmed by experiment

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "section": self.section,
            "summary": self.summary,
            "language": self.language,
            "status": self.status.value,
            "confidence_percent": self.confidence_percent,
            "confidence_bucket": self.confidence_bucket,
            "confidence_basis": "heuristic (see docs/ARCHITECTURE.md#confidence), not a statistical estimate",
            "evidence": [d.to_dict() for d in self.evidence],
        }


def _score_group(facts: list[PropertyDiff]) -> int:
    score = sum(_RELEVANCE_WEIGHT[f.relevance] for f in facts)
    high_or_above = sum(1 for f in facts if f.relevance in (Relevance.HIGH, Relevance.CRITICAL))
    if high_or_above >= 2:
        score += _CORRELATION_BONUS
    return score


def _score_to_percent(score: int) -> int:
    # Saturating curve bounded in (0, 100): a lone LOW fact scores low,
    # a handful of HIGH/CRITICAL correlated facts approach but never
    # claim 100 — GhostState never asserts certainty from correlation
    # alone (see docs/THREAT_MODEL.md, "false causality").
    if score <= 0:
        return 0
    percent = 100 * score / (score + _SATURATION_CONSTANT)
    return min(round(percent), 96)


def _bucket_for(percent: int) -> str:
    if percent >= 67:
        return "HIGH"
    if percent >= 34:
        return "MEDIUM"
    return "LOW"


def _language_for(facts: list[PropertyDiff]) -> str:
    max_relevance = max((f.relevance for f in facts), default=Relevance.NONE)
    if max_relevance == Relevance.CRITICAL:
        return "strongly correlated with"
    if max_relevance == Relevance.HIGH:
        return "correlated with"
    if max_relevance == Relevance.MEDIUM:
        return "consistent with"
    return "suggests"


def build_hypotheses(diff_result: DiffResult, group_by: str = "section") -> list[Hypothesis]:
    """Group changed facts by top-level snapshot section and score each group.

    Grouping by section is the entire MVP correlation model: it is
    intentionally simple and fully described here rather than hidden
    behind unexplained clustering. Cross-section correlation is a
    documented roadmap item, not something this function pretends to do.
    """
    changed = [d for d in diff_result.diffs if d.status != ChangeStatus.UNCHANGED]
    if not changed:
        return []

    groups: dict[str, list[PropertyDiff]] = {}
    for fact in changed:
        section = fact.path.split(".", 1)[0]
        groups.setdefault(section, []).append(fact)

    hypotheses: list[Hypothesis] = []
    for section, facts in groups.items():
        score = _score_group(facts)
        percent = _score_to_percent(score)
        top_fact = max(facts, key=lambda f: _RELEVANCE_WEIGHT[f.relevance])
        hypotheses.append(
            Hypothesis(
                id=f"hyp-{section}",
                section=section,
                summary=f"{section} changed ({top_fact.path}: {top_fact.before!r} -> {top_fact.after!r})",
                evidence=sorted(facts, key=lambda f: -_RELEVANCE_WEIGHT[f.relevance]),
                confidence_percent=percent,
                confidence_bucket=_bucket_for(percent),
                language=_language_for(facts),
            )
        )

    hypotheses.sort(key=lambda h: -h.confidence_percent)
    return hypotheses


def mark_experiment_result(hypothesis: Hypothesis, supports: bool) -> Hypothesis:
    """The only legitimate way a hypothesis's language may reach 'confirmed'."""
    hypothesis.status = (
        EvidenceStatus.SUPPORTED_BY_EXPERIMENT if supports else EvidenceStatus.REFUTED_BY_EXPERIMENT
    )
    hypothesis.language = "confirmed by experiment" if supports else "refuted by experiment"
    return hypothesis
