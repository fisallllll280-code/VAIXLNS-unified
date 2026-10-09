import base64
import gzip
import json
from pathlib import Path

from tools.expand_index_bundle import decode_artifact

ROOT = Path(__file__).resolve().parents[1]


def test_index_catalog_is_unique_and_nexus_owned():
    data = json.loads((ROOT / "registry/index_catalog.json").read_text(encoding="utf-8"))
    indexes = data["indexes"]
    ids = [item["index_id"] for item in indexes]
    assert len(indexes) == 56
    assert len(ids) == len(set(ids))
    assert all(item["canonical_owner"] == "NEXUS" for item in indexes)


def test_innovation_records_preserve_status_and_wallet_nonproduction_boundary():
    data = json.loads((ROOT / "registry/innovation_registry.json").read_text(encoding="utf-8"))
    records = data["records"]
    ids = [item["innovation_id"] for item in records]
    assert len(records) == 59
    assert len(ids) == len(set(ids))
    assert all(item.get("legacy_id") is None for item in records)
    wallet = next(item for item in records if item["innovation_id"] == "INNO-WALLET-AUTOMATION-001")
    assert wallet["operational_state"] == "NOT_PRODUCTION"
    assert wallet["test_evidence"].startswith("Wallet GitHub Actions")


def test_coverage_manifest_preserves_archive_counts_and_legacy_gap():
    data = json.loads((ROOT / "registry/index_coverage_manifest.json").read_text(encoding="utf-8"))
    assert data["source_files_in_workspace"] == 69
    assert data["index_views_catalogued"] == 56
    assert data["innovation_records_compiled"] == 59
    assert data["derived_atomic_decomposition_records"] == 570
    assert data["original_legacy_mapping_status"] == "UNPROVEN_NOT_RECOVERED_ELEMENT_BY_ELEMENT"
    assert "not original" in data["critical_distinction"]


def test_inventory_summary_points_to_digested_full_inventory():
    data = json.loads((ROOT / "registry/archive_source_inventory_summary.json").read_text(encoding="utf-8"))
    assert data["source_files_in_workspace"] == 69
    assert data["total_bytes"] == 786341
    assert len(data["detailed_inventory_sha256"]) == 64


def test_decoder_roundtrip_on_synthetic_compressed_index(tmp_path):
    source = {"schema":"fixture.v1","records":[["E-001","Example","SECTION",7]]}
    compressed = gzip.compress(json.dumps(source).encode("utf-8"), mtime=0)
    artifact = tmp_path / "fixture.json.gz.b64"
    artifact.write_text(base64.b64encode(compressed).decode("ascii"), encoding="ascii")
    decoded_path = decode_artifact(artifact, tmp_path / "out")
    assert json.loads(decoded_path.read_text(encoding="utf-8")) == source
