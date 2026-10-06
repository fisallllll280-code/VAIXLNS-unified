"""SLSA/in-toto-shaped local artifact attestation.

The output is intentionally UNSIGNED unless an external signing service is
provided. Shape compatibility is not an assertion of trusted provenance.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Tuple


def _stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return sha256(_stable(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Subject:
    name: str
    digest: Mapping[str, str]


@dataclass(frozen=True)
class Material:
    uri: str
    digest: Mapping[str, str]


@dataclass(frozen=True)
class BuildAttestation:
    statement_type: str
    subject: Tuple[Subject, ...]
    predicate_type: str
    predicate: Mapping[str, Any]
    attestation_digest: str
    signature_status: str = "UNSIGNED"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_attestation(
    *,
    subject_name: str,
    subject_digest: str,
    builder_id: str,
    build_type: str,
    materials: Tuple[Material, ...] = (),
    invocation: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> BuildAttestation:
    subject = Subject(subject_name, {"sha256": subject_digest})
    predicate = {
        "buildDefinition": {
            "buildType": build_type,
            "externalParameters": dict(invocation or {}),
            "internalParameters": {},
            "resolvedDependencies": [
                {"uri": material.uri, "digest": dict(material.digest)}
                for material in materials
            ],
        },
        "runDetails": {
            "builder": {"id": builder_id},
            "metadata": dict(metadata or {}),
            "byproducts": [],
            "startedOn": datetime.now(timezone.utc).isoformat(),
        },
    }
    body = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [asdict(subject)],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": predicate,
    }
    return BuildAttestation(
        statement_type=body["_type"],
        subject=(subject,),
        predicate_type=body["predicateType"],
        predicate=predicate,
        attestation_digest=_digest(body),
    )
