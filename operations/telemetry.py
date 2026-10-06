"""Vendor-neutral telemetry contracts.

The runtime can emit trace/metric/log records without requiring a collector.
An OpenTelemetry exporter can consume the normalized event shape later.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol


@dataclass(frozen=True)
class TelemetryEvent:
    name: str
    kind: str
    trace_id: str
    span_id: str
    timestamp: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


class TelemetrySink(Protocol):
    def emit(self, event: TelemetryEvent) -> None: ...


class InMemoryTelemetry:
    def __init__(self) -> None:
        self.events: list[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        self.events.append(event)

    def names(self) -> tuple[str, ...]:
        return tuple(event.name for event in self.events)


class JsonlTelemetry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: TelemetryEvent) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n")

    def read(self) -> tuple[TelemetryEvent, ...]:
        events: list[TelemetryEvent] = []
        if not self.path.exists():
            return ()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line:
                events.append(TelemetryEvent(**json.loads(line)))
        return tuple(events)


class Telemetry:
    def __init__(self, sinks: Iterable[TelemetrySink] = ()) -> None:
        self.sinks = tuple(sinks)

    def event(
        self,
        name: str,
        *,
        kind: str,
        trace_id: str,
        span_id: str,
        attributes: Mapping[str, Any] | None = None,
    ) -> TelemetryEvent:
        item = TelemetryEvent(
            name=name,
            kind=kind,
            trace_id=trace_id,
            span_id=span_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            attributes=dict(attributes or {}),
        )
        for sink in self.sinks:
            sink.emit(item)
        return item
