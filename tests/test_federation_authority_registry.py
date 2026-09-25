import unittest

from core.identity import Identity, Permission
from core.sovereign_constitution import SovereignConstitution
from governance.authority_contract import ConstitutionAuthorizer
from intelligence.model_registry import CapabilityRegistry, ModelSpec, ToolSpec
from interface.manifest import InterfaceFactory
from operations.reconciliation import Reconciler
from adapters.github_federation import GitHubFederationAdapter


class FederationAuthorityRegistryTests(unittest.TestCase):
    def test_authority_contract(self):
        actor=Identity("a","test","system",{Permission.EXECUTE},{"build"})
        decision=ConstitutionAuthorizer(SovereignConstitution()).decide(actor,"build")
        self.assertTrue(decision.allowed)
        actor.revoke_capability("build")
        self.assertFalse(ConstitutionAuthorizer(SovereignConstitution()).decide(actor,"build").allowed)

    def test_model_and_tool_registry(self):
        reg=CapabilityRegistry()
        reg.register_model(ModelSpec("gpt-5.6-luna","openai",("reasoning","general"),1050000))
        reg.register_tool(ToolSpec("github","mcp",("repository","code"),"high"))
        self.assertTrue(reg.models_for("reasoning"))
        self.assertEqual(reg.tools_for("repository")[0].id,"github")

    def test_interface_factory(self):
        ui=InterfaceFactory().build("four-domain mission",["mathematics","physics","engineering","computing"])
        self.assertIn("equations",ui.panels)
        self.assertIn("topology",ui.panels)
        self.assertIn("code",ui.panels)
        self.assertIn("execute",ui.controls)

    def test_github_adapter_requires_runtime_token(self):
        adapter=GitHubFederationAdapter(token=None)
        self.assertFalse(adapter.configured)
        with self.assertRaisesRegex(RuntimeError, "GITHUB_TOKEN_NOT_CONFIGURED"):
            adapter.repository_metadata("fisallllll280-code/VAIXLNS")

    def test_reconciliation(self):
        state={"ready":False}
        actions=[]
        def observe():
            return dict(state)
        def converge(key,value):
            actions.append((key,value))
            state[key]=value
            return f"set:{key}"
        result=Reconciler(observe,converge).run_once({"ready":True})
        self.assertTrue(result.converged)
        self.assertEqual(actions,[("ready",True)])


if __name__ == "__main__":
    unittest.main()
