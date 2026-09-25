import unittest

from intelligence.mind_bridge import MissionDeliberator, OpenAIMindAdapter
from intelligence.multi_mind_orchestrator import Mind, Task


class FakeResponses:
    def create(self, **kwargs):
        class Response:
            id="resp-mind"
            output_text="specialist proposal"
        self.kwargs=kwargs
        return Response()


class FakeClient:
    def __init__(self):
        self.responses=FakeResponses()


class MindBridgeTests(unittest.TestCase):
    def test_selected_minds_use_role_and_context(self):
        adapter=OpenAIMindAdapter(
            adapter=__import__("intelligence.openai_responses_adapter", fromlist=["OpenAIResponsesAdapter"])
            .OpenAIResponsesAdapter(client=FakeClient(), model="test-model")
        )
        minds=[
            Mind("math","mathematics",["math"]),
            Mind("physics","physics",["physics"]),
            Mind("security","security",["security"]),
        ]
        deliberator=MissionDeliberator(minds,adapter)
        runs=deliberator.deliberate(
            Task("t1","solve coupled model","solve",{"domain":"four-domain"},["proof"]),
            ["math","physics"],
        )
        self.assertEqual([r.mind_id for r in runs],["math","physics"])
        self.assertTrue(all(r.result["status"]=="ok" for r in runs))
        self.assertEqual(len(deliberator.proposals(
            Task("t1","solve coupled model","solve"),runs
        )),2)


if __name__ == "__main__":
    unittest.main()
