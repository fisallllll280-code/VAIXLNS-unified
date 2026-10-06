"""Governed architecture change proposal boundary.

A proposal can be generated deterministically, but canonical promotion still
requires explicit authority plus verification, replay, and declared checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Tuple


def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True)
class ChangeProposal:
    candidate_id: str
    base_branch: str
    proposed_branch: str
    required_checks: Tuple[str, ...]
    impact_nodes: Tuple[str, ...]
    verified: bool
    independent: bool
    replayable: bool
    digest: str


@dataclass(frozen=True)
class ChangeDecision:
    accepted: bool
    stage: str
    reasons: Tuple[str, ...]
    digest: str


def create_proposal(
    *,
    candidate_id: str,
    base_branch: str,
    proposed_branch: str,
    required_checks: Iterable[str],
    impact_nodes: Iterable[str],
    verified: bool,
    independent: bool,
    replayable: bool,
) -> ChangeProposal:
    checks = tuple(dict.fromkeys(required_checks))
    nodes = tuple(sorted(set(impact_nodes)))
    body = {
        "candidate_id": candidate_id,
        "base_branch": base_branch,
        "proposed_branch": proposed_branch,
        "required_checks": checks,
        "impact_nodes": nodes,
        "verified": verified,
        "independent": independent,
        "replayable": replayable,
    }
    return ChangeProposal(**body, digest=_digest(body))


def admit_proposal(proposal: ChangeProposal, explicit_authority: bool) -> ChangeDecision:
    reasons = []
    if not proposal.verified:
        reasons.append("VERIFICATION_REQUIRED")
    if not proposal.independent:
        reasons.append("INDEPENDENT_VERIFICATION_REQUIRED")
    if not proposal.replayable:
        reasons.append("REPLAY_REQUIRED")
    if not proposal.required_checks:
        reasons.append("CHECKS_REQUIRED")
    if proposal.base_branch == proposal.proposed_branch:
        reasons.append("SEPARATE_CHANGE_BRANCH_REQUIRED")
    if not explicit_authority:
        reasons.append("EXPLICIT_AUTHORITY_REQUIRED")
    accepted = not reasons
    return ChangeDecision(
        accepted=accepted,
        stage="ADMISSIBLE" if accepted else "REJECTED",
        reasons=tuple(reasons),
        digest=_digest({"proposal": proposal.digest, "accepted": accepted, "reasons": reasons}),
    )
