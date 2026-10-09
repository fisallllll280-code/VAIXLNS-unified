"""Zero-loss legacy archive extraction and lineage-preserving index primitives.

This module is intentionally provider-neutral and offline-safe. It ingests source
text supplied by approved adapters, splits it into atomic records, fingerprints
records deterministically, proposes (never applies) duplicate/lineage links, and
exports an auditable JSONL catalog. It never deletes, merges, or promotes records.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import re
import unicodedata
from typing import Iterable, Mapping, Sequence

SCHEMA_VERSION = "1.0.0"
RECORD_ID_PATTERN = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:ID\s*[:：]|(?:Ω\.)?\d{1,6}[.)、:]\s*)"
)
EXPLICIT_ID_PATTERN = re.compile(
    r"(?im)^\s*(?:#{1,6}\s*)?(?:ID\s*[:：]\s*([A-Z0-9_.:-]{2,64})"
    r"|((?:Ω\.)?[A-Z][A-Z0-9_.:-]{1,63}|\d{1,6})\s*[.)、:])"
)
HEADING_PATTERN = re.compile(r"(?m)^#{1,6}\s+(.+?)\s*$")
STATUS_VALUES = {
    "RECOVERED", "CANONICAL", "PROPOSED", "IMPLEMENTED", "VERIFIED",
    "MISSING", "CONFLICT", "UNRESOLVED",
}


def sha256_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """Unicode-aware normalization used only for search and comparison hints."""
    value = unicodedata.normalize("NFKC", text).casefold()
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def token_similarity(left: str, right: str) -> float:
    a = set(normalize_text(left).split())
    b = set(normalize_text(right).split())
    return len(a & b) / len(a | b) if a and b else 0.0


@dataclass(frozen=True)
class SourceDocument:
    source_uri: str
    content: str
    title: str = ""
    revision: str = ""
    source_type: str = "UNKNOWN"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_uri.strip():
            raise ValueError("SOURCE_URI_REQUIRED")
        if not self.content.strip():
            raise ValueError("SOURCE_CONTENT_REQUIRED")
        if self.source_type not in {
            "ARCHIVE", "REPOSITORY", "DOCUMENT", "ISSUE", "COMMIT", "UNKNOWN"
        }:
            raise ValueError("INVALID_SOURCE_TYPE")

    @property
    def content_sha256(self) -> str:
        return sha256_text(self.content)

    @property
    def source_id(self) -> str:
        seed = json.dumps(
            [self.source_uri.rstrip("/"), self.revision, self.content_sha256],
            ensure_ascii=False, separators=(",", ":"),
        )
        return "SRC-" + sha256_text(seed)[:20]


@dataclass(frozen=True)
class AtomicRecord:
    record_uid: str
    legacy_id: str
    title: str
    body: str
    source_id: str
    source_uri: str
    source_sha256: str
    ordinal: int
    status: str = "RECOVERED"
    parent_uid: str = ""
    aliases: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    lineage_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.record_uid or not self.source_id or not self.source_sha256:
            raise ValueError("RECORD_IDENTITY_AND_PROVENANCE_REQUIRED")
        if self.status not in STATUS_VALUES:
            raise ValueError("INVALID_RECORD_STATUS")
        if self.ordinal < 1:
            raise ValueError("ORDINAL_MUST_BE_POSITIVE")

    @property
    def content_sha256(self) -> str:
        return sha256_text(self.title + "\n" + self.body)


@dataclass(frozen=True)
class SimilarityCandidate:
    left_uid: str
    right_uid: str
    score: float
    reason: str
    action: str = "HUMAN_REVIEW_ONLY"


@dataclass(frozen=True)
class ExtractionReport:
    schema_version: str
    source_count: int
    record_count: int
    unique_content_count: int
    repeated_content_groups: tuple[tuple[str, ...], ...]
    missing_legacy_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    records: tuple[AtomicRecord, ...]


def _split_spans(content: str) -> list[tuple[int, int]]:
    """Split on Markdown headings first; otherwise preserve numbered/ID records."""
    headings = list(HEADING_PATTERN.finditer(content))
    if len(headings) >= 2:
        starts = [m.start() for m in headings]
        spans = [(start, starts[i + 1] if i + 1 < len(starts) else len(content))
                 for i, start in enumerate(starts)]
        preamble = content[:starts[0]].strip()
        if preamble:
            spans.insert(0, (0, starts[0]))
        return spans
    matches = list(RECORD_ID_PATTERN.finditer(content))
    if len(matches) >= 2:
        starts = [m.start() for m in matches]
        return [(start, starts[i + 1] if i + 1 < len(starts) else len(content))
                for i, start in enumerate(starts)]
    return [(0, len(content))]


def _title_for(chunk: str, ordinal: int) -> str:
    heading = HEADING_PATTERN.search(chunk)
    if heading:
        return heading.group(1).strip()
    lines = [line.strip(" #\t") for line in chunk.splitlines() if line.strip()]
    if not lines:
        return f"Untitled record {ordinal}"
    first = lines[0]
    # Remove a leading explicit identifier from the display title.
    first = re.sub(r"(?i)^\s*(?:ID\s*[:：]\s*)?(?:Ω\.)?[A-Z0-9_.:-]{2,64}[.)、:]?\s*", "", first)
    return first[:180] or f"Untitled record {ordinal}"


def _legacy_id(chunk: str, ordinal: int) -> str:
    first_lines = "\n".join(chunk.splitlines()[:4])
    match = EXPLICIT_ID_PATTERN.search(first_lines)
    if match:
        candidate = (match.group(1) or match.group(2)).strip()
        # A standalone numbered Markdown heading/entry is a legacy ID only when
        # the original text actually uses an enumerated form.
        return candidate
    return ""


def extract_atomic_records(source: SourceDocument) -> tuple[AtomicRecord, ...]:
    """Atomize a document without dropping content; record UIDs are reproducible."""
    records: list[AtomicRecord] = []
    for ordinal, (start, end) in enumerate(_split_spans(source.content), start=1):
        chunk = source.content[start:end]
        if not chunk.strip():
            continue
        title = _title_for(chunk, ordinal)
        legacy_id = _legacy_id(chunk, ordinal)
        body = chunk
        uid_seed = json.dumps(
            [source.source_id, ordinal, legacy_id, sha256_text(chunk)],
            ensure_ascii=False, separators=(",", ":"),
        )
        uid = "REC-" + sha256_text(uid_seed)[:24]
        notes = () if legacy_id else ("LEGACY_ID_NOT_EXPLICIT_IN_SOURCE",)
        records.append(AtomicRecord(
            record_uid=uid,
            legacy_id=legacy_id,
            title=title,
            body=body,
            source_id=source.source_id,
            source_uri=source.source_uri,
            source_sha256=source.content_sha256,
            ordinal=ordinal,
            notes=notes,
        ))
    return tuple(records)


def repeated_content_groups(records: Sequence[AtomicRecord]) -> tuple[tuple[str, ...], ...]:
    """Report exact repeats as review groups; retain every record and its provenance."""
    by_hash: dict[str, list[str]] = {}
    for record in records:
        by_hash.setdefault(record.content_sha256, []).append(record.record_uid)
    return tuple(sorted(
        (tuple(sorted(uids)) for uids in by_hash.values() if len(uids) > 1),
        key=lambda group: group,
    ))


def propose_similarity_links(
    records: Sequence[AtomicRecord], threshold: float = 0.82,
) -> tuple[SimilarityCandidate, ...]:
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("THRESHOLD_OUT_OF_RANGE")
    candidates: list[SimilarityCandidate] = []
    for i, left in enumerate(records):
        for right in records[i + 1:]:
            if left.content_sha256 == right.content_sha256:
                score, reason = 1.0, "EXACT_CONTENT_MATCH"
            else:
                score = token_similarity(left.title + " " + left.body,
                                         right.title + " " + right.body)
                reason = "TOKEN_SIMILARITY_REVIEW"
            if score >= threshold:
                candidates.append(SimilarityCandidate(
                    left.record_uid, right.record_uid, round(score, 6), reason
                ))
    return tuple(sorted(candidates, key=lambda c: (-c.score, c.left_uid, c.right_uid)))


def build_extraction_report(
    sources: Iterable[SourceDocument],
    *,
    expected_legacy_ids: Iterable[str] = (),
) -> ExtractionReport:
    source_list = tuple(sources)
    if len({source.source_id for source in source_list}) != len(source_list):
        raise ValueError("DUPLICATE_SOURCE_ID")
    records = tuple(record for source in source_list for record in extract_atomic_records(source))
    seen_ids = {record.legacy_id for record in records if record.legacy_id}
    missing = tuple(sorted(set(expected_legacy_ids) - seen_ids))
    warnings: list[str] = []
    if not source_list:
        warnings.append("NO_SOURCES_SUPPLIED")
    if missing:
        warnings.append("EXPECTED_LEGACY_IDS_NOT_FOUND")
    if any(record.notes for record in records):
        warnings.append("SOME_RECORDS_HAVE_NO_EXPLICIT_LEGACY_ID")
    hashes = {record.content_sha256 for record in records}
    return ExtractionReport(
        schema_version=SCHEMA_VERSION,
        source_count=len(source_list),
        record_count=len(records),
        unique_content_count=len(hashes),
        repeated_content_groups=repeated_content_groups(records),
        missing_legacy_ids=missing,
        warnings=tuple(warnings),
        records=records,
    )


def export_jsonl(records: Iterable[AtomicRecord]) -> str:
    """Stable UTF-8 JSONL suitable for version control and streaming ingestion."""
    return "".join(
        json.dumps(asdict(record), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )


def search_records(
    records: Sequence[AtomicRecord], query: str, limit: int = 20,
) -> tuple[tuple[float, AtomicRecord], ...]:
    """Deterministic lexical retrieval; not a substitute for multilingual embeddings."""
    if limit < 1:
        raise ValueError("LIMIT_MUST_BE_POSITIVE")
    q = set(normalize_text(query).split())
    ranked = []
    for record in records:
        terms = set(normalize_text(record.title + " " + record.body + " " +
                                   " ".join(record.aliases + record.tags)).split())
        score = len(q & terms) / len(q) if q else 0.0
        if score > 0:
            ranked.append((round(score, 6), record))
    ranked.sort(key=lambda item: (-item[0], item[1].legacy_id or "~",
                                  item[1].source_uri, item[1].ordinal))
    return tuple(ranked[:limit])
