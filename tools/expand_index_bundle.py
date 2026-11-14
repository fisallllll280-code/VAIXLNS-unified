#!/usr/bin/env python3
"""Expand committed base64-encoded gzip JSON registry artifacts."""
from __future__ import annotations
import argparse
import base64
import gzip
import json
from pathlib import Path


def decode_artifact(path: Path, output_dir: Path) -> Path:
    encoded = path.read_text(encoding="ascii").strip()
    payload = gzip.decompress(base64.b64decode(encoded, validate=True))
    value = json.loads(payload.decode("utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    name = path.name.removesuffix(".gz.b64")
    if not name.endswith(".json"):
        name += ".json"
    output = output_dir / name
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifacts", nargs="*", type=Path, help="one or more *.json.gz.b64 files")
    parser.add_argument("--input-dir", type=Path, help="directory to scan for *.json.gz.b64")
    parser.add_argument("--output-dir", type=Path, default=Path("registry/generated"))
    args = parser.parse_args()
    artifacts = list(args.artifacts)
    if args.input_dir:
        artifacts.extend(sorted(args.input_dir.glob("*.json.gz.b64")))
    if not artifacts:
        parser.error("provide artifact paths or --input-dir")
    for artifact in artifacts:
        print(decode_artifact(artifact, args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
