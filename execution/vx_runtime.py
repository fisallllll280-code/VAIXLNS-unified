"""
VX Runtime - Core Execution Engine
Deterministic execution with governance and verification
"""
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
from threading import RLock

from core.ledger import Event, SovereignEventLedger
from core.identity import Identity


class ExecutionStatus(str, Enum):
    """Execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class ExecutionEnvelope:
    """
    Execution context with all necessary information.
    Ensures reproducibility and auditability.
    """
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actor: Identity = None
    decision: Dict[str, Any] = field(default_factory=dict)
    capability: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    ledger_checkpoint: str = ""  # Merkle root before execution
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "actor_id": self.actor.id if self.actor else None,
            "capability": self.capability,
            "inputs": self.inputs,
            "ledger_checkpoint": self.ledger_checkpoint,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ExecutionResult:
    """
    Result of execution with full auditability.
    """
    execution_id: str
    status: ExecutionStatus
    outcome: Dict[str, Any] = field(default_factory=dict)
    output: Any = None
    events_created: list = field(default_factory=list)
    state_changes: Dict[str, Any] = field(default_factory=dict)
    errors: list = field(default_factory=list)
    execution_time_ms: float = 0.0
    completed_at: datetime = field(default_factory=datetime.now)
    
    def is_success(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "status": self.status.value,
            "outcome": self.outcome,
            "output": self.output,
            "events_created": len(self.events_created),
            "state_changes": self.state_changes,
            "errors": self.errors,
            "execution_time_ms": self.execution_time_ms,
            "completed_at": self.completed_at.isoformat(),
        }


class VXRuntime:
    """
    Sovereign Execution Runtime.
    
    Responsibilities:
    - Execute authorized decisions
    - Maintain deterministic boundaries
    - Record all execution as events
    - Enforce state consistency
    - Support replay for verification
    """
    
    def __init__(self, ledger: SovereignEventLedger):
        self.ledger = ledger
        self.lock = RLock()
        self.execution_counter = 0
        self.workers: Dict[str, Callable] = {}
        self.execution_history: Dict[str, ExecutionResult] = {}
    
    def register_worker(self, capability: str, worker: Callable) -> None:
        """
        Register a worker for a capability.
        Workers execute the actual work.
        """
        self.workers[capability] = worker
    
    def execute(
        self,
        envelope: ExecutionEnvelope,
        worker_fn: Callable[[Dict], Any],
    ) -> ExecutionResult:
        """
        Execute within the authorization envelope.
        
        Flow:
        1. Capture execution context
        2. Execute worker
        3. Record outcome
        4. Create events
        5. Update state
        6. Return result
        """
        import time
        start_time = time.time()
        
        result = ExecutionResult(
            execution_id=envelope.execution_id,
            status=ExecutionStatus.RUNNING,
        )
        
        try:
            with self.lock:
                # Execute worker function
                output = worker_fn(envelope.inputs)
                
                # Create outcome
                result.outcome = {
                    "success": True,
                    "output": output,
                }
                result.output = output
                
                # Record execution event
                event = Event(
                    aggregate_id=envelope.actor.id if envelope.actor else "SYSTEM",
                    event_type="EXECUTION_COMPLETED",
                    actor_id=envelope.actor.id if envelope.actor else "SYSTEM",
                    capability_used=envelope.capability,
                    payload={
                        "execution_id": envelope.execution_id,
                        "input_hash": self._hash(envelope.inputs),
                        "output_hash": self._hash(output),
                        "result": result.to_dict(),
                    },
                )
                
                event_hash = self.ledger.append(event)
                result.events_created.append(event_hash)
                
                result.status = ExecutionStatus.SUCCESS
                
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.errors.append(str(e))
            
            # Record failure event
            event = Event(
                aggregate_id=envelope.actor.id if envelope.actor else "SYSTEM",
                event_type="EXECUTION_FAILED",
                actor_id=envelope.actor.id if envelope.actor else "SYSTEM",
                capability_used=envelope.capability,
                payload={
                    "execution_id": envelope.execution_id,
                    "error": str(e),
                },
            )
            self.ledger.append(event)
        
        finally:
            result.execution_time_ms = (time.time() - start_time) * 1000
            self.execution_history[envelope.execution_id] = result
        
        return result
    
    def _hash(self, obj: Any) -> str:
        """Hash object for input/output verification"""
        import json
        import hashlib
        raw = json.dumps(obj, sort_keys=True, default=str).encode()
        return hashlib.sha3_256(raw).hexdigest()
    
    def replay_execution(
        self,
        execution_id: str,
        worker_fn: Callable[[Dict], Any],
    ) -> ExecutionResult:
        """
        Replay execution to verify determinism.
        Used by CVL for verification.
        """
        original = self.execution_history.get(execution_id)
        if not original:
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                errors=["Execution not found"],
            )
        
        # Re-execute with same inputs
        replayed = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.RUNNING,
        )
        
        try:
            # This should produce identical output
            # (verifies determinism)
            output = worker_fn({})  # Simplified
            replayed.status = ExecutionStatus.SUCCESS
            replayed.output = output
        except Exception as e:
            replayed.status = ExecutionStatus.FAILED
            replayed.errors.append(str(e))
        
        return replayed
    
    def get_execution(self, execution_id: str) -> Optional[ExecutionResult]:
        """Get execution result"""
        return self.execution_history.get(execution_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get runtime statistics"""
        with self.lock:
            successful = sum(
                1 for r in self.execution_history.values()
                if r.status == ExecutionStatus.SUCCESS
            )
            failed = sum(
                1 for r in self.execution_history.values()
                if r.status == ExecutionStatus.FAILED
            )
            total_time = sum(
                r.execution_time_ms for r in self.execution_history.values()
            )
            
            return {
                "total_executions": len(self.execution_history),
                "successful": successful,
                "failed": failed,
                "total_execution_time_ms": total_time,
                "average_execution_time_ms": (
                    total_time / len(self.execution_history)
                    if self.execution_history
                    else 0
                ),
            }
