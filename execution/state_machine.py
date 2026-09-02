"""
State Machine
Manages valid state transitions
"""
from typing import Dict, Set, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class State(str, Enum):
    """Valid system states"""
    INITIAL = "initial"
    BOOTING = "booting"
    INITIALIZING = "initializing"
    CHECKING = "checking"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    SAFE_MODE = "safe_mode"
    SHUTDOWN = "shutdown"


class Event(str, Enum):
    """Valid state transition events"""
    BOOT = "boot"
    INITIALIZE = "initialize"
    CHECK = "check"
    ACTIVATE = "activate"
    DEGRADE = "degrade"
    RECOVER = "recover"
    ENTER_SAFE_MODE = "enter_safe_mode"
    EXIT_SAFE_MODE = "exit_safe_mode"
    SHUTDOWN = "shutdown"
    FAIL = "fail"


@dataclass
class Transition:
    """State transition"""
    from_state: State
    to_state: State
    event: Event
    timestamp: datetime
    reason: str = ""


class StateMachine:
    """
    Manages system state with valid transitions.
    Ensures system can only move through valid states.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.current_state = State.INITIAL
        self.transitions: list[Transition] = []
        
        # Define valid transitions
        self.valid_transitions: Dict[State, Set[State]] = {
            State.INITIAL: {State.BOOTING},
            State.BOOTING: {State.INITIALIZING, State.SHUTDOWN},
            State.INITIALIZING: {State.CHECKING, State.SHUTDOWN},
            State.CHECKING: {State.READY, State.DEGRADED, State.SHUTDOWN},
            State.READY: {State.ACTIVE, State.DEGRADED, State.SHUTDOWN},
            State.ACTIVE: {State.DEGRADED, State.RECOVERING, State.SHUTDOWN},
            State.DEGRADED: {State.RECOVERING, State.SAFE_MODE, State.SHUTDOWN},
            State.RECOVERING: {State.READY, State.SAFE_MODE, State.SHUTDOWN},
            State.SAFE_MODE: {State.RECOVERING, State.SHUTDOWN},
            State.SHUTDOWN: set(),
        }
    
    def can_transition(self, event: Event) -> bool:
        """
        Check if event can cause a valid transition.
        """
        # Event to state mapping
        event_target: Dict[Event, State] = {
            Event.BOOT: State.BOOTING,
            Event.INITIALIZE: State.INITIALIZING,
            Event.CHECK: State.CHECKING,
            Event.ACTIVATE: State.ACTIVE,
            Event.DEGRADE: State.DEGRADED,
            Event.RECOVER: State.RECOVERING,
            Event.ENTER_SAFE_MODE: State.SAFE_MODE,
            Event.EXIT_SAFE_MODE: State.READY,
            Event.SHUTDOWN: State.SHUTDOWN,
            Event.FAIL: State.DEGRADED,
        }
        
        target = event_target.get(event)
        if not target:
            return False
        
        return target in self.valid_transitions.get(self.current_state, set())
    
    def transition(self, event: Event, reason: str = "") -> bool:
        """
        Attempt to transition to new state based on event.
        Returns: True if transition successful, False otherwise
        """
        if not self.can_transition(event):
            return False
        
        # Event to state mapping
        event_target: Dict[Event, State] = {
            Event.BOOT: State.BOOTING,
            Event.INITIALIZE: State.INITIALIZING,
            Event.CHECK: State.CHECKING,
            Event.ACTIVATE: State.ACTIVE,
            Event.DEGRADE: State.DEGRADED,
            Event.RECOVER: State.RECOVERING,
            Event.ENTER_SAFE_MODE: State.SAFE_MODE,
            Event.EXIT_SAFE_MODE: State.READY,
            Event.SHUTDOWN: State.SHUTDOWN,
            Event.FAIL: State.DEGRADED,
        }
        
        old_state = self.current_state
        new_state = event_target[event]
        
        # Record transition
        trans = Transition(
            from_state=old_state,
            to_state=new_state,
            event=event,
            timestamp=datetime.now(),
            reason=reason,
        )
        self.transitions.append(trans)
        
        # Update state
        self.current_state = new_state
        
        print(
            f"[{self.name}] {old_state.value} --({event.value})--> "
            f"{new_state.value} | {reason}"
        )
        
        return True
    
    def get_state(self) -> State:
        """Get current state"""
        return self.current_state
    
    def get_transitions_history(self) -> list[Transition]:
        """Get all transitions"""
        return self.transitions
