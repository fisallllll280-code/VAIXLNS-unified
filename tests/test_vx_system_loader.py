import hashlib
import unittest

from vx.system_loader import LoaderError, VXSystemLoader, validate_manifest


def manifest_for(payload: bytes):
    return {
        "schema_version": "1.0",
        "system_id": "ubuntu-24.04-amd64",
        "version": "24.04",
        "display_name": "Ubuntu 24.04 LTS (example metadata only)",
        "target": {
            "os": "linux",
            "architectures": ["x86_64"],
            "firmware": ["uefi"],
        },
        "install_policy": {
            "mode": "plan_only",
            "require_human_approval": True,
            "network_enabled": False,
            "execute_install": False,
        },
        "artifacts": [{
            "artifact_id": "ubuntu-image",
            "kind": "os_image",
            "uri": "https://releases.ubuntu.com/24.04/example.iso",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "signature": {
                "algorithm": "ed25519",
                "signer_id": "example-key-not-enrolled",
                "value": "TEST-ONLY-NOT-A-REAL-SIGNATURE",
            },
        }],
    }


class VXSystemLoaderTests(unittest.TestCase):
    def test_manifest_accepts_allowlisted_https_artifact(self):
        self.assertEqual(len(validate_manifest(manifest_for(b"image"))), 1)

    def test_rejects_http(self):
        data = manifest_for(b"image")
        data["artifacts"][0]["uri"] = "http://releases.ubuntu.com/image.iso"
        with self.assertRaises(LoaderError):
            validate_manifest(data)

    def test_rejects_unlisted_host(self):
        data = manifest_for(b"image")
        data["artifacts"][0]["uri"] = "https://example.invalid/image.iso"
        with self.assertRaises(LoaderError):
            validate_manifest(data)

    def test_rejects_path_credentials_and_fragment(self):
        data = manifest_for(b"image")
        data["artifacts"][0]["uri"] = "https://user:pass@releases.ubuntu.com/image.iso#x"
        with self.assertRaises(LoaderError):
            validate_manifest(data)

    def test_rejects_duplicate_artifact_ids(self):
        data = manifest_for(b"image")
        data["artifacts"].append(dict(data["artifacts"][0]))
        with self.assertRaises(LoaderError):
            validate_manifest(data)

    def test_requires_plan_only_and_human_approval(self):
        data = manifest_for(b"image")
        data["install_policy"]["require_human_approval"] = False
        with self.assertRaises(LoaderError):
            validate_manifest(data)

    def test_rejects_network_and_install_execution(self):
        data = manifest_for(b"image")
        data["install_policy"]["network_enabled"] = True
        with self.assertRaises(LoaderError):
            validate_manifest(data)
        data = manifest_for(b"image")
        data["install_policy"]["execute_install"] = True
        with self.assertRaises(LoaderError):
            validate_manifest(data)

    def test_hash_and_size_match_but_missing_signature_verifier_blocks(self):
        payload = b"known-test-image"
        plan = VXSystemLoader().inspect(manifest_for(payload), "ubuntu-image", payload)
        self.assertEqual(plan.status, "BLOCKED")
        self.assertTrue(plan.checks["sha256_matches"])
        self.assertTrue(plan.checks["size_matches"])
        self.assertFalse(plan.checks["signature_verified"])

    def test_independent_signature_verifier_allows_review_state_only(self):
        payload = b"known-test-image"
        verifier = lambda body, artifact: body == payload and artifact.signer_id == "example-key-not-enrolled"
        plan = VXSystemLoader(verifier).inspect(manifest_for(payload), "ubuntu-image", payload)
        self.assertEqual(plan.status, "VERIFIED_FOR_REVIEW")
        self.assertFalse(plan.checks["human_approval_present"])
        self.assertTrue(plan.checks["install_execution_disabled"])

    def test_wrong_hash_blocks(self):
        payload = b"actual"
        data = manifest_for(b"expected")
        plan = VXSystemLoader(lambda *_: True).inspect(data, "ubuntu-image", payload)
        self.assertEqual(plan.status, "BLOCKED")
        self.assertFalse(plan.checks["sha256_matches"])

    def test_unknown_artifact_is_rejected(self):
        payload = b"image"
        with self.assertRaises(LoaderError):
            VXSystemLoader().inspect(manifest_for(payload), "not-declared", payload)

    def test_install_is_unavailable(self):
        with self.assertRaisesRegex(LoaderError, "INSTALL_EXECUTION_DISABLED"):
            VXSystemLoader.install()


if __name__ == "__main__":
    unittest.main()
