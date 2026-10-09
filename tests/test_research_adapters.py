import base64
from pathlib import Path
import tempfile
import unittest

from innovation_control.research_fabric import QueryPurpose, ResearchQuery, EvidenceClass
from tools.research_adapters import GitHubRepositorySearchProvider, LocalRepositorySearchProvider


COMMIT = "a" * 40


class FakeGitHubTransport:
    def __init__(self, *, truncated=False):
        self.truncated = truncated
        self.calls = []
        self.file_content = "# Innovation execution\nSource evidence, novelty, and verifier contract.\n"

    def get_json(self, url, headers, timeout):
        self.calls.append((url, dict(headers), timeout))
        endpoint = url.replace("https://api.github.com", "")
        if endpoint == "/repos/acme/vaixlns":
            return {"default_branch": "main"}
        if endpoint == "/repos/acme/vaixlns/commits/main":
            return {"sha": COMMIT}
        if endpoint == f"/repos/acme/vaixlns/git/trees/{COMMIT}?recursive=1":
            return {
                "truncated": self.truncated,
                "tree": [
                    {"type": "blob", "path": "docs/innovation.md", "size": len(self.file_content), "sha": "1"},
                    {"type": "blob", "path": "README.md", "size": 20, "sha": "2"},
                    {"type": "tree", "path": "docs", "size": 0},
                    {"type": "blob", "path": ".env", "size": 9, "sha": "3"},
                ],
            }
        if endpoint == f"/repos/acme/vaixlns/contents/docs/innovation.md?ref={COMMIT}":
            return {
                "type": "file",
                "encoding": "base64",
                "size": len(self.file_content),
                "content": base64.b64encode(self.file_content.encode()).decode(),
            }
        if endpoint == f"/repos/acme/vaixlns/contents/README.md?ref={COMMIT}":
            value = "Repository overview".encode()
            return {"type": "file", "encoding": "base64", "size": len(value),
                    "content": base64.b64encode(value).decode()}
        raise AssertionError("Unexpected endpoint: " + endpoint)


class ResearchAdapterTests(unittest.TestCase):
    def query(self, text="innovation execution verification"):
        return ResearchQuery("Q-test", text, QueryPurpose.DISCOVERY, True)

    def test_local_provider_returns_scored_source_with_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs").mkdir()
            doc = root / "docs" / "innovation.md"
            doc.write_text("Innovation execution requires source evidence and replay verification.", encoding="utf-8")
            provider = LocalRepositorySearchProvider(root)
            sources = provider.search(self.query(), ())
            self.assertTrue(sources)
            self.assertEqual(sources[0].evidence_class, EvidenceClass.SECONDARY)
            self.assertEqual(len(sources[0].content_sha256), 64)
            self.assertEqual(sources[0].metadata["provider"], provider.provider_id)

    def test_local_provider_refuses_non_repository_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "missing"
            with self.assertRaisesRegex(ValueError, "LOCAL_REPOSITORY_ROOT_MUST_BE_DIRECTORY"):
                LocalRepositorySearchProvider(root)

    def test_github_provider_is_pinned_to_commit_and_content_hashed(self):
        transport = FakeGitHubTransport()
        provider = GitHubRepositorySearchProvider(("acme/vaixlns",), token="test-token", transport=transport)
        records = provider.search(self.query(), ("acme/vaixlns",))
        self.assertTrue(records)
        self.assertTrue(records[0].uri.startswith(f"https://github.com/acme/vaixlns/blob/{COMMIT}/"))
        self.assertEqual(records[0].revision, COMMIT)
        self.assertEqual(len(records[0].content_sha256), 64)
        self.assertIn("Innovation execution", records[0].content)
        self.assertTrue(all(url.startswith("https://api.github.com/") for url, _, _ in transport.calls))
        self.assertTrue(all(headers.get("Authorization") == "Bearer test-token" for _, headers, _ in transport.calls))

    def test_github_provider_rejects_repository_not_in_allowlist_before_network(self):
        transport = FakeGitHubTransport()
        provider = GitHubRepositorySearchProvider(("acme/vaixlns",), transport=transport)
        with self.assertRaisesRegex(PermissionError, "GITHUB_REPOSITORY_NOT_ALLOWLISTED"):
            provider.search(self.query(), ("other/repo",))
        self.assertEqual(transport.calls, [])

    def test_github_provider_fails_closed_on_truncated_tree(self):
        transport = FakeGitHubTransport(truncated=True)
        provider = GitHubRepositorySearchProvider(("acme/vaixlns",), transport=transport)
        with self.assertRaisesRegex(RuntimeError, "GITHUB_TREE_TRUNCATED"):
            provider.search(self.query(), ("acme/vaixlns",))

    def test_github_provider_requires_explicit_allowlist(self):
        with self.assertRaisesRegex(ValueError, "EXPLICIT_GITHUB_REPOSITORY_ALLOWLIST_REQUIRED"):
            GitHubRepositorySearchProvider(())

    def test_github_provider_deduplicates_scopes(self):
        transport = FakeGitHubTransport()
        provider = GitHubRepositorySearchProvider(("acme/vaixlns",), transport=transport)
        provider.search(self.query(), ("acme/vaixlns", "acme/vaixlns"))
        self.assertEqual(sum("git/trees" in url for url, _, _ in transport.calls), 1)


if __name__ == "__main__":
    unittest.main()
