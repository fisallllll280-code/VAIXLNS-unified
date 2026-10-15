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
        self.assertEqual(names, {
            "vx.health",
            "vx.status",
            "vx.offices.list",
            "vx.office.route.preview",
            "vx.capabilities.list",
        })
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

    def test_office_inventory_uses_fixed_authenticated_api_path(self):
        from integrations import mcp_server

        with patch.object(
            mcp_server, "_request_json", return_value={"status": "PROPOSAL_ONLY"}
        ) as request:
            result = _tool_result("vx.offices.list", {})
        self.assertIn("PROPOSAL_ONLY", result["content"][0]["text"])
        request.assert_called_once_with("/offices", method="GET")

    def test_office_route_preview_posts_only_typed_route_envelope(self):
        from integrations import mcp_server

        expected = {
            "status": "HOLD",
            "dispatch_allowed": False,
            "external_calls_made": False,
        }
        args = {"office_id": "OFF-TEST", "intent": "Review readiness"}
        with patch.object(mcp_server, "_request_json", return_value=expected) as request:
            result = _tool_result("vx.office.route.preview", args)
        self.assertIn('"dispatch_allowed": false', result["content"][0]["text"])
        request.assert_called_once_with(
            "/office-routing/preview",
            method="POST",
            payload=args,
        )

    def test_route_preview_rejects_extra_or_malformed_arguments(self):
        with self.assertRaises(BridgeError):
            _tool_result(
                "vx.office.route.preview",
                {"office_id": "OFF-TEST", "intent": "Review", "url": "https://example.com"},
            )
        with self.assertRaises(BridgeError):
            _tool_result("vx.office.route.preview", {"office_id": "", "intent": "Review"})


if __name__ == "__main__":
    unittest.main()
