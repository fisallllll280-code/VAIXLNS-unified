"""Command-line entrypoint for the governed, read-only VAIXLNS research cycle.

This runner composes the existing REDF decision fabric with pinned GitHub
repository adapters. It never writes to GitHub, mutates a checkout, or grants
promotion authority. Its only write is a create-only local evidence bundle.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence

from innovation_control.research_fabric import (
    CatalogEntry,
    ResearchDecisionOrchestrator,
    ResearchRequest,
    digest,
)
from tools.research_adapters import GitHubRepositorySearchProvider


def _read_json(path: str | None, *, expected: type) -> Any:
    if not path:
        return expected() if expected in (dict, list) else None
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, expected):
        raise ValueError(f"INPUT_JSON_EXPECTED_{expected.__name__.upper()}")
    return value


def _load_catalog(path: str | None) -> tuple[CatalogEntry, ...]:
    raw = _read_json(path, expected=list)
    entries = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"CATALOG_ENTRY_{index}_MUST_BE_OBJECT")
        aliases = item.get("aliases", [])
        if not isinstance(aliases, list) or any(not isinstance(x, str) for x in aliases):
            raise ValueError(f"CATALOG_ENTRY_{index}_ALIASES_MUST_BE_STRING_LIST")
        entries.append(CatalogEntry(
            innovation_id=str(item.get("innovation_id", "")).strip(),
            name=str(item.get("name", "")).strip(),
            summary=str(item.get("summary", "")),
            aliases=tuple(aliases),
        ))
    return tuple(entries)


def _write_bundle_create_only(path: str, bundle: dict[str, Any]) -> str:
    """Persist an auditable bundle without ever overwriting a prior run."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(str(target), flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return str(target)


def run_cycle(
    *,
    mission: str,
    candidate_title: str,
    repositories: Sequence[str],
    candidate_summary: str = "",
    engineering_spec: dict[str, Any] | None = None,
    catalog: Sequence[CatalogEntry] = (),
    catalog_coverage_complete: bool = False,
    min_source_records: int = 2,
    min_primary_sources: int = 1,
    max_sources: int = 8,
    token: str = "",
) -> dict[str, Any]:
    """Run all REDF research lanes against an explicit GitHub allowlist."""
    allowlist = tuple(dict.fromkeys(item.strip() for item in repositories if item.strip()))
    if not allowlist:
        raise ValueError("EXPLICIT_REPOSITORY_ALLOWLIST_REQUIRED")
    provider = GitHubRepositorySearchProvider(
        allowed_repositories=allowlist,
        token=token,
        max_sources=max_sources,
    )
    request = ResearchRequest(
        mission=mission,
        candidate_title=candidate_title,
        candidate_summary=candidate_summary,
        scopes=allowlist,
        catalog=tuple(catalog),
        catalog_coverage_complete=catalog_coverage_complete,
        engineering_spec=engineering_spec or {},
        min_source_records=min_source_records,
        min_primary_sources=min_primary_sources,
    )
    bundle = ResearchDecisionOrchestrator().run(request, (provider,))
    payload = bundle.to_dict()
    payload["bundle_sha256"] = digest(payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an evidence-first, read-only research cycle over allowlisted GitHub repositories."
    )
    parser.add_argument("--mission", required=True)
    parser.add_argument("--candidate-title", required=True)
    parser.add_argument("--candidate-summary", default="")
    parser.add_argument("--repositories", required=True,
                        help="Comma-separated owner/repository allowlist; no wildcard expansion.")
    parser.add_argument("--engineering-spec", help="Optional JSON object with the REDF engineering contract.")
    parser.add_argument("--catalog", help="Optional JSON array of existing innovation records.")
    parser.add_argument("--catalog-coverage-complete", action="store_true",
                        help="Declare catalog coverage complete only when independently established.")
    parser.add_argument("--min-sources", type=int, default=2)
    parser.add_argument("--min-primary-sources", type=int, default=1)
    parser.add_argument("--max-sources", type=int, default=8)
    parser.add_argument("--output", required=True, help="Create-only path for the evidence JSON bundle.")
    parser.add_argument("--allow-network", action="store_true",
                        help="Explicitly permit read-only GitHub API requests.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.allow_network:
        print("BLOCKED: pass --allow-network to authorize read-only GitHub API access.", file=sys.stderr)
        return 2
    try:
        repositories = tuple(args.repositories.split(","))
        spec = _read_json(args.engineering_spec, expected=dict)
        catalog = _load_catalog(args.catalog)
        bundle = run_cycle(
            mission=args.mission,
            candidate_title=args.candidate_title,
            candidate_summary=args.candidate_summary,
            repositories=repositories,
            engineering_spec=spec,
            catalog=catalog,
            catalog_coverage_complete=args.catalog_coverage_complete,
            min_source_records=args.min_sources,
            min_primary_sources=args.min_primary_sources,
            max_sources=args.max_sources,
            token=os.environ.get("GITHUB_TOKEN", ""),
        )
        output = _write_bundle_create_only(args.output, bundle)
    except FileExistsError:
        print("BLOCKED: output already exists; refusing to overwrite prior evidence.", file=sys.stderr)
        return 3
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({
        "run_id": bundle["run_id"],
        "decision_state": bundle["decision_state"],
        "novelty_state": bundle["novelty_state"],
        "source_count": len(bundle["sources"]),
        "query_lane_count": len(bundle["queries"]),
        "promotion_authorized": bundle["promotion_authorized"],
        "bundle_sha256": bundle["bundle_sha256"] if "bundle_sha256" in bundle else None,
        "output": output,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
