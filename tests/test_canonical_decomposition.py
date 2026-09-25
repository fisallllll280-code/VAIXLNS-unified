import json
import tempfile
import unittest
from pathlib import Path

from integration.canonical_gap_audit import audit, report
from vx.mission_router import MissionRouter


class CanonicalDecompositionTests(unittest.TestCase):
    def test_gap_audit_preserves_declared_architecture(self):
        source = {
            "canonical_system": "VAIXLNS",
            "planes": [
                {"id": "nexus", "status": "partial"},
                {"id": "simulation", "status": "missing_runtime_bridge"},
                {"id": "interfaces", "status": "specified"}
            ]
        }
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "decomposition.json"
            p.write_text(json.dumps(source), encoding="utf-8")
            gaps = audit(p)
            self.assertEqual(len(gaps), 3)
            summary = report(p)
            self.assertEqual(summary["gap_count"], 3)
            self.assertIn("critical", summary["severity_counts"])

    def test_four_domain_room_selects_specialists_and_workspaces(self):
        router = MissionRouter("config/vx_mission_profiles.json")
        room = router.compose(
            "coupled aero-mechanical solver",
            ["mathematics", "physics", "engineering", "computing"],
            mode="solve",
        )
        self.assertEqual(len(room.domains), 4)
        self.assertIn("math", room.minds)
        self.assertIn("physics", room.minds)
        self.assertIn("topology_workspace", room.workspaces)
        self.assertIn("runtime_workspace", room.workspaces)
        self.assertIn("verify", room.gates)


if __name__ == "__main__":
    unittest.main()
