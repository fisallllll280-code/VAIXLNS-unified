"""
Sovereign Constitution Layer
Highest authority - rules that cannot be broken
"""
from typing import Set, Dict, Any
from dataclasses import dataclass, field
from enum import Enum


class SecurityInvariant(str, Enum):
    """Security rules that must never be violated"""
    NO_PRIVILEGE_ESCALATION = "no_privilege_escalation"
    CAPABILITY_REQUIRED = "capability_required"
    AUTHORIZATION_REQUIRED = "authorization_required"
    IDENTITY_REQUIRED = "identity_required"
    AUDIT_REQUIRED = "audit_required"


class ExecutionInvariant(str, Enum):
    """Execution rules that must never be violated"""
    DETERMINISTIC_BOUNDARY = "deterministic_boundary"
    STATE_CONSISTENCY = "state_consistency"
    EVENT_ORDERING = "event_ordering"
    LEDGER_INTEGRITY = "ledger_integrity"
    NO_UNLOGGED_CHANGES = "no_unlogged_changes"


class GovernanceRule(str, Enum):
    """Governance rules that must be enforced"""
    POLICY_EVALUATION = "policy_evaluation"
    AUTHORIZATION_CHECK = "authorization_check"
    CAPABILITY_VERIFICATION = "capability_verification"
    DECISION_RECORDING = "decision_recording"


class DataRule(str, Enum):
    """Data integrity rules"""
    NO_DIRECT_STATE_MODIFICATION = "no_direct_state_modification"
    ONLY_EVENT_DRIVEN = "only_event_driven"
    IMMUTABLE_HISTORY = "immutable_history"
    VERSIONED_STATE = "versioned_state"


class DeterminismRule(str, Enum):
    """Determinism rules"""
    CAPTURED_EXTERNAL_INPUT = "captured_external_input"
    LOGGED_RANDOMNESS = "logged_randomness"
    NO_UNCAUGHT_IO = "no_uncaught_io"
    REPLAY_FIDELITY = "replay_fidelity"


@dataclass
class SovereignConstitution:
    """
    The highest authority in VAIXLNS.
    These rules cannot be broken without explicit override and audit.
    """
    
    # Identity Rules
    identity_required: bool = True
    mfa_for_critical_ops: bool = True
    session_timeout_seconds: int = 3600
    
    # Security Invariants
    security_invariants: Set[SecurityInvariant] = field(
        default_factory=lambda: {
            SecurityInvariant.NO_PRIVILEGE_ESCALATION,
            SecurityInvariant.CAPABILITY_REQUIRED,
            SecurityInvariant.AUTHORIZATION_REQUIRED,
            SecurityInvariant.IDENTITY_REQUIRED,
            SecurityInvariant.AUDIT_REQUIRED,
        }
    )
    
    # Execution Invariants
    execution_invariants: Set[ExecutionInvariant] = field(
        default_factory=lambda: {
            ExecutionInvariant.DETERMINISTIC_BOUNDARY,
            ExecutionInvariant.STATE_CONSISTENCY,
            ExecutionInvariant.EVENT_ORDERING,
            ExecutionInvariant.LEDGER_INTEGRITY,
            ExecutionInvariant.NO_UNLOGGED_CHANGES,
        }
    )
    
    # Governance Rules
    governance_rules: Set[GovernanceRule] = field(
        default_factory=lambda: {
            GovernanceRule.POLICY_EVALUATION,
            GovernanceRule.AUTHORIZATION_CHECK,
            GovernanceRule.CAPABILITY_VERIFICATION,
            GovernanceRule.DECISION_RECORDING,
        }
    )
    
    # Data Rules
    data_rules: Set[DataRule] = field(
        default_factory=lambda: {
            DataRule.NO_DIRECT_STATE_MODIFICATION,
            DataRule.ONLY_EVENT_DRIVEN,
            DataRule.IMMUTABLE_HISTORY,
            DataRule.VERSIONED_STATE,
        }
    )
    
    # Determinism Rules
    determinism_rules: Set[DeterminismRule] = field(
        default_factory=lambda: {
            DeterminismRule.CAPTURED_EXTERNAL_INPUT,
            DeterminismRule.LOGGED_RANDOMNESS,
            DeterminismRule.NO_UNCAUGHT_IO,
            DeterminismRule.REPLAY_FIDELITY,
        }
    )
    
    # Capability Rules
    least_privilege_required: bool = True
    capability_contract_required: bool = True
    unknown_capability_denied: bool = True
    
    # Safety Constraints
    max_execution_time_seconds: int = 300
    max_memory_mb: int = 2048
    max_ledger_events: int = 1_000_000
    
    # Evolution Constraints
    learning_requires_verification: bool = True
    learning_requires_approval: bool = True
    major_changes_require_review: bool = True
    
    def verify_compliance(self, rule_category: str) -> bool:
        """Verify that mandatory rules are in place"""
        if rule_category == "security":
            return len(self.security_invariants) > 0
        elif rule_category == "execution":
            return len(self.execution_invariants) > 0
        elif rule_category == "governance":
            return len(self.governance_rules) > 0
        elif rule_category == "data":
            return len(self.data_rules) > 0
        elif rule_category == "determinism":
            return len(self.determinism_rules) > 0
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Export constitution as dictionary"""
        return {
            "identity_required": self.identity_required,
            "mfa_for_critical_ops": self.mfa_for_critical_ops,
            "session_timeout_seconds": self.session_timeout_seconds,
            "security_invariants": [s.value for s in self.security_invariants],
            "execution_invariants": [e.value for e in self.execution_invariants],
            "governance_rules": [g.value for g in self.governance_rules],
            "data_rules": [d.value for d in self.data_rules],
            "determinism_rules": [dm.value for dm in self.determinism_rules],
            "least_privilege_required": self.least_privilege_required,
            "capability_contract_required": self.capability_contract_required,
            "unknown_capability_denied": self.unknown_capability_denied,
            "max_execution_time_seconds": self.max_execution_time_seconds,
            "max_memory_mb": self.max_memory_mb,
            "max_ledger_events": self.max_ledger_events,
            "learning_requires_verification": self.learning_requires_verification,
            "learning_requires_approval": self.learning_requires_approval,
            "major_changes_require_review": self.major_changes_require_review,
        }
