#!/usr/bin/env python3
"""Run the bounded, read-only VAIXLNS repository research cycle."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.global_research_runtime import (  # noqa: E402
    DEFAULT_REPOSITORIES,
    ResearchCycleConfig,
    load_catalog,
    render_report,
    require_network_authorization,
    run_research_cycle,
)
from tools.research_adapters import GitHubRepositorySearchProvider  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mission",
        default="Discover, challenge, and recover evidence for VAIXLNS engineering innovations.",
    )
    parser.add_argument("--repositories", nargs="+", default=list(DEFAULT_REPOSITORIES))
    parser.add_argument("--catalog", help="Path to a local innovation-index JSON snapshot.")
    parser.add_argument("--max-sources", type=int, default=8)
    parser.add_argument("--max-candidates-per-repo", type=int, default=2)
    parser.add_argument("--execute", action="store_true", help="Request live read-only GitHub research.")
    parser.add_argument("--output", help="Optional local JSON report path; no repository write occurs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        require_network_authorization(
            execute=args.execute,
            network_enabled=os.environ.get("VX_RESEARCH_NETWORK_ENABLED") == "1",
        )
        if not 1 <= args.max_sources <= 12:
            raise ValueError("MAX_SOURCES_OUT_OF_RANGE")
        if not 1 <= args.max_candidates_per_repo <= 8:
            raise ValueError("MAX_CANDIDATES_PER_REPO_OUT_OF_RANGE")
        config = ResearchCycleConfig(
            mission=args.mission,
            repositories=tuple(args.repositories),
        )
        provider = GitHubRepositorySearchProvider(
            allowed_repositories=config.repositories,
            token=os.environ.get("GITHUB_TOKEN", ""),
            max_sources=args.max_sources,
            max_candidates_per_repo=args.max_candidates_per_repo,
        )
        catalog = load_catalog(args.catalog)
        report = run_research_cycle(config, (provider,), catalog)
        rendered = render_report(report)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0
    except Exception as exc:
        sys.stderr.write(f"GLOBAL_RESEARCH_BLOCKED: {type(exc).__name__}: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
