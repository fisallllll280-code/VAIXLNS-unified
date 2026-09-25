import tempfile
import unittest
from pathlib import Path

from nexus.typed_graph import CanonicalNexus, Entity
from simulation.runtime import EulerBackend, SimulationCase, SimulationRegistry
from memory.durable_fabric import DurableMemoryFabric


class SystemBridgeTests(unittest.TestCase):
    def test_typed_nexus_relations_are_first_class(self):
        nx=CanonicalNexus()
        a=nx.add_entity(Entity("a","capability","solver"))
        b=nx.add_entity(Entity("b","simulation","physics"))
        rel=nx.relate(a.id,b.id,"ENABLES","solver enables simulation",("repo:VAIXLNS",))
        self.assertEqual(rel.target,"b")
        self.assertEqual(nx.neighbors("a")[0].id,"b")

    def test_deterministic_simulation_backend(self):
        reg=SimulationRegistry()
        reg.register(EulerBackend())
        case=SimulationCase("sim-1","physics",{"acceleration":1.0},(0.0,0.0),10,0.1)
        r1=reg.run("euler-reference",case)
        r2=reg.run("euler-reference",case)
        self.assertTrue(r1.success)
        self.assertEqual(r1.state,r2.state)
        self.assertTrue(r1.deterministic)

    def test_durable_memory_keeps_history(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"memory.jsonl"
            mem=DurableMemoryFabric(path)
            mem.write("m1",{"value":3},["source:a"])
            mem.branch("m2","m1",{"value":4},["experiment:b"])
            mem.invalidate("m1","superseded")
            events=mem.events()
            self.assertEqual([e.event_type for e in events],["write","branch","invalidate"])
            self.assertEqual(events[1].payload["parent_id"],"m1")


if __name__ == "__main__":
    unittest.main()
