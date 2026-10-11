import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from integrations.openai_vx_assistant import (
    CAPABILITIES,
    TOOLS,
    VXAssistantError,
    VXOpenAIAssistant,
    _base_url,
    _execute_readonly_tool,
)


class FakeResponses:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class OpenAIVXAssistantTests(unittest.TestCase):
    def test_only_fixed_readonly_tools_are_advertised(self):
        names = {tool["name"] for tool in TOOLS}
        self.assertEqual(names, {"vx_health", "vx_status", "vx_capabilities_list"})
        self.assertTrue(all(tool["type"] == "function" for tool in TOOLS))
        self.assertEqual(CAPABILITIES["mode"], "read-only")
        self.assertNotIn("shell", names)

    def test_capabilities_tool_rejects_arguments(self):
        self.assertEqual(
            _execute_readonly_tool("vx_capabilities_list", {}),
            CAPABILITIES,
        )
        with self.assertRaises(VXAssistantError):
            _execute_readonly_tool("vx_capabilities_list", {"path": "/etc/passwd"})

    def test_unknown_tool_fails_closed(self):
        with self.assertRaisesRegex(VXAssistantError, "TOOL_NOT_ALLOWED"):
            _execute_readonly_tool("execute_shell", {})

    def test_remote_http_is_rejected(self):
        with patch.dict(os.environ, {"VX_OPENAI_API_BASE_URL": "http://example.com"}):
            with self.assertRaisesRegex(VXAssistantError, "HTTPS"):
                _base_url()

    def test_remote_endpoint_requires_api_token(self):
        env = {
            "VX_OPENAI_API_BASE_URL": "https://vx.example.com",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(VXAssistantError, "TOKEN"):
                _base_url()

    def test_plain_text_response(self):
        fake = FakeResponses([SimpleNamespace(output=[], output_text="VX adapter ready.")])
        assistant = VXOpenAIAssistant(client=SimpleNamespace(responses=fake), model="test-model")
        self.assertEqual(assistant.respond("Summarize VX status."), "VX adapter ready.")
        self.assertEqual(fake.calls[0]["model"], "test-model")
        self.assertEqual(fake.calls[0]["tools"], TOOLS)

    def test_readonly_tool_call_is_bounded_and_returns_to_model(self):
        first = SimpleNamespace(
            id="resp-1",
            output=[SimpleNamespace(
                type="function_call",
                name="vx_capabilities_list",
                arguments="{}",
                call_id="call-1",
            )],
            output_text="",
        )
        second = SimpleNamespace(output=[], output_text="There are three read-only tools.")
        fake = FakeResponses([first, second])
        assistant = VXOpenAIAssistant(client=SimpleNamespace(responses=fake), max_tool_calls=1)
        self.assertEqual(assistant.respond("List available capabilities."), "There are three read-only tools.")
        self.assertEqual(fake.calls[1]["previous_response_id"], "resp-1")
        self.assertEqual(fake.calls[1]["input"][0]["call_id"], "call-1")

    def test_tool_call_budget_is_enforced(self):
        first = SimpleNamespace(
            id="resp-1",
            output=[SimpleNamespace(
                type="function_call",
                name="vx_capabilities_list",
                arguments="{}",
                call_id="call-1",
            )],
            output_text="",
        )
        fake = FakeResponses([first])
        assistant = VXOpenAIAssistant(client=SimpleNamespace(responses=fake), max_tool_calls=0)
        with self.assertRaisesRegex(VXAssistantError, "BUDGET"):
            assistant.respond("Use a tool.")


if __name__ == "__main__":
    unittest.main()
