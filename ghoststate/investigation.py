"""Investigation Engine: orchestrates diff + evidence into a ranked report.

This module is where "insufficient evidence" is treated as a legitimate,
first-class outcome (see section 25 of the product brief / README
"What GhostState cannot know") rather than something the system tries to
paper over with a guess.
"""

from __future__ import annotations

from dataclasses import dataclass

from .diff import DiffResult, Relevance, diff_snapshots
from .evidence import Hypothesis, build_hypotheses
from .schema import Snapshot, is_schema_compatible

_MIN_RELEVANCE_FOR_CANDIDATE = {Relevance.MEDIUM, Relevance.HIGH, Relevance.CRITICAL}


@dataclass
class InvestigationReport:
    diff: DiffResult
    hypotheses: list[Hypothesis]
    sufficient_evidence: bool
    note: str

    def to_dict(self) -> dict:
        return {
            "schema_compatible": self.diff.schema_compatible,
            "sufficient_evidence": self.sufficient_evidence,
            "note": self.note,
            "summary_counts": self.diff.summary_counts(),
            "hypotheses": [h.to_dict() for h in self.hypotheses],
        }


def investigate(before: Snapshot, after: Snapshot) -> InvestigationReport:
    if not is_schema_compatible(before.schema_version) or not is_schema_compatible(after.schema_version):
        empty = diff_snapshots(before, after)
        return InvestigationReport(
            diff=empty,
            hypotheses=[],
            sufficient_evidence=False,
            note=(
                f"Snapshots use incompatible schema versions "
                f"({before.schema_version} vs {after.schema_version}). "
                "Refusing to compare — see docs/ARCHITECTURE.md#schema-versioning."
            ),
        )

    diff_result = diff_snapshots(before, after)
    hypotheses = build_hypotheses(diff_result)

    has_candidate = any(
        any(fact.relevance in _MIN_RELEVANCE_FOR_CANDIDATE for fact in h.evidence) for h in hypotheses
    )

    if not diff_result.changed():
        return InvestigationReport(
            diff=diff_result,
            hypotheses=[],
            sufficient_evidence=False,
            note=(
                "No differences detected between the two snapshots. GhostState cannot "
                "explain a failure it did not observe a change for."
            ),
        )

    if not has_candidate:
        return InvestigationReport(
            diff=diff_result,
            hypotheses=hypotheses,
            sufficient_evidence=False,
            note=(
                "Differences were found, but none reach MEDIUM relevance or above. "
                "Insufficient evidence for a confident hypothesis — this is reported "
                "honestly rather than inflated."
            ),
        )

    return InvestigationReport(
        diff=diff_result,
        hypotheses=hypotheses,
        sufficient_evidence=True,
        note=f"{len(hypotheses)} candidate cause(s) ranked by heuristic confidence.",
    )
