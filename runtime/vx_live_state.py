"""Live in-process state for the VX-CONTINUUM dashboard."""
from __future__ import annotations
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

class LiveState:
    def __init__(self):
        self._lock=Lock()
        self.started_at=datetime.now(timezone.utc).isoformat()
        self.events=deque(maxlen=250)
        self.state={"system":"VAIXLNS/VX-CONTINUUM","status":"BOOTING","atomaton":"IDLE","proof":"PENDING","governance":"BLOCKED","topology":[]}
    def publish(self,event:str,**data:Any):
        with self._lock:
            item={"ts":datetime.now(timezone.utc).isoformat(),"event":event,**data}
            self.events.append(item)
    def update(self,**fields:Any):
        with self._lock: self.state.update(fields)
    def snapshot(self):
        with self._lock:
            return {"started_at":self.started_at,"state":dict(self.state),"events":list(self.events)}

LIVE=LiveState()
