"""Optional OpenTelemetry bridge for VX traces and metrics."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

try:
    from opentelemetry import metrics, trace
except ImportError:  # optional dependency
    metrics = None  # type: ignore[assignment]
    trace = None  # type: ignore[assignment]


class VXTelemetry:
    def __init__(self, service_name: str = "vaixlns-vx") -> None:
        self.service_name = service_name
        self.tracer = trace.get_tracer(service_name) if trace else None
        self.meter = metrics.get_meter(service_name) if metrics else None

    @property
    def configured(self) -> bool:
        return self.tracer is not None and self.meter is not None

    @contextmanager
    def span(self, name: str) -> Iterator[object]:
        if not self.tracer:
            yield None
            return
        with self.tracer.start_as_current_span(name) as span:
            yield span
