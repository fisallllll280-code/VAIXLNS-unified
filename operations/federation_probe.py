"""Read-only, fail-closed health probes for explicitly configured federation endpoints."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse, unquote
from urllib.request import HTTPRedirectHandler, Request, build_opener

DEFAULT_POLICY = Path(__file__).resolve().parents[1] / "config" / "federation-probe-policy.v1.json"
MAX_RESPONSE_BYTES = 65_536
DEFAULT_TIMEOUT_SECONDS = 3.0
_TRUE = {"1", "true", "yes", "on"}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _enabled(env: Mapping[str, str], key: str | None) -> bool:
    return bool(key and env.get(key, "").strip().lower() in _TRUE)


def _safe_path(path: str) -> bool:
    if not path.startswith("/") or path.startswith("//") or any(c in path for c in ("?", "#", "\\", "\r", "\n")):
        return False
    decoded_segments = unquote(path).split("/")
    return all(segment not in {".", ".."} for segment in decoded_segments)


def _safe_url(raw: str) -> bool:
    try:
        parsed = urlparse(raw)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            return False
        if any(char.isspace() for char in raw):
            return False
        if parsed.scheme == "http":
            host = parsed.hostname.lower()
            loopback = host == "localhost"
            try:
                loopback = loopback or ipaddress.ip_address(host).is_loopback
            except ValueError:
                pass
            if not loopback:
                return False
        if not _safe_path(parsed.path or "/"):
            return False
        _ = parsed.port
        return True
    except (ValueError, UnicodeError):
        return False


def _resolve_endpoint(target: Mapping[str, Any], env: Mapping[str, str]) -> tuple[str | None, str | None]:
    url_env = target.get("url_env")
    if url_env:
        raw = env.get(str(url_env), "").strip()
        return (raw, None) if raw else (None, "ENDPOINT_NOT_CONFIGURED")

    base_env = target.get("base_url_env")
    if base_env:
        base = env.get(str(base_env), "").strip()
        if not base:
            return None, "ENDPOINT_NOT_CONFIGURED"
        base_parts = urlparse(base)
        if base_parts.query or base_parts.fragment or base_parts.username or base_parts.password:
            return None, "ENDPOINT_URL_INVALID"
        path_env = target.get("path_env")
        path = (env.get(str(path_env), "").strip() if path_env else "") or str(target.get("default_path", "/health"))
        if not _safe_path(path):
            return None, "HEALTH_PATH_INVALID"
        final = urlunparse((base_parts.scheme, base_parts.netloc, path, "", "", ""))
        return (final, None) if _safe_url(final) else (None, "ENDPOINT_URL_INVALID")
    return None, "ENDPOINT_CONFIGURATION_INVALID"


def _same_typed_value(actual: Any, expected: Any) -> bool:
    return type(actual) is type(expected) and actual == expected


def _result(
    system_id: str,
    state: str,
    reason: str,
    *,
    endpoint_configured: bool = False,
    http_status: int | None = None,
    observed_identity: str | None = None,
    identity_match: bool | None = None,
    health_match: bool | None = None,
    response_sha256: str | None = None,
    latency_ms: float | None = None,
) -> dict[str, Any]:
    return {
        "system_id": system_id,
        "state": state,
        "reason": reason,
        "endpoint_configured": endpoint_configured,
        "http_status": http_status,
        "observed_identity": observed_identity,
        "identity_match": identity_match,
        "health_match": health_match,
        "response_sha256": response_sha256,
        "latency_ms": latency_ms,
    }


def probe_target(
    target: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    opener: Any | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_response_bytes: int = MAX_RESPONSE_BYTES,
) -> dict[str, Any]:
    """Probe one target with GET only. No endpoint is called without explicit opt-in."""
    environment = os.environ if env is None else env
    system_id = str(target.get("system_id", "UNKNOWN_SYSTEM"))

    enabled_env = target.get("enabled_env")
    if not _enabled(environment, str(enabled_env) if enabled_env else None):
        return _result(system_id, "BLOCKED", "PROBE_NOT_ENABLED")

    expected_identity = target.get("expected_identity")
    expected_identity_env = target.get("expected_identity_env")
    if expected_identity_env:
        expected_identity = environment.get(str(expected_identity_env), "").strip()
    if not isinstance(expected_identity, str) or not expected_identity:
        return _result(system_id, "BLOCKED", "EXPECTED_SERVICE_IDENTITY_NOT_PINNED")

    url, error = _resolve_endpoint(target, environment)
    if error:
        state = "MISSING" if error == "ENDPOINT_NOT_CONFIGURED" else "BLOCKED"
        return _result(system_id, state, error)
    if not url or not _safe_url(url):
        return _result(system_id, "BLOCKED", "ENDPOINT_URL_INVALID", endpoint_configured=bool(url))

    timeout = min(max(float(timeout_seconds), 0.1), 10.0)
    max_bytes = min(max(int(max_response_bytes), 1), 1_000_000)
    headers = {"Accept": "application/json", "User-Agent": "VAIXLNS-Federation-Probe/1.0"}
    token_env = target.get("token_env")
    token = environment.get(str(token_env), "") if token_env else ""
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, headers=headers, method="GET")
    client = opener if opener is not None else build_opener(_NoRedirect())
    started = time.monotonic()
    try:
        response = client.open(request, timeout=timeout)
        try:
            status = int(response.getcode())
            body = response.read(max_bytes + 1)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
    except HTTPError as exc:
        elapsed = round((time.monotonic() - started) * 1000, 3)
        if 300 <= exc.code < 400:
            return _result(system_id, "BLOCKED", "REDIRECT_REFUSED",
                           endpoint_configured=True, http_status=int(exc.code), latency_ms=elapsed)
        return _result(system_id, "DEGRADED", "HTTP_ERROR",
                       endpoint_configured=True, http_status=int(exc.code), latency_ms=elapsed)
    except (URLError, TimeoutError, OSError, ValueError):
        elapsed = round((time.monotonic() - started) * 1000, 3)
        return _result(system_id, "UNKNOWN", "CONNECTIVITY_OR_RESPONSE_ERROR",
                       endpoint_configured=True, latency_ms=elapsed)

    elapsed = round((time.monotonic() - started) * 1000, 3)
    response_digest = hashlib.sha256(body).hexdigest()
    if 300 <= status < 400:
        return _result(system_id, "BLOCKED", "REDIRECT_REFUSED", endpoint_configured=True,
                       http_status=status, response_sha256=response_digest, latency_ms=elapsed)
    if not 200 <= status < 300:
        return _result(system_id, "DEGRADED", "HTTP_STATUS_NOT_OK", endpoint_configured=True,
                       http_status=status, response_sha256=response_digest, latency_ms=elapsed)
    if len(body) > max_bytes:
        return _result(system_id, "UNKNOWN", "RESPONSE_TOO_LARGE", endpoint_configured=True,
                       http_status=status, response_sha256=response_digest, latency_ms=elapsed)
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _result(system_id, "UNKNOWN", "HEALTH_RESPONSE_INVALID_JSON", endpoint_configured=True,
                       http_status=status, response_sha256=response_digest, latency_ms=elapsed)
    if not isinstance(payload, dict):
        return _result(system_id, "UNKNOWN", "HEALTH_RESPONSE_NOT_OBJECT", endpoint_configured=True,
                       http_status=status, response_sha256=response_digest, latency_ms=elapsed)

    identity_field = str(target.get("identity_field", "service"))
    observed_identity = payload.get(identity_field)
    identity_match = observed_identity == expected_identity
    if not identity_match:
        return _result(system_id, "BLOCKED", "SERVICE_IDENTITY_MISMATCH", endpoint_configured=True,
                       http_status=status,
                       observed_identity=observed_identity if isinstance(observed_identity, str) else None,
                       identity_match=False, response_sha256=response_digest, latency_ms=elapsed)
    health_field = str(target.get("health_field", "ok"))
    health_match = _same_typed_value(payload.get(health_field), target.get("healthy_value", True))
    if not health_match:
        return _result(system_id, "DEGRADED", "HEALTH_SIGNAL_NOT_READY", endpoint_configured=True,
                       http_status=status, observed_identity=observed_identity, identity_match=True,
                       health_match=False, response_sha256=response_digest, latency_ms=elapsed)
    return _result(system_id, "HEALTHY", "HTTP_HEALTH_AND_IDENTITY_MATCHED", endpoint_configured=True,
                   http_status=status, observed_identity=observed_identity, identity_match=True,
                   health_match=True, response_sha256=response_digest, latency_ms=elapsed)


def build_report(
    policy: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    opener: Any | None = None,
) -> dict[str, Any]:
    targets = policy.get("targets")
    if not isinstance(targets, list) or not targets or any(not isinstance(t, Mapping) for t in targets):
        raise ValueError("PROBE_POLICY_TARGETS_REQUIRED")
    environment = os.environ if env is None else env
    results = [
        probe_target(
            target, env=environment, opener=opener,
            timeout_seconds=float(policy.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
            max_response_bytes=int(policy.get("max_response_bytes", MAX_RESPONSE_BYTES)),
        )
        for target in targets
    ]
    healthy = sum(1 for item in results if item["state"] == "HEALTHY")
    report: dict[str, Any] = {
        "schema_version": str(policy.get("schema_version", "1.0")),
        "mode": "READ_ONLY_GET",
        "canonical": False,
        "overall": "HEALTHY" if healthy == len(results) else "BLOCKED",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "target_count": len(results),
        "healthy_count": healthy,
        "targets": results,
        "policy_sha256": sha256_json(dict(policy)),
        "safety": {
            "no_mutations": True,
            "no_redirects": True,
            "no_endpoint_or_token_echo": True,
        },
    }
    report["report_sha256"] = sha256_json(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict", action="store_true",
                        help="return exit code 2 unless every configured system is HEALTHY")
    args = parser.parse_args(argv)
    try:
        policy = json.loads(args.policy.read_text(encoding="utf-8"))
        if not isinstance(policy, dict):
            raise ValueError("PROBE_POLICY_MUST_BE_OBJECT")
        report = build_report(policy)
        encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        print(encoded, end="")
        return 2 if args.strict and report["overall"] != "HEALTHY" else 0
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        print(json.dumps({"overall": "BLOCKED", "reason": type(exc).__name__ + ":" + str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
