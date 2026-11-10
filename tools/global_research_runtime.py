"""Bounded, read-only global research cycle built on the existing REDF fabric.

This module orchestrates research only. It never writes to repositories, executes
candidate code, changes canonical records, or authorizes promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from innovation_control.research_fabric import (
    CatalogEntry,
    ResearchDecisionOrchestrator,
    ResearchRequest,
    SearchProvider,
)

DEFAULT_REPOSITORIES = (
    "fisallllll280-code/VAIXLNS",
    "fisallllll280-code/VAIXLNS-unified",
    "fisallllll280-code/VX-runtime",
)


@dataclass(frozen=True)
class ResearchCycleConfig:
    mission: str
    repositories: tuple[str, ...] = DEFAULT_REPOSITORIES
    min_source_records: int = 2
    min_primary_sources: int = 1
    require_counterevidence: bool = True

    def __post_init__(self) -> None:
        if not self.mission.strip():
            raise ValueError("MISSION_REQUIRED")
        if not self.repositories:
            raise ValueError("EXPLICIT_REPOSITORY_ALLOWLIST_REQUIRED")
        if len(set(self.repositories)) != len(self.repositories):
            raise ValueError("DUPLICATE_REPOSITORY_SCOPE")
        if self.min_source_records < 1 or self.min_primary_sources < 0:
            raise ValueError("INVALID_SOURCE_THRESHOLDS")
        for repository in self.repositories:
            parts = repository.split("/")
            if len(parts) != 2 or not all(parts) or any(
                not (part.replace("-", "").replace("_", "").replace(".", "").isalnum())
                for part in parts
            ):
                raise ValueError("INVALID_REPOSITORY_SCOPE")


def catalog_from_payload(payload: Any) -> tuple[CatalogEntry, ...]:
    """Parse an explicitly supplied innovation index without claiming completeness."""
    records = payload if isinstance(payload, list) else (
        payload.get("items", []) if isinstance(payload, Mapping) else []
    )
    if not isinstance(records, list):
        raise ValueError("CATALOG_ITEMS_MUST_BE_ARRAY")
    entries: list[CatalogEntry] = []
    for item in records:
        if not isinstance(item, Mapping):
            continue
        identifier = item.get("canonical_id") or item.get("innovation_id") or item.get("id")
        name = item.get("name") or item.get("title")
        if not isinstance(identifier, str) or not isinstance(name, str):
            continue
        summary = item.get("description") or item.get("summary") or ""
        aliases = item.get("aliases") or item.get("native_ids") or ()
        if isinstance(aliases, str):
            aliases = (aliases,)
        if not isinstance(aliases, (list, tuple)):
            aliases = ()
        entries.append(CatalogEntry(
            innovation_id=identifier,
            name=name,
            summary=summary if isinstance(summary, str) else "",
            aliases=tuple(x for x in aliases if isinstance(x, str) and x.strip()),
        ))
    # Stable, deterministic identity handling; conflicting duplicate IDs are not silently merged.
    by_id: dict[str, CatalogEntry] = {}
    for entry in entries:
        previous = by_id.get(entry.innovation_id)
        if previous is not None and previous != entry:
            raise ValueError("CATALOG_ID_CONFLICT:" + entry.innovation_id)
        by_id[entry.innovation_id] = entry
    return tuple(by_id[key] for key in sorted(by_id))


def load_catalog(path: str | Path | None) -> tuple[CatalogEntry, ...]:
    if path is None:
        return ()
    source = Path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    return catalog_from_payload(payload)


def build_research_request(
    config: ResearchCycleConfig,
    catalog: Sequence[CatalogEntry] = (),
) -> ResearchRequest:
    return ResearchRequest(
        mission=config.mission,
        candidate_title="VAIXLNS Global Research Cycle",
        candidate_summary=(
            "Evidence-first discovery, contradiction analysis, engineering readiness, "
            "simulation planning, and repository recovery coordination."
        ),
        innovation_id="VX-GLOBAL-RESEARCH-CYCLE",
        scopes=config.repositories,
        catalog=tuple(catalog),
        # A local index snapshot is never assumed to cover all historical or external work.
        catalog_coverage_complete=False,
        min_source_records=config.min_source_records,
        min_primary_sources=config.min_primary_sources,
        require_counterevidence=config.require_counterevidence,
    )


def run_research_cycle(
    config: ResearchCycleConfig,
    providers: Sequence[SearchProvider],
    catalog: Sequence[CatalogEntry] = (),
) -> dict[str, Any]:
    if not providers:
        raise ValueError("AT_LEAST_ONE_SEARCH_PROVIDER_REQUIRED")
    request = build_research_request(config, catalog)
    bundle = ResearchDecisionOrchestrator().run(request, tuple(providers))
    payload = bundle.to_dict()
    payload["cycle_control"] = {
        "repositories": list(config.repositories),
        "provider_ids": sorted(provider.provider_id for provider in providers),
        "read_only": True,
        "candidate_execution": False,
        "canonical_mutation": False,
        "promotion_authorized": False,
        "catalog_coverage_certified": False,
    }
    payload["cycle_metrics"] = {
        "query_lanes": len(bundle.queries),
        "unique_sources": len(bundle.sources),
        "provider_errors": sum(1 for item in bundle.search_outcomes if item.status == "ERROR"),
        "source_revisions": len({(item.uri, item.revision) for item in bundle.sources}),
    }
    return payload


def require_network_authorization(execute: bool, network_enabled: bool) -> None:
    """Fail closed: both an explicit CLI request and an explicit environment gate are required."""
    if not execute:
        raise PermissionError("EXECUTION_NOT_REQUESTED")
    if not network_enabled:
        raise PermissionError("NETWORK_GATE_DISABLED_SET_VX_RESEARCH_NETWORK_ENABLED=1")


def render_report(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


__all__ = [
    "DEFAULT_REPOSITORIES",
    "ResearchCycleConfig",
    "build_research_request",
    "catalog_from_payload",
    "load_catalog",
    "render_report",
    "require_network_authorization",
    "run_research_cycle",
]
