"""Validate a VX ONE system manifest and print a plan-only summary."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vx.system_loader import LoaderError, load_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="path to a VX system manifest JSON file")
    args = parser.parse_args()
    try:
        data, artifacts = load_manifest(args.manifest)
    except LoaderError as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({
        "status": "MANIFEST_VALID_PLAN_ONLY",
        "system_id": data["system_id"],
        "version": data["version"],
        "artifact_count": len(artifacts),
        "network_enabled": False,
        "install_execution": False,
        "human_approval_required": True,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
