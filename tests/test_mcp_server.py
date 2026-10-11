import unittest
from unittest.mock import patch

from integrations.mcp_server import BridgeError, _tool_result, handle_message


class ReadOnlyMCPBridgeTests(unittest.TestCase):
    def test_initialize_negotiates_protocol(self):
        response = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertEqual(response["result"]["protocolVersion"], "2024-11-05")
        self.assertIn("tools", response["result"]["capabilities"])

    def test_lists_only_read_only_tools(self):
        response = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {tool["name"] for tool in response["result"]["tools"]}
        self.assertEqual(names, {"vx.health", "vx.status", "vx.capabilities.list"})
        self.assertFalse(any("write" in name or "shell" in name for name in names))

    def test_notifications_have_no_response(self):
        self.assertIsNone(handle_message({
            "jsonrpc": "2.0", "method": "notifications/initialized"
        }))

    def test_unknown_method_is_json_rpc_error(self):
        response = handle_message({"jsonrpc": "2.0", "id": 3, "method": "execute_shell"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_tools_reject_arguments(self):
        response = handle_message({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "vx.health", "arguments": {"url": "https://example.com"}},
        })
        self.assertTrue(response["result"]["isError"])

    def test_capabilities_report_no_write_tools(self):
        result = _tool_result("vx.capabilities.list", {})
        self.assertIn("read-only", result["content"][0]["text"])
        self.assertIn("deploy", result["content"][0]["text"])

    def test_base_url_rejects_non_tls_remote(self):
        with patch.dict("os.environ", {"VX_MCP_API_BASE_URL": "http://example.com"}):
            from integrations.mcp_server import _base_url
            with self.assertRaises(BridgeError):
                _base_url()


if __name__ == "__main__":
    unittest.main()
