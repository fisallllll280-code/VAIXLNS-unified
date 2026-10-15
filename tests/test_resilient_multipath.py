"""Tests for VX resilient multi-destination delivery."""
import unittest

from operations.resilient_multipath import (
    Destination,
    VXResilientMultipathPipeline,
)


class ResilientMultipathTests(unittest.TestCase):
    def setUp(self):
        self.destinations = [
            Destination("phone-a", "https://a.invalid/push"),
            Destination("phone-b", "https://b.invalid/push"),
            Destination("server-c", "https://c.invalid/events"),
        ]

    def test_fanout_delivers_to_all_destinations(self):
        seen = []

        def sender(destination, payload, key):
            seen.append((destination.destination_id, payload, key))
            return {"ok": True}

        pipeline = VXResilientMultipathPipeline(max_attempts=1, base_backoff=0)
        report = pipeline.broadcast(
            destinations=self.destinations,
            payload={"event": "alert"},
            idempotency_key="event-001",
            sender=sender,
        )

        self.assertTrue(report.complete)
        self.assertEqual(report.delivered, 3)
        self.assertEqual(len(seen), 3)
        self.assertTrue(all(item[2] == "event-001" for item in seen))

    def test_one_failed_destination_does_not_cancel_others(self):
        def sender(destination, payload, key):
            if destination.destination_id == "phone-b":
                raise ConnectionError("simulated outage")
            return True

        pipeline = VXResilientMultipathPipeline(max_attempts=1, base_backoff=0)
        report = pipeline.broadcast(
            destinations=self.destinations,
            payload="hello",
            idempotency_key="event-002",
            sender=sender,
        )
        by_id = {item.destination_id: item for item in report.results}
        self.assertTrue(by_id["phone-a"].delivered)
        self.assertFalse(by_id["phone-b"].delivered)
        self.assertTrue(by_id["server-c"].delivered)
        self.assertEqual(report.delivered, 2)
        self.assertEqual(report.failed, 1)

    def test_circuit_breaker_suppresses_repeatedly_failing_destination(self):
        def sender(destination, payload, key):
            raise ConnectionError("offline")

        pipeline = VXResilientMultipathPipeline(
            max_attempts=1, base_backoff=0, failure_threshold=1,
            breaker_reset_after=60,
        )
        first = pipeline.broadcast(
            destinations=[self.destinations[0]], payload="x",
            idempotency_key="event-003", sender=sender,
        )
        second = pipeline.broadcast(
            destinations=[self.destinations[0]], payload="x",
            idempotency_key="event-004", sender=sender,
        )
        self.assertEqual(first.results[0].status, "FAILED")
        self.assertEqual(second.results[0].status, "CIRCUIT_OPEN")
        self.assertEqual(second.results[0].attempts, 0)

    def test_health_probe_failure_is_reported_and_fanned_out(self):
        def sender(destination, payload, key):
            return True

        pipeline = VXResilientMultipathPipeline(max_attempts=1, base_backoff=0)
        report = pipeline.broadcast(
            destinations=self.destinations[:2],
            payload="x",
            idempotency_key="event-005",
            sender=sender,
            health_probe=lambda destination: destination.destination_id != "phone-a",
        )
        by_id = {item.destination_id: item for item in report.results}
        self.assertFalse(by_id["phone-a"].delivered)
        self.assertTrue(by_id["phone-b"].delivered)

    def test_requires_idempotency_key(self):
        pipeline = VXResilientMultipathPipeline(max_attempts=1)
        with self.assertRaises(ValueError):
            pipeline.broadcast(
                destinations=self.destinations, payload="x",
                idempotency_key=" ", sender=lambda *args: True,
            )


if __name__ == "__main__":
    unittest.main()
