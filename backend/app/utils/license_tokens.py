"""Ed25519 keys and JWTs for the Open Wearables Connect license server.

python-jose has no EdDSA, so tokens are compact JWS built here. The instance only signs;
the license server verifies. Token kinds are described in the Connect license protocol.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat

LICENSE_SERVER_AUDIENCE = "ow-license-server"
INSTANCE_TOKEN_LIFETIME_SECONDS = 60
SEAT_REQUEST_LIFETIME_SECONDS = 300


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def generate_private_key() -> str:
    """A new Ed25519 private key as base64url of its 32-byte seed."""
    seed = Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return _b64url(seed)


def public_key_of(private_key: str) -> str:
    """base64url of the raw public key, the form the license server registers."""
    key = Ed25519PrivateKey.from_private_bytes(_b64url_decode(private_key))
    return _b64url(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def generate_hmac_secret() -> str:
    return secrets.token_urlsafe(32)


def pseudo_user_id(hmac_secret: str, user_id: UUID) -> str:
    """Stable per-instance pseudonym of a user; the license server cannot reverse it."""
    digest = hmac.new(hmac_secret.encode(), str(user_id).encode(), hashlib.sha256).digest()
    return _b64url(digest)


def _sign(private_key: str, instance_id: UUID, token_use: str, lifetime: int, **claims: str) -> str:
    now = int(time.time())
    header = {"alg": "EdDSA", "typ": "JWT", "kid": str(instance_id)}
    payload = {
        "iss": str(instance_id),
        "aud": LICENSE_SERVER_AUDIENCE,
        "token_use": token_use,
        "iat": now,
        "exp": now + lifetime,
        **claims,
    }
    signing_input = ".".join(_b64url(json.dumps(part, separators=(",", ":")).encode()) for part in (header, payload))
    signature = Ed25519PrivateKey.from_private_bytes(_b64url_decode(private_key)).sign(signing_input.encode())
    return f"{signing_input}.{_b64url(signature)}"


def instance_token(private_key: str, instance_id: UUID) -> str:
    """Bearer token for the instance's own calls to the license server."""
    return _sign(private_key, instance_id, "instance", INSTANCE_TOKEN_LIFETIME_SECONDS)


def seat_request(private_key: str, instance_id: UUID, pseudonym: str) -> str:
    """Short-lived, single-use proof that this instance vouches for a user claiming an app seat."""
    return _sign(
        private_key,
        instance_id,
        "seat_request",
        SEAT_REQUEST_LIFETIME_SECONDS,
        sub=pseudonym,
        jti=secrets.token_urlsafe(16),
    )
