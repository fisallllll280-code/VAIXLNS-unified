"""Resilient multi-destination delivery for VX.

This module provides bounded retries, per-destination circuit breakers,
health probes, and fan-out delivery. Network-specific MCP/HTTP/WebSocket
adapters are injected by callers; this module does not claim to create a
network connection by itself.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Lock
from time import monotonic, sleep
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class Destination:
    destination_id: str
    endpoint: str
    enabled: bool = True


@dataclass(frozen=True)
class DeliveryResult:
    destination_id: str
    delivered: bool
    attempts: int
    status: str
    error: str | None = None


@dataclass(frozen=True)
class BroadcastReport:
    idempotency_key: str
    results: tuple[DeliveryResult, ...]

    @property
    def delivered(self) -> int:
        return sum(result.delivered for result in self.results)

    @property
    def failed(self) -> int:
        return len(self.results) - self.delivered

    @property
    def complete(self) -> bool:
        return bool(self.results) and self.failed == 0


class CircuitBreaker:
    """Small thread-safe breaker: CLOSED -> OPEN -> HALF_OPEN."""

    def __init__(self, failure_threshold: int = 3, reset_after: float = 15.0):
        if failure_threshold < 1 or reset_after < 0:
            raise ValueError("invalid circuit-breaker settings")
        self.failure_threshold = failure_threshold
        self.reset_after = reset_after
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = Lock()

    def allow_request(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return True
            if monotonic() - self._opened_at >= self.reset_after:
                # Permit a probe request. A failed probe re-opens the circuit.
                self._opened_at = None
                self._failures = self.failure_threshold - 1
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = monotonic()


Sender = Callable[[Destination, Any, str], Any]
HealthProbe = Callable[[Destination], bool]


class VXResilientMultipathPipeline:
    """Fan-out to independent destinations; partial failures remain visible."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        base_backoff: float = 0.1,
        failure_threshold: int = 3,
        breaker_reset_after: float = 15.0,
        max_workers: int = 8,
    ) -> None:
        if max_attempts < 1 or base_backoff < 0 or max_workers < 1:
            raise ValueError("invalid retry or concurrency settings")
        self.max_attempts = max_attempts
        self.base_backoff = base_backoff
        self.failure_threshold = failure_threshold
        self.breaker_reset_after = breaker_reset_after
        self.max_workers = max_workers
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = Lock()

    def _breaker_for(self, destination_id: str) -> CircuitBreaker:
        with self._lock:
            if destination_id not in self._breakers:
                self._breakers[destination_id] = CircuitBreaker(
                    self.failure_threshold, self.breaker_reset_after
                )
            return self._breakers[destination_id]

    def _deliver(
        self,
        destination: Destination,
        payload: Any,
        idempotency_key: str,
        sender: Sender,
        health_probe: HealthProbe | None,
    ) -> DeliveryResult:
        if not destination.enabled:
            return DeliveryResult(destination.destination_id, False, 0, "DISABLED")

        breaker = self._breaker_for(destination.destination_id)
        if not breaker.allow_request():
            return DeliveryResult(
                destination.destination_id, False, 0, "CIRCUIT_OPEN",
                "Destination temporarily suppressed after repeated failures",
            )

        last_error: str | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                if health_probe is not None and not health_probe(destination):
                    raise ConnectionError("health probe failed")
                response = sender(destination, payload, idempotency_key)
                if response is False:
                    raise RuntimeError("sender reported unsuccessful delivery")
                breaker.record_success()
                return DeliveryResult(
                    destination.destination_id, True, attempt, "DELIVERED"
                )
            except Exception as exc:  # adapter errors are converted into report data
                last_error = f"{type(exc).__name__}: {exc}"
                breaker.record_failure()
                if attempt < self.max_attempts:
                    sleep(self.base_backoff * (2 ** (attempt - 1)))

        return DeliveryResult(
            destination.destination_id, False, self.max_attempts,
            "FAILED", last_error,
        )

    def broadcast(
        self,
        *,
        destinations: Iterable[Destination],
        payload: Any,
        idempotency_key: str,
        sender: Sender,
        health_probe: HealthProbe | None = None,
    ) -> BroadcastReport:
        """Deliver independently to every enabled destination concurrently.

        The sender must use idempotency_key with the remote service where
        supported. A failed destination does not cancel delivery to others.
        """
        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        targets = tuple(destinations)
        if len({target.destination_id for target in targets}) != len(targets):
            raise ValueError("destination_id values must be unique per broadcast")
        if not targets:
            return BroadcastReport(idempotency_key, ())

        results: list[DeliveryResult] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(targets))) as pool:
            futures = {
                pool.submit(
                    self._deliver, target, payload, idempotency_key,
                    sender, health_probe,
                ): target.destination_id
                for target in targets
            }
            for future in as_completed(futures):
                results.append(future.result())

        results.sort(key=lambda item: item.destination_id)
        return BroadcastReport(idempotency_key, tuple(results))
