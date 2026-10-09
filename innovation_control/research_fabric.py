"""Evidence-first multi-agent research and engineering-decision fabric.

The fabric gathers source-bound evidence, tests counterclaims, screens lineage,
checks engineering completeness, and produces an auditable decision packet.
It does not make search-provider claims without adapter results and never
promotes a proposal to VERIFIED or CANONICAL.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Protocol, Sequence


SCHEMA_VERSION = "1.0.0"

DEFAULT_SPEC_FIELDS = (
    "problem_statement",
    "assumptions",
    "invariants",
    "architecture",
    "interfaces",
    "dependencies",
    "security_boundary",
    "failure_modes",
    "implementation_plan",
    "acceptance_tests",
    "verification_plan",
    "rollback_plan",
    "operational_metrics",
    "owner",
    "evidence_refs",
    "known_unknowns",
)


class QueryPurpose(str, Enum):
    DISCOVERY = "DISCOVERY"
    NOVELTY = "NOVELTY"
    COUNTEREVIDENCE = "COUNTEREVIDENCE"
    IMPLEMENTATION = "IMPLEMENTATION"
    CONTRADICTION = "CONTRADICTION"
    FAILURE_ANALYSIS = "FAILURE_ANALYSIS"


class EvidenceClass(str, Enum):
    CANONICAL_SOURCE = "CANONICAL_SOURCE"
    ARCHIVE = "ARCHIVE"
    IMPLEMENTATION = "IMPLEMENTATION"
    TEST = "TEST"
    RUNTIME = "RUNTIME"
    SECONDARY = "SECONDARY"
    UNKNOWN = "UNKNOWN"


class Stance(str, Enum):
    SUPPORTS = "SUPPORTS"
    REFUTES = "REFUTES"
    QUALIFIES = "QUALIFIES"
    NEUTRAL = "NEUTRAL"


class AgentOutcome(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCKED = "BLOCKED"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    GAP = "GAP"
    BLOCKER = "BLOCKER"


class DecisionState(str, Enum):
    BLOCKED = "BLOCKED"
    NEEDS_INVESTIGATION = "NEEDS_INVESTIGATION"
    ENGINEERING_GAPS = "ENGINEERING_GAPS"
    READY_FOR_ENGINEERING_REVIEW = "READY_FOR_ENGINEERING_REVIEW"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def digest(value: Any) -> str:
    return sha256(stable_json(value).encode("utf-8")).hexdigest()


def content_digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def token_similarity(left: str, right: str) -> float:
    a = {t for t in normalize(left).split() if len(t) > 1}
    b = {t for t in normalize(right).split() if len(t) > 1}
    return len(a & b) / len(a | b) if a and b else 0.0


@dataclass(frozen=True)
class ResearchQuery:
    query_id: str
    text: str
    purpose: QueryPurpose
    required: bool = True


@dataclass(frozen=True)
class ClaimEvidence:
    claim_id: str
    stance: Stance
    excerpt: str
    location: str = ""

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.excerpt.strip():
            raise ValueError("CLAIM_EVIDENCE_REQUIRES_ID_AND_EXCERPT")


@dataclass(frozen=True)
class SourceRecord:
    title: str
    uri: str
    content: str
    evidence_class: EvidenceClass = EvidenceClass.UNKNOWN
    revision: str = ""
    origin_digest: str = ""
    claims: tuple[ClaimEvidence, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    source_id: str = ""
    content_sha256: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip() or not self.uri.strip():
            raise ValueError("SOURCE_TITLE_AND_URI_REQUIRED")
        actual = content_digest(self.content)
        if self.content_sha256 and self.content_sha256.lower() != actual:
            raise ValueError("SOURCE_CONTENT_HASH_MISMATCH")
        if not self.content_sha256:
            object.__setattr__(self, "content_sha256", actual)
        if self.origin_digest and not re.fullmatch(r"[0-9a-fA-F]{64}", self.origin_digest):
            raise ValueError("ORIGIN_DIGEST_MUST_BE_SHA256")
        if not self.source_id:
            object.__setattr__(
                self,
                "source_id",
                "SRC-" + digest({
                    "uri": self.uri.rstrip("/"),
                    "content_sha256": actual,
                    "revision": self.revision,
                    "origin_digest": self.origin_digest.lower(),
                })[:16],
            )


@dataclass(frozen=True)
class CatalogEntry:
    innovation_id: str
    name: str
    summary: str = ""
    aliases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.innovation_id.strip() or not self.name.strip():
            raise ValueError("CATALOG_ENTRY_REQUIRES_ID_AND_NAME")


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    statement: str
    required: bool = True

    def __post_init__(self) -> None:
        if not self.claim_id.strip() or not self.statement.strip():
            raise ValueError("RESEARCH_CLAIM_REQUIRES_ID_AND_STATEMENT")


@dataclass(frozen=True)
class ResearchRequest:
    mission: str
    candidate_title: str
    candidate_summary: str = ""
    innovation_id: str = ""
    scopes: tuple[str, ...] = ()
    custom_queries: tuple[str, ...] = ()
    claims: tuple[ResearchClaim, ...] = ()
    catalog: tuple[CatalogEntry, ...] = ()
    catalog_coverage_complete: bool = False
    engineering_spec: Mapping[str, Any] = field(default_factory=dict)
    required_spec_fields: tuple[str, ...] = DEFAULT_SPEC_FIELDS
    min_source_records: int = 2
    min_primary_sources: int = 1
    require_counterevidence: bool = True

    def __post_init__(self) -> None:
        if not self.mission.strip() or not self.candidate_title.strip():
            raise ValueError("MISSION_AND_CANDIDATE_TITLE_REQUIRED")
        if self.min_source_records < 1 or self.min_primary_sources < 0:
            raise ValueError("INVALID_SOURCE_THRESHOLDS")
        if len({claim.claim_id for claim in self.claims}) != len(self.claims):
            raise ValueError("DUPLICATE_CLAIM_ID")


class SearchProvider(Protocol):
    """Provider adapter for GitHub, web, archives, files, or a local index."""

    @property
    def provider_id(self) -> str:
        ...

    def search(self, query: ResearchQuery, scopes: Sequence[str]) -> Sequence[SourceRecord]:
        ...


@dataclass(frozen=True)
class SearchOutcome:
    provider_id: str
    query_id: str
    purpose: QueryPurpose
    status: str
    source_ids: tuple[str, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    source_refs: tuple[str, ...] = ()
    blocks_readiness: bool = False


@dataclass(frozen=True)
class AgentReport:
    agent_id: str
    role: str
    outcome: AgentOutcome
    summary: str
    findings: tuple[Finding, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    work_items: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResearchContext:
    request: ResearchRequest
    queries: tuple[ResearchQuery, ...]
    sources: tuple[SourceRecord, ...]
    outcomes: tuple[SearchOutcome, ...]


@dataclass(frozen=True)
class ResearchBundle:
    schema_version: str
    run_id: str
    innovation_id: str
    mission: str
    candidate_title: str
    decision_state: DecisionState
    novelty_state: str
    sources: tuple[SourceRecord, ...]
    queries: tuple[ResearchQuery, ...]
    search_outcomes: tuple[SearchOutcome, ...]
    agent_reports: tuple[AgentReport, ...]
    open_questions: tuple[str, ...]
    next_actions: tuple[str, ...]
    promotion_authorized: bool = False
    epistemic_note: str = (
        "Research output is not implementation, verification, certification, or canonical authority."
    )

    @property
    def canonical_eligible(self) -> bool:
        return False

    @property
    def bundle_sha256(self) -> str:
        return digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        def encode(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if hasattr(value, "__dataclass_fields__"):
                return {key: encode(item) for key, item in asdict(value).items()}
            if isinstance(value, Mapping):
                return {str(key): encode(item) for key, item in value.items()}
            if isinstance(value, (tuple, list)):
                return [encode(item) for item in value]
            return value
        return encode(self)


def build_query_plan(request: ResearchRequest) -> tuple[ResearchQuery, ...]:
    """Generate complementary lanes; adversarial and implementation search are mandatory."""
    title, mission = request.candidate_title.strip(), request.mission.strip()
    planned = [
        (QueryPurpose.DISCOVERY, f'"{title}" archive index historical source'),
        (QueryPurpose.DISCOVERY, f"{mission} related systems capabilities prior work"),
        (QueryPurpose.NOVELTY, f"{title} existing catalog aliases implementation overlap"),
        (QueryPurpose.COUNTEREVIDENCE, f"{title} counterexample limitations failure security risk"),
        (QueryPurpose.IMPLEMENTATION, f"{title} source code tests runtime evidence provenance"),
        (QueryPurpose.CONTRADICTION, f"{mission} conflicting claims alternative explanations"),
        (QueryPurpose.FAILURE_ANALYSIS, f"{title} adversarial cases rollback recovery failure modes"),
    ]
    planned.extend((QueryPurpose.DISCOVERY, item.strip()) for item in request.custom_queries if item.strip())
    result: dict[tuple[str, str], ResearchQuery] = {}
    for purpose, text in planned:
        key = (purpose.value, normalize(text))
        if key not in result:
            result[key] = ResearchQuery(
                query_id="Q-" + digest({"purpose": purpose.value, "query": text})[:12],
                text=text,
                purpose=purpose,
                required=True,
            )
    return tuple(result[key] for key in sorted(result))


def consolidate_sources(records: Sequence[SourceRecord]) -> tuple[SourceRecord, ...]:
    """Merge exact copies only; same URI with changed content is retained as a version conflict."""
    grouped: dict[tuple[str, str, str, str], list[SourceRecord]] = {}
    for source in records:
        key = (source.uri.rstrip("/"), source.content_sha256, source.revision, source.origin_digest.lower())
        grouped.setdefault(key, []).append(source)
    consolidated: list[SourceRecord] = []
    for key, copies in sorted(grouped.items()):
        uri, sha, revision, origin = key
        chosen = sorted(copies, key=lambda item: (item.title.casefold(), item.source_id))[0]
        claims = {
            (claim.claim_id, claim.stance.value, claim.excerpt, claim.location): claim
            for source in copies for claim in source.claims
        }
        classes = {source.evidence_class for source in copies}
        evidence_class = next(iter(classes)) if len(classes) == 1 else EvidenceClass.UNKNOWN
        metadata: dict[str, str] = {}
        for source in copies:
            metadata.update({str(k): str(v) for k, v in source.metadata.items()})
        consolidated.append(SourceRecord(
            title=chosen.title,
            uri=uri,
            content=chosen.content,
            evidence_class=evidence_class,
            revision=revision,
            origin_digest=origin,
            claims=tuple(claims[k] for k in sorted(claims)),
            metadata=metadata,
            source_id="SRC-" + digest({"uri": uri, "sha": sha, "revision": revision, "origin": origin})[:16],
            content_sha256=sha,
        ))
    return tuple(consolidated)


def _report(agent_id: str, role: str, findings: Sequence[Finding], summary: str,
            metrics: Mapping[str, float] | None = None, work_items: Sequence[str] = ()) -> AgentReport:
    blockers = any(f.blocks_readiness for f in findings)
    warnings = any(f.severity in (Severity.WARNING, Severity.GAP) for f in findings)
    state = AgentOutcome.BLOCKED if blockers else AgentOutcome.WARN if warnings else AgentOutcome.PASS
    return AgentReport(agent_id, role, state, summary, tuple(findings), metrics or {}, tuple(work_items))


class SourceCoverageAgent:
    agent_id = "INV-RESEARCH-01"
    role = "SOURCE_DISCOVERY_AND_COVERAGE"

    def investigate(self, context: ResearchContext) -> AgentReport:
        findings: list[Finding] = []
        classified = [s for s in context.sources if s.evidence_class is not EvidenceClass.UNKNOWN]
        if len(context.sources) < context.request.min_source_records:
            findings.append(Finding("SOURCE_COUNT_BELOW_MINIMUM", Severity.BLOCKER,
                f"Expected at least {context.request.min_source_records} unique sources; found {len(context.sources)}.",
                tuple(s.source_id for s in context.sources), True))
        if sum(s.evidence_class in (EvidenceClass.CANONICAL_SOURCE, EvidenceClass.ARCHIVE,
                                    EvidenceClass.IMPLEMENTATION, EvidenceClass.TEST, EvidenceClass.RUNTIME)
               for s in context.sources) < context.request.min_primary_sources:
            findings.append(Finding("PRIMARY_EVIDENCE_BELOW_MINIMUM", Severity.BLOCKER,
                f"Expected at least {context.request.min_primary_sources} primary/implementation/test/runtime source(s).",
                tuple(s.source_id for s in context.sources), True))
        successful_query_ids = {o.query_id for o in context.outcomes if o.status == "OK"}
        required_missing = [q.query_id for q in context.queries if q.required and q.query_id not in successful_query_ids]
        if required_missing:
            findings.append(Finding("REQUIRED_QUERY_LANES_INCOMPLETE", Severity.BLOCKER,
                "Required query lanes had no successful provider result: " + ", ".join(required_missing), (), True))
        failed = [o for o in context.outcomes if o.status == "ERROR"]
        if failed:
            findings.append(Finding("PROVIDER_ERRORS", Severity.WARNING,
                f"{len(failed)} provider/query call(s) failed; the research corpus may be incomplete.",
                (), False))
        if not classified:
            findings.append(Finding("NO_CLASSIFIED_SOURCE", Severity.BLOCKER,
                "No source has a declared evidence class.", (), True))
        return _report(self.agent_id, self.role, findings,
            f"{len(context.sources)} unique source records; {len(classified)} classified.",
            {"unique_sources": float(len(context.sources)), "classified_sources": float(len(classified))},
            ("retry_failed_lanes", "classify_unknown_sources") if findings else ())


class NoveltyLineageAgent:
    agent_id = "INV-RESEARCH-02"
    role = "NOVELTY_AND_LINEAGE_INVESTIGATION"

    def investigate(self, context: ResearchContext) -> tuple[str, AgentReport]:
        request = context.request
        target = " ".join((request.candidate_title, request.candidate_summary))
        matches: list[tuple[float, CatalogEntry]] = []
        exact: list[CatalogEntry] = []
        for entry in request.catalog:
            phrases = (entry.name, entry.summary, *entry.aliases)
            if any(normalize(request.candidate_title) == normalize(p) for p in phrases if p.strip()):
                exact.append(entry)
            score = max((token_similarity(target, phrase) for phrase in phrases if phrase.strip()), default=0.0)
            if score >= 0.55:
                matches.append((score, entry))
        matches.sort(key=lambda item: (-item[0], item[1].innovation_id))
        refs = tuple(entry.innovation_id for _, entry in matches)
        if exact:
            state = "EXACT_CATALOG_MATCH"
            findings = [Finding("EXACT_CATALOG_MATCH", Severity.BLOCKER,
                "An exact title/alias match exists; link this candidate to the existing record instead of creating a duplicate.",
                tuple(entry.innovation_id for entry in exact), True)]
        elif matches:
            state = "POSSIBLE_OVERLAP"
            findings = [Finding("POSSIBLE_CATALOG_OVERLAP", Severity.GAP,
                "Lexical similarity found possible overlap. This is a review signal, not proof of duplication or novelty.",
                refs, True)]
        elif not request.catalog_coverage_complete:
            state = "CATALOG_INCOMPLETE"
            findings = [Finding("NOVELTY_NOT_ESTABLISHED", Severity.GAP,
                "No matching record was found in the supplied catalog, but catalog coverage is not certified complete.",
                (), True)]
        else:
            state = "NO_CATALOG_MATCH"
            findings = [Finding("NO_CATALOG_MATCH", Severity.INFO,
                "No lexical catalog match found. Novelty still requires technical comparison and independent review.",
                (), False)]
        report = _report(self.agent_id, self.role, findings,
            f"Novelty screen: {state}; {len(matches)} possible match(es).",
            {"possible_matches": float(len(matches))},
            ("resolve_lineage_and_aliases",) if matches or not request.catalog_coverage_complete else ())
        return state, report


class ClaimAdversaryAgent:
    agent_id = "INV-RESEARCH-03"
    role = "CLAIM_EVIDENCE_AND_COUNTEREVIDENCE"

    def investigate(self, context: ResearchContext) -> AgentReport:
        findings: list[Finding] = []
        all_evidence = [(source, item) for source in context.sources for item in source.claims]
        for claim in context.request.claims:
            evidence = [(source, item) for source, item in all_evidence if item.claim_id == claim.claim_id]
            supports = [(source, item) for source, item in evidence if item.stance is Stance.SUPPORTS]
            refutes = [(source, item) for source, item in evidence if item.stance is Stance.REFUTES]
            qualifies = [(source, item) for source, item in evidence if item.stance is Stance.QUALIFIES]
            if claim.required and not evidence:
                findings.append(Finding("CLAIM_WITHOUT_SOURCE_EVIDENCE", Severity.BLOCKER,
                    f"Required claim {claim.claim_id} has no source-bound evidence.", (), True))
                continue
            if supports and refutes:
                findings.append(Finding("UNRESOLVED_CLAIM_CONTRADICTION", Severity.BLOCKER,
                    f"Claim {claim.claim_id} has both supporting and refuting evidence; preserve both until adjudicated.",
                    tuple(sorted({s.source_id for s, _ in supports + refutes})), True))
            elif context.request.require_counterevidence and supports and not refutes and not qualifies:
                findings.append(Finding("COUNTEREVIDENCE_NOT_LOCATED", Severity.GAP,
                    f"Claim {claim.claim_id} has supporting evidence but no refuting/qualifying evidence was located. Absence is not disproof.",
                    tuple(sorted({s.source_id for s, _ in supports})), True))
            elif not supports and not refutes and qualifies:
                findings.append(Finding("CLAIM_ONLY_QUALIFIED", Severity.GAP,
                    f"Claim {claim.claim_id} is qualified but not directly supported or refuted.", 
                    tuple(sorted({s.source_id for s, _ in qualifies})), True))
        return _report(self.agent_id, self.role, findings,
            f"Reviewed {len(context.request.claims)} declared claim(s) against source-bound support/counterevidence.",
            {"declared_claims": float(len(context.request.claims)),
             "claim_evidence_records": float(len(all_evidence))},
            ("seek_counterevidence", "resolve_contradictions") if findings else ())


class EngineeringCompletenessAgent:
    agent_id = "INV-RESEARCH-04"
    role = "RESEARCH_TO_ENGINEERING_TRANSLATION"

    def investigate(self, context: ResearchContext) -> AgentReport:
        request = context.request
        missing = []
        for key in request.required_spec_fields:
            value = request.engineering_spec.get(key)
            if value is None or value == "" or value == [] or value == {} or value == ():
                missing.append(key)
        findings = [Finding("ENGINEERING_SPEC_FIELD_MISSING", Severity.GAP,
            "Missing or empty engineering contract fields: " + ", ".join(missing), (), True)] if missing else []
        return _report(self.agent_id, self.role, findings,
            f"{len(request.required_spec_fields) - len(missing)}/{len(request.required_spec_fields)} required engineering fields supplied.",
            {"required_fields": float(len(request.required_spec_fields)),
             "missing_fields": float(len(missing))},
            tuple("specify:" + item for item in missing))


class EvidenceIntegrityAgent:
    agent_id = "INV-RESEARCH-05"
    role = "PROVENANCE_AND_SOURCE_INTEGRITY"

    def investigate(self, context: ResearchContext) -> AgentReport:
        findings: list[Finding] = []
        by_uri_revision: dict[tuple[str, str], set[str]] = {}
        known_ids = {source.source_id for source in context.sources}
        for source in context.sources:
            by_uri_revision.setdefault((source.uri.rstrip("/"), source.revision), set()).add(source.content_sha256)
            if source.content_sha256 != content_digest(source.content):
                findings.append(Finding("SOURCE_HASH_MISMATCH", Severity.BLOCKER,
                    f"Content digest mismatch for {source.source_id}.", (source.source_id,), True))
            for claim in source.claims:
                if not claim.excerpt.strip():
                    findings.append(Finding("EMPTY_EVIDENCE_EXCERPT", Severity.BLOCKER,
                        f"Empty excerpt in {source.source_id}.", (source.source_id,), True))
        for (uri, revision), hashes in by_uri_revision.items():
            if len(hashes) > 1:
                findings.append(Finding("SOURCE_REVISION_CONFLICT", Severity.BLOCKER,
                    f"The same source URI and revision has conflicting content: {uri} ({revision or 'unspecified revision'}).",
                    tuple(s.source_id for s in context.sources if s.uri.rstrip("/") == uri and s.revision == revision), True))
        dangling = [claim for source in context.sources for claim in source.claims if not source.source_id]
        if dangling:
            findings.append(Finding("SOURCE_ID_MISSING", Severity.BLOCKER,
                "Claim evidence has no stable source identity.", (), True))
        return _report(self.agent_id, self.role, findings,
            f"Checked content hashes and source URI/revision consistency across {len(known_ids)} source record(s).",
            {"source_records_checked": float(len(context.sources))})


class ResearchDecisionOrchestrator:
    """Run search lanes and independent analysis roles; never self-authorize promotion."""

    REQUIRED_PURPOSES = {
        QueryPurpose.DISCOVERY, QueryPurpose.NOVELTY, QueryPurpose.COUNTEREVIDENCE,
        QueryPurpose.IMPLEMENTATION, QueryPurpose.CONTRADICTION, QueryPurpose.FAILURE_ANALYSIS,
    }

    def run(self, request: ResearchRequest, providers: Sequence[SearchProvider]) -> ResearchBundle:
        queries = build_query_plan(request)
        raw_sources: list[SourceRecord] = []
        outcomes: list[SearchOutcome] = []
        for provider in sorted(providers, key=lambda p: p.provider_id):
            for query in queries:
                try:
                    returned = tuple(provider.search(query, request.scopes))
                    raw_sources.extend(returned)
                    outcomes.append(SearchOutcome(provider.provider_id, query.query_id, query.purpose,
                        "OK", tuple(s.source_id for s in returned)))
                except Exception as exc:  # provider failure is recorded, not mistaken for empty search
                    outcomes.append(SearchOutcome(provider.provider_id, query.query_id, query.purpose,
                        "ERROR", (), f"{type(exc).__name__}: {exc}"))
        sources = consolidate_sources(raw_sources)
        # Rewrite outcome refs through the stable consolidation ids.
        uri_lookup = {(s.uri.rstrip("/"), s.content_sha256, s.revision, s.origin_digest.lower()): s.source_id for s in sources}
        normalized_outcomes: list[SearchOutcome] = []
        for outcome in outcomes:
            old_refs = set(outcome.source_ids)
            refs = tuple(s.source_id for s in sources if any(
                original.source_id in old_refs and
                (original.uri.rstrip("/"), original.content_sha256, original.revision, original.origin_digest.lower())
                == (s.uri.rstrip("/"), s.content_sha256, s.revision, s.origin_digest.lower())
                for original in raw_sources
            ))
            normalized_outcomes.append(SearchOutcome(outcome.provider_id, outcome.query_id, outcome.purpose,
                outcome.status, tuple(sorted(set(refs))), outcome.error))
        context = ResearchContext(request, queries, sources, tuple(normalized_outcomes))

        coverage = SourceCoverageAgent().investigate(context)
        novelty_state, novelty = NoveltyLineageAgent().investigate(context)
        claims = ClaimAdversaryAgent().investigate(context)
        engineering = EngineeringCompletenessAgent().investigate(context)
        integrity = EvidenceIntegrityAgent().investigate(context)
        reports = (coverage, novelty, claims, engineering, integrity)

        blockers = [f for report in reports for f in report.findings if f.blocks_readiness and f.severity is Severity.BLOCKER]
        gaps = [f for report in reports for f in report.findings if f.blocks_readiness and f.severity is not Severity.BLOCKER]
        if blockers:
            decision_state = DecisionState.BLOCKED
        elif gaps or any(outcome.status == "ERROR" for outcome in normalized_outcomes):
            # Separate research incompleteness from engineering-spec incompleteness.
            research_gap_codes = {
                "SOURCE_COUNT_BELOW_MINIMUM", "PRIMARY_EVIDENCE_BELOW_MINIMUM",
                "REQUIRED_QUERY_LANES_INCOMPLETE", "NO_CLASSIFIED_SOURCE",
                "NOVELTY_NOT_ESTABLISHED", "POSSIBLE_CATALOG_OVERLAP",
                "COUNTEREVIDENCE_NOT_LOCATED", "CLAIM_ONLY_QUALIFIED",
            }
            if any(f.code in research_gap_codes for f in gaps) or any(o.status == "ERROR" for o in normalized_outcomes):
                decision_state = DecisionState.NEEDS_INVESTIGATION
            else:
                decision_state = DecisionState.ENGINEERING_GAPS
        else:
            decision_state = DecisionState.READY_FOR_ENGINEERING_REVIEW

        open_questions: list[str] = []
        next_actions: list[str] = []
        for report in reports:
            for finding in report.findings:
                if finding.blocks_readiness:
                    open_questions.append(f"{finding.code}: {finding.message}")
            next_actions.extend(report.work_items)
        if not providers:
            open_questions.append("No search providers were supplied; no live research was performed.")
            next_actions.append("Connect or inject GitHub, archive, web, and repository search adapters.")
            decision_state = DecisionState.NEEDS_INVESTIGATION
        # Deterministic order and uniqueness supports replay and diffing.
        open_questions = sorted(set(open_questions))
        next_actions = sorted(set(next_actions))
        bundle_seed = {
            "schema_version": SCHEMA_VERSION,
            "innovation_id": request.innovation_id,
            "mission": request.mission,
            "candidate_title": request.candidate_title,
            "sources": [asdict(s) for s in sources],
            "queries": [asdict(q) for q in queries],
            "outcomes": [asdict(o) for o in normalized_outcomes],
            "reports": [asdict(r) for r in reports],
            "decision_state": decision_state.value,
        }
        return ResearchBundle(
            schema_version=SCHEMA_VERSION,
            run_id="RSH-" + digest(bundle_seed)[:16],
            innovation_id=request.innovation_id,
            mission=request.mission,
            candidate_title=request.candidate_title,
            decision_state=decision_state,
            novelty_state=novelty_state,
            sources=sources,
            queries=queries,
            search_outcomes=tuple(normalized_outcomes),
            agent_reports=reports,
            open_questions=tuple(open_questions),
            next_actions=tuple(next_actions),
            promotion_authorized=False,
        )


__all__ = [
    "AgentOutcome", "AgentReport", "CatalogEntry", "ClaimEvidence", "DecisionState",
    "EvidenceClass", "Finding", "QueryPurpose", "ResearchBundle", "ResearchClaim",
    "ResearchDecisionOrchestrator", "ResearchQuery", "ResearchRequest", "SearchOutcome",
    "SearchProvider", "Severity", "SourceRecord", "Stance", "build_query_plan",
    "consolidate_sources", "content_digest", "digest", "normalize", "token_similarity",
]
