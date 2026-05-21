"""Tests for PKCE helper functions."""
import base64
import hashlib
import string
import sys
import unittest
from pathlib import Path


COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "neosmartblinds"
sys.path.insert(0, str(COMPONENT_PATH))

from pkce import (  # noqa: E402
    CODE_CHALLENGE_METHOD,
    CODE_VERIFIER_CHARS,
    generate_code_challenge,
    generate_code_verifier,
    generate_pkce_pair,
)


class PKCETest(unittest.TestCase):
    def test_generate_code_verifier_uses_valid_length_and_charset(self):
        verifier = generate_code_verifier()

        self.assertEqual(len(verifier), 128)
        self.assertLessEqual(set(verifier), set(CODE_VERIFIER_CHARS))

    def test_generate_code_verifier_rejects_invalid_lengths(self):
        with self.assertRaises(ValueError):
            generate_code_verifier(42)

        with self.assertRaises(ValueError):
            generate_code_verifier(129)

    def test_generate_code_challenge_uses_s256_without_padding(self):
        verifier = string.ascii_letters + string.digits
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).decode("ascii").rstrip("=")

        self.assertEqual(generate_code_challenge(verifier), expected)
        self.assertNotIn("=", generate_code_challenge(verifier))

    def test_generate_pkce_pair_returns_matching_s256_values(self):
        verifier, challenge = generate_pkce_pair()

        self.assertEqual(CODE_CHALLENGE_METHOD, "S256")
        self.assertEqual(generate_code_challenge(verifier), challenge)


if __name__ == "__main__":
    unittest.main()
