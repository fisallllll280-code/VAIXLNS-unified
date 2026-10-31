"""VX ONE system-image manifest and fail-closed preflight loader.

This module validates declared OS/runtime artifacts and produces a plan.
It deliberately does not download, write boot sectors, modify EFI variables,
install operating systems, or reboot a machine.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


class LoaderError(ValueError):
    """Raised when a manifest or artifact violates the loader contract."""


_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ALLOWED_KINDS = {"os_image", "installer", "runtime_bundle", "recovery_image"}
_ALLOWED_FIRMWARE = {"uefi", "bios", "either"}
_ALLOWED_HOSTS = {
    "download.microsoft.com",
    "www.microsoft.com",
    "ubuntu.com",
    "releases.ubuntu.com",
    "cdimage.ubuntu.com",
    "debian.org",
    "cdimage.debian.org",
    "getfedora.org",
    "download.fedoraproject.org",
    "rockylinux.org",
    "almalinux.org",
}


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    kind: str
    uri: str
    sha256: str
    size_bytes: int
    signature_algorithm: str
    signer_id: str
    signature_value: str


@dataclass(frozen=True)
class LoaderPlan:
    system_id: str
    version: str
    artifact_id: str
    status: str
    checks: dict[str, bool]
    reasons: tuple[str, ...]
    actions: tuple[str, ...]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LoaderError(message)


def validate_manifest(
    data: dict[str, Any],
    *,
    allowed_hosts: set[str] | None = None,
) -> tuple[Artifact, ...]:
    """Validate the strict v1 manifest contract without network or disk writes."""
    _require(isinstance(data, dict), "manifest must be a JSON object")
    _require(data.get("schema_version") == "1.0", "unsupported schema_version")

    system_id = data.get("system_id")
    _require(isinstance(system_id, str) and bool(_ID.fullmatch(system_id)),
             "system_id is invalid")
    _require(isinstance(data.get("version"), str) and bool(data["version"].strip()),
             "version is required")
    _require(isinstance(data.get("display_name"), str) and bool(data["display_name"].strip()),
             "display_name is required")

    target = data.get("target")
    _require(isinstance(target, dict), "target must be an object")
    _require(isinstance(target.get("os"), str) and bool(target["os"].strip()),
             "target.os is required")
    _require(isinstance(target.get("architectures"), list) and target["architectures"],
             "target.architectures must be a non-empty list")
    _require(all(isinstance(x, str) and x.strip() for x in target["architectures"]),
             "target.architectures contains an invalid value")
    firmware = target.get("firmware")
    _require(isinstance(firmware, list) and firmware, "target.firmware must be a non-empty list")
    _require(all(isinstance(x, str) for x in firmware),
             "target.firmware contains an invalid value")
    _require(set(firmware).issubset(_ALLOWED_FIRMWARE), "unsupported firmware target")

    policy = data.get("install_policy")
    _require(isinstance(policy, dict), "install_policy must be an object")
    _require(policy.get("mode") == "plan_only", "v1 only supports plan_only mode")
    _require(policy.get("require_human_approval") is True,
             "human approval must be required")
    _require(policy.get("network_enabled") is False,
             "network access must remain disabled in v1")
    _require(policy.get("execute_install") is False,
             "install execution must remain disabled in v1")

    entries = data.get("artifacts")
    _require(isinstance(entries, list) and entries, "artifacts must be a non-empty list")
    hosts = _ALLOWED_HOSTS if allowed_hosts is None else {h.lower() for h in allowed_hosts}
    seen: set[str] = set()
    artifacts: list[Artifact] = []

    for entry in entries:
        _require(isinstance(entry, dict), "artifact entry must be an object")
        artifact_id = entry.get("artifact_id")
        _require(isinstance(artifact_id, str) and bool(_ID.fullmatch(artifact_id)),
                 "artifact_id is invalid")
        _require(artifact_id not in seen, "duplicate artifact_id")
        seen.add(artifact_id)

        kind = entry.get("kind")
        _require(isinstance(kind, str) and kind in _ALLOWED_KINDS,
                 "unsupported artifact kind")
        uri = entry.get("uri")
        _require(isinstance(uri, str), "artifact uri is required")
        parsed = urlparse(uri)
        _require(parsed.scheme == "https" and parsed.hostname is not None,
                 "artifact uri must use HTTPS")
        _require(
            parsed.username is None and parsed.password is None
            and not parsed.fragment and not parsed.query,
            "artifact uri must not contain credentials, query strings, or fragments",
        )
        _require(parsed.hostname.lower() in hosts, "artifact host is not allowlisted")

        digest = entry.get("sha256")
        _require(isinstance(digest, str) and bool(_SHA256.fullmatch(digest)),
                 "artifact sha256 must be 64 lowercase hexadecimal characters")
        size_bytes = entry.get("size_bytes")
        _require(isinstance(size_bytes, int) and not isinstance(size_bytes, bool)
                 and 0 < size_bytes <= 100 * 1024 * 1024 * 1024,
                 "artifact size_bytes is outside the v1 limit")

        signature = entry.get("signature")
        _require(isinstance(signature, dict), "detached signature is required")
        _require(signature.get("algorithm") == "ed25519",
                 "only Ed25519 detached signatures are supported")
        signer_id = signature.get("signer_id")
        signature_value = signature.get("value")
        _require(isinstance(signer_id, str) and bool(signer_id.strip()),
                 "signature signer_id is required")
        _require(isinstance(signature_value, str) and bool(signature_value.strip()),
                 "signature value is required")

        artifacts.append(Artifact(
            artifact_id=artifact_id,
            kind=kind,
            uri=uri,
            sha256=digest,
            size_bytes=size_bytes,
            signature_algorithm="ed25519",
            signer_id=signer_id,
            signature_value=signature_value,
        ))

    return tuple(artifacts)


def load_manifest(path: str | Path) -> tuple[dict[str, Any], tuple[Artifact, ...]]:
    """Read a local manifest file. This function performs no network access."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LoaderError(f"cannot read manifest: {exc}") from exc
    return data, validate_manifest(data)


