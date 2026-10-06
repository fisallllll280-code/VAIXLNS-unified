import unittest
from closure.operational_closure import IntentCompiler,IdempotencyStore,readiness,EvolutionGovernor,MCPTrustRegistry,ToolRecord,detect_change

class ClosureKernelTests(unittest.TestCase):
    def test_intent_compiler_is_deterministic(self):
        c=IntentCompiler(); a=c.compile("i","actor","cap",{"x":1},["safe"]); b=c.compile("i","actor","cap",{"x":1},["safe"]); self.assertEqual(a.digest,b.digest)
    def test_idempotency(self):
        s=IdempotencyStore(); calls=[]; self.assertEqual(s.get_or_run("k",lambda:calls.append(1) or 7),7); self.assertEqual(s.get_or_run("k",lambda:calls.append(1) or 9),7); self.assertEqual(calls,[1])
    def test_readiness_requires_evidence(self):
        self.assertFalse(readiness("x",{"boot":True}).final); self.assertTrue(readiness("x",{"boot":True},["ci"]).final)
    def test_evolution_fails_closed(self): self.assertFalse(EvolutionGovernor().admit("x",True,True,False,["a"]).allowed)
    def test_mcp_least_privilege(self):
        r=MCPTrustRegistry(); r.register(ToolRecord("tool","server",("read",),True,"healthy","digest")); self.assertTrue(r.authorize("server","tool","read")); self.assertFalse(r.authorize("server","tool","write"))
    def test_change_detection(self):
        changed,h=detect_change(None,{"rev":1}); self.assertTrue(changed); changed,_=detect_change(h,{"rev":1}); self.assertFalse(changed); changed,_=detect_change(h,{"rev":2}); self.assertTrue(changed)
if __name__=="__main__": unittest.main()
