"""PKCE helpers for Neo Smart Blinds OAuth."""
import base64
import hashlib
import secrets
import string


CODE_VERIFIER_LENGTH = 128
CODE_VERIFIER_CHARS = string.ascii_letters + string.digits + "-._~"
CODE_CHALLENGE_METHOD = "S256"


def generate_code_verifier(length: int = CODE_VERIFIER_LENGTH) -> str:
    """Generate an RFC 7636 code verifier."""
    if length < 43 or length > 128:
        raise ValueError("code_verifier length must be between 43 and 128 characters")
    return "".join(secrets.choice(CODE_VERIFIER_CHARS) for _ in range(length))


def generate_code_challenge(code_verifier: str) -> str:
    """Generate an S256 code challenge for a verifier."""
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def generate_pkce_pair():
    """Generate a code verifier and matching S256 code challenge."""
    code_verifier = generate_code_verifier()
    return code_verifier, generate_code_challenge(code_verifier)
