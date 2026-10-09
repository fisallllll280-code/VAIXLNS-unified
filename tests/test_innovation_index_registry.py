import base64
import gzip
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_gzip_b64(path: Path):
    payload = gzip.decompress(base64.b64decode(path.read_text(encoding="ascii").strip(), validate=True))
    return json.loads(payload.decode("utf-8"))


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


def test_atomic_decomposition_index_is_570_source_local_labels_not_legacy_ids():
    path = ROOT / "registry/atomic_decomposition_index.json.gz.b64"
    data = _load_gzip_b64(path)
    assert data["record_count"] == 570
    assert len(data["records"]) == 570
    assert data["records"][0][0] == "A-001"
    assert data["records"][-1][0] == "A-570"
    assert len({record[0] for record in data["records"]}) == 570
    assert "not historical 0001-2750 IDs" in data["legacy_mapping"]


def test_archive_source_inventory_is_69_sources_with_unique_ids_and_hashes():
    path = ROOT / "registry/archive_source_inventory.json.gz.b64"
    data = _load_gzip_b64(path)
    assert data["count"] == 69
    assert len(data["sources"]) == 69
    ids = [item["source_id"] for item in data["sources"]]
    hashes = [item["sha256"] for item in data["sources"]]
    assert len(ids) == len(set(ids))
    assert all(len(digest) == 64 for digest in hashes)


def test_coverage_manifest_keeps_original_registry_gap_explicit():
    data = json.loads((ROOT / "registry/index_coverage_manifest.json").read_text(encoding="utf-8"))
    assert data["derived_atomic_decomposition_records"] == 570
    assert data["original_legacy_mapping_status"] == "UNPROVEN_NOT_RECOVERED_ELEMENT_BY_ELEMENT"
    assert "not original" in data["critical_distinction"]
