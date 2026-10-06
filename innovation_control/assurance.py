"""Ω Assurance V1: verification diversity and proof freshness.
These controls strengthen the promotion boundary without claiming formal proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class Freshness(str, Enum):
    FRESH = "FRESH"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class VerifierProfile:
    verifier_id: str
    implementation_id: str
    model_family: str
    evidence_sources: tuple[str, ...]
    algorithm_family: str

    def signature(self) -> tuple[str, ...]:
        return (
            self.implementation_id,
            self.model_family,
            *tuple(sorted(self.evidence_sources)),
            self.algorithm_family,
        )


@dataclass(frozen=True)
class DiversityResult:
    score: float
    threshold: float
    passed: bool
    overlaps: Mapping[str, float]


class VerificationDiversity:
    """Measure independence by shared implementation/model/evidence mechanisms."""

    def assess(self, profiles: Iterable[VerifierProfile], threshold: float = 0.5) -> DiversityResult:
        items = tuple(profiles)
        if len(items) < 3:
            raise ValueError("VERIFIER_DIVERSITY_REQUIRES_THREE_PROFILES")
        overlaps: dict[str, float] = {}
        similarities: list[float] = []
        for i, left in enumerate(items):
            left_sig = set(left.signature())
            for right in items[i + 1:]:
                right_sig = set(right.signature())
                union = left_sig | right_sig
                similarity = len(left_sig & right_sig) / len(union) if union else 1.0
                key = f"{left.verifier_id}:{right.verifier_id}"
                overlaps[key] = similarity
                similarities.append(similarity)
        score = 1.0 - (sum(similarities) / len(similarities))
        return DiversityResult(score, threshold, score >= threshold, overlaps)


@dataclass(frozen=True)
class ProofValidity:
    evidence_fingerprint: str
    issued_epoch: int
    expires_epoch: int
    dependency_fingerprint: str
    environment_fingerprint: str


class ProofFreshness:
    """A proof is scoped to dependencies/environment and expires by policy."""

    def evaluate(
        self,
        validity: ProofValidity,
        *,
        now_epoch: int,
        dependency_fingerprint: str,
        environment_fingerprint: str,
    ) -> Freshness:
        if dependency_fingerprint != validity.dependency_fingerprint:
            return Freshness.INVALIDATED
        if environment_fingerprint != validity.environment_fingerprint:
            return Freshness.INVALIDATED
        if now_epoch < validity.issued_epoch:
            return Freshness.INVALIDATED
        if now_epoch >= validity.expires_epoch:
            return Freshness.EXPIRED
        return Freshness.FRESH

    @staticmethod
    def issue(*, evidence_fingerprint: str, issued_epoch: int, ttl_epochs: int, dependency_fingerprint: str, environment_fingerprint: str) -> ProofValidity:
        if ttl_epochs <= 0:
            raise ValueError("PROOF_TTL_MUST_BE_POSITIVE")
        return ProofValidity(
            evidence_fingerprint=evidence_fingerprint,
            issued_epoch=issued_epoch,
            expires_epoch=issued_epoch + ttl_epochs,
            dependency_fingerprint=dependency_fingerprint,
            environment_fingerprint=environment_fingerprint,
        )


__all__ = ["DiversityResult", "Freshness", "ProofFreshness", "ProofValidity", "VerifierProfile", "VerificationDiversity"]
