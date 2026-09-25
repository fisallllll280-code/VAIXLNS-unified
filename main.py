"""VAIXLNS executable entrypoint for the current federated runtime surface."""

from __future__ import annotations

import json
import sys

from integration.boot import run_smoke


def main() -> int:
    report = run_smoke()
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.smoke_passed else 1


if __name__ == "__main__":
    sys.exit(main())
