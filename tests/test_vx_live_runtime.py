import json, unittest
from runtime.vx_live_state import LiveState
class LiveRuntimeTests(unittest.TestCase):
    def test_snapshot_is_serializable_and_bounded(self):
        s=LiveState(); s.update(status="LIVE",atomaton="OBSERVED",proof="ADMITTED",governance="READY",topology=["node-01"])
        s.publish("TEST")
        x=s.snapshot()
        json.dumps(x)
        self.assertEqual(x["state"]["status"],"LIVE")
        self.assertEqual(x["events"][-1]["event"],"TEST")
if __name__=="__main__": unittest.main()
