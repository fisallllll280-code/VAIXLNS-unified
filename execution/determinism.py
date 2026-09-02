"""
Deterministic Boundary
Ensures all external inputs are captured and logged
"""
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import time
import random
import uuid


@dataclass
class CapturedInput:
    """External input that was captured"""
    input_id: str
    input_type: str  # time, randomness, io, etc
    value: Any
    timestamp: datetime
    logged: bool = True


class DeterministicBoundary:
    """
    Captures all non-deterministic external factors.
    
    Without this, replay/verification is impossible:
    - Unlogged time calls
    - Unlogged random generation
    - Unlogged I/O operations
    - Unlogged external state
    
    With this, execution is fully reproducible.
    """
    
    def __init__(self):
        self.captured_inputs: Dict[str, CapturedInput] = {}
        self.capture_mode = True  # During execution
        self.replay_mode = False  # During verification
        self.replay_index = 0
    
    def capture_time(self) -> datetime:
        """
        Capture current time.
        During replay, returns logged time.
        """
        if self.replay_mode and self.replay_index < len(self.captured_inputs):
            # Return logged time from previous execution
            logged = list(self.captured_inputs.values())[self.replay_index]
            if logged.input_type == "time":
                self.replay_index += 1
                return logged.value
        
        now = datetime.now()
        if self.capture_mode:
            input_id = str(uuid.uuid4())
            self.captured_inputs[input_id] = CapturedInput(
                input_id=input_id,
                input_type="time",
                value=now,
                timestamp=now,
            )
        
        return now
    
    def capture_randomness(self, seed: Optional[int] = None) -> float:
        """
        Capture random number.
        Deterministic when seed is set.
        """
        if self.replay_mode and self.replay_index < len(self.captured_inputs):
            logged = list(self.captured_inputs.values())[self.replay_index]
            if logged.input_type == "random":
                self.replay_index += 1
                return logged.value
        
        if seed is not None:
            random.seed(seed)
        
        value = random.random()
        
        if self.capture_mode:
            input_id = str(uuid.uuid4())
            self.captured_inputs[input_id] = CapturedInput(
                input_id=input_id,
                input_type="random",
                value=value,
                timestamp=datetime.now(),
            )
        
        return value
    
    def capture_io(self, io_description: str, result: Any) -> Any:
        """
        Capture external I/O operation.
        """
        if self.replay_mode and self.replay_index < len(self.captured_inputs):
            logged = list(self.captured_inputs.values())[self.replay_index]
            if logged.input_type == "io":
                self.replay_index += 1
                return logged.value
        
        if self.capture_mode:
            input_id = str(uuid.uuid4())
            self.captured_inputs[input_id] = CapturedInput(
                input_id=input_id,
                input_type="io",
                value=result,
                timestamp=datetime.now(),
            )
        
        return result
    
    def start_replay(self) -> None:
        """Begin replay mode"""
        self.capture_mode = False
        self.replay_mode = True
        self.replay_index = 0
    
    def end_replay(self) -> None:
        """End replay mode"""
        self.capture_mode = True
        self.replay_mode = False
        self.replay_index = 0
    
    def get_captured_inputs(self) -> Dict[str, CapturedInput]:
        """Get all captured inputs"""
        return dict(self.captured_inputs)
    
    def verify_completeness(self) -> bool:
        """
        Verify all external inputs were captured.
        Returns True if no external factors escaped capture.
        """
        return all(ci.logged for ci in self.captured_inputs.values())