class VXSystemLoader:
    """Fail-closed artifact verifier and plan generator.

    signature_verifier is an injected, independently maintained trust adapter.
    Without it, the loader can calculate a digest but cannot claim authenticity.
    """

    def __init__(
        self,
        signature_verifier: Callable[[bytes, Artifact], bool] | None = None,
    ) -> None:
        self._signature_verifier = signature_verifier

    def inspect(
        self,
        manifest: dict[str, Any],
        artifact_id: str,
        payload: bytes,
    ) -> LoaderPlan:
        artifacts = validate_manifest(manifest)
        artifact = next((item for item in artifacts if item.artifact_id == artifact_id), None)
        if artifact is None:
            raise LoaderError("artifact_id is not declared by this manifest")
        if not isinstance(payload, bytes):
            raise LoaderError("payload must be bytes")

        digest_ok = hashlib.sha256(payload).hexdigest() == artifact.sha256
        size_ok = len(payload) == artifact.size_bytes
        signature_ok = False
        if self._signature_verifier is not None and digest_ok and size_ok:
            try:
                signature_ok = bool(self._signature_verifier(payload, artifact))
            except Exception:
                signature_ok = False

        checks = {
            "manifest_valid": True,
            "source_allowlisted": True,
            "size_matches": size_ok,
            "sha256_matches": digest_ok,
            "signature_verified": signature_ok,
            "human_approval_present": False,
            "install_execution_disabled": True,
        }
        reasons: list[str] = []
        if not size_ok:
            reasons.append("ARTIFACT_SIZE_MISMATCH")
        if not digest_ok:
            reasons.append("ARTIFACT_HASH_MISMATCH")
        if not signature_ok:
            reasons.append("SIGNATURE_NOT_VERIFIED")
        reasons.append("HUMAN_APPROVAL_REQUIRED")
        reasons.append("INSTALL_EXECUTION_DISABLED")

        return LoaderPlan(
            system_id=manifest["system_id"],
            version=manifest["version"],
            artifact_id=artifact.artifact_id,
            status="VERIFIED_FOR_REVIEW" if size_ok and digest_ok and signature_ok else "BLOCKED",
            checks=checks,
            reasons=tuple(reasons),
            actions=("REVIEW_PLAN", "OBTAIN_EXPLICIT_APPROVAL"),
        )

    @staticmethod
    def install(*_args: Any, **_kwargs: Any) -> None:
        """Installation is intentionally unavailable in v1."""
        raise LoaderError(
            "INSTALL_EXECUTION_DISABLED: v1 supports manifest validation and preflight only"
        )
