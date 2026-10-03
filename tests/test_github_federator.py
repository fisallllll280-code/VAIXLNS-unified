import unittest
from federation.github_federator import GitHubFederator

class GitHubFederatorTests(unittest.TestCase):
    def test_role_classification(self):
        role, signals = GitHubFederator._role({
            "name":"NEXENT","description":"research discovery runtime"
        })
        self.assertEqual(role, "canonical")
        self.assertIn("nexent", signals)

    def test_unclassified_repo_gets_organization_actions(self):
        actions = GitHubFederator._actions(
            {"name":"misc-project","description":"","has_issues":False},
            "unclassified",
        )
        self.assertIn("assign_canonical_role", actions)
        self.assertIn("scan_duplicate_capabilities", actions)
        self.assertIn("generate_interface_candidate", actions)

if __name__ == "__main__":
    unittest.main()
