"""
Sovereign Event Ledger
Append-only, immutable, Merkle-verified history
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import hashlib
from threading import RLock
import uuid


@dataclass
class Event:
    """Single event in the ledger"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_id: str = ""  # Entity this event belongs to
    event_type: str = ""  # Type of event (INIT, STATE_CHANGE, etc)
    sequence: int = 0  # Sequence number
    timestamp: datetime = field(default_factory=datetime.now)
    actor_id: str = ""  # Who triggered this
    capability_used: str = ""  # Which capability was used
    payload: Dict[str, Any] = field(default_factory=dict)
    input_hash: str = ""  # Hash of input
    output_hash: str = ""  # Hash of output
    previous_hash: str = ""  # Hash of previous event (Merkle chain)
    event_hash: str = ""  # This event's hash
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


class SovereignEventLedger:
    """
    The single source of truth for system history.
    
    Properties:
    - Append-only: Events can only be added, never modified or removed
    - Immutable: Hash chain ensures integrity
    - Ordered: Events have timestamps and sequence numbers
    - Verifiable: Merkle root can be used for external proof
    - Temporal: Can reconstruct state at any point in time
    """
    
    def __init__(self):
        self.events: List[Event] = []
        self.lock = RLock()
        self.merkle_root: Optional[str] = None
        self.sequence_counter = 0
    
    def append(self, event: Event) -> str:
        """
        Append event to ledger.
        Returns: Event hash
        """
        with self.lock:
            # Set sequence number
            event.sequence = self.sequence_counter
            self.sequence_counter += 1
            
            # Set previous hash
            if self.events:
                event.previous_hash = self.events[-1].event_hash
            else:
                event.previous_hash = "GENESIS"
            
            # Calculate event hash
            event.event_hash = self._calculate_hash(event)
            
            # Append to ledger
            self.events.append(event)
            
            # Update merkle root
            self._update_merkle_root()
            
            return event.event_hash
    
    def _calculate_hash(self, event: Event) -> str:
        """Calculate SHA3-512 hash of event"""
        data = {
            "event_id": event.event_id,
            "aggregate_id": event.aggregate_id,
            "event_type": event.event_type,
            "sequence": event.sequence,
            "timestamp": event.timestamp.isoformat(),
            "actor_id": event.actor_id,
            "capability_used": event.capability_used,
            "payload": event.payload,
            "input_hash": event.input_hash,
            "output_hash": event.output_hash,
            "previous_hash": event.previous_hash,
        }
        raw = json.dumps(data, sort_keys=True, default=str).encode()
        return hashlib.sha3_512(raw).hexdigest()
    
    def _update_merkle_root(self) -> None:
        """Update merkle root based on all events"""
        if not self.events:
            self.merkle_root = None
            return
        
        hashes = [e.event_hash for e in self.events]
        self.merkle_root = self._merkle_root_from_hashes(hashes)
    
    def _merkle_root_from_hashes(self, hashes: List[str]) -> str:
        """Calculate merkle root from list of hashes"""
        if not hashes:
            return "EMPTY"
        
        layer = list(hashes)
        while len(layer) > 1:
            next_layer = []
            for i in range(0, len(layer), 2):
                left = layer[i]
                right = layer[i + 1] if i + 1 < len(layer) else layer[i]
                parent = hashlib.sha3_512(
                    (left + right).encode()
                ).hexdigest()
                next_layer.append(parent)
            layer = next_layer
        
        return layer[0]
    
    def verify_integrity(self) -> bool:
        """Verify ledger integrity using Merkle chain"""
        with self.lock:
            if not self.events:
                return True
            
            # Verify each event's previous hash
            for i, event in enumerate(self.events):
                if i == 0:
                    if event.previous_hash != "GENESIS":
                        return False
                else:
                    if event.previous_hash != self.events[i - 1].event_hash:
                        return False
                
                # Recalculate event hash
                calculated_hash = self._calculate_hash(event)
                if calculated_hash != event.event_hash:
                    return False
            
            # Verify merkle root
            hashes = [e.event_hash for e in self.events]
            calculated_root = self._merkle_root_from_hashes(hashes)
            return calculated_root == self.merkle_root
    
    def get_events(self, aggregate_id: str = "") -> List[Event]:
        """Get all events, optionally filtered by aggregate"""
        with self.lock:
            if aggregate_id:
                return [e for e in self.events if e.aggregate_id == aggregate_id]
            return list(self.events)
    
    def get_event_by_hash(self, event_hash: str) -> Optional[Event]:
        """Get event by hash"""
        with self.lock:
            for event in self.events:
                if event.event_hash == event_hash:
                    return event
            return None
    
    def reconstruct_state(self, aggregate_id: str, up_to_sequence: Optional[int] = None) -> Dict[str, Any]:
        """
        Reconstruct state of aggregate at a point in time.
        This is used for temporal queries and replay.
        """
        with self.lock:
            state = {}
            for event in self.events:
                if event.aggregate_id != aggregate_id:
                    continue
                if up_to_sequence is not None and event.sequence > up_to_sequence:
                    continue
                
                # Apply event to state (simple merge for now)
                if "state" in event.payload:
                    state.update(event.payload["state"])
            
            return state
    
    def get_state_at_time(self, aggregate_id: str, timestamp: datetime) -> Dict[str, Any]:
        """Get state at specific point in time"""
        with self.lock:
            state = {}
            for event in self.events:
                if event.aggregate_id != aggregate_id:
                    continue
                if event.timestamp > timestamp:
                    continue
                
                if "state" in event.payload:
                    state.update(event.payload["state"])
            
            return state
    
    def get_stats(self) -> Dict[str, Any]:
        """Get ledger statistics"""
        with self.lock:
            return {
                "total_events": len(self.events),
                "merkle_root": self.merkle_root,
                "integrity_verified": self.verify_integrity(),
                "first_event": self.events[0].timestamp.isoformat() if self.events else None,
                "last_event": self.events[-1].timestamp.isoformat() if self.events else None,
            }
