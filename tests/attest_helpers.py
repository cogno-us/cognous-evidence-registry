"""Test-only helpers: sign BitRep v1 link attestations with a throwaway Ed25519 key."""

import base64
import json
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.bitrep_verify.models import SignedStatement
from app.bitrep_verify.verification import canonical_bytes
from app.core.models import LinkCreate
from app.evidence.link_attestation import LINK_STATEMENT_TYPE, link_content_digest

AUDIENCE = "index:test"
ISSUER = "issuer:alice"
KEY_ID = "key:1"


def b64pub(priv):
    from cryptography.hazmat.primitives import serialization as s

    return base64.b64encode(
        priv.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
    ).decode()


def make_registry(priv, now=None, issuer=ISSUER, key_id=KEY_ID, revoked_at=None, audience=AUDIENCE):
    now = int(time.time()) if now is None else now
    return {
        "registry_version": "bitrep-trust/1",
        "audience": audience,
        "published_at": now - 10_000,
        "valid_until": now + 100_000,
        "keys": [
            {
                "issuer": issuer,
                "key_id": key_id,
                "public_key": b64pub(priv),
                "valid_from": now - 10_000,
                "valid_until": now + 100_000,
                "revoked_at": revoked_at,
            }
        ],
    }


def sign_link(priv, link_fields, attestation_id="att-1", issuer=ISSUER, key_id=KEY_ID,
              now=None, audience=AUDIENCE, ttl=3600, issued_offset=-60, **overrides):
    """Return a full POST body (link fields + attested_by + signed attestation)."""
    now = int(time.time()) if now is None else now
    link = LinkCreate(attested_by=issuer, **link_fields)
    st = {
        "protocol_version": "bitrep-attestation/1",
        "algorithm": "Ed25519",
        "attestation_id": attestation_id,
        "issuer": issuer,
        "key_id": key_id,
        "subject": link.claim_id,
        "statement_type": LINK_STATEMENT_TYPE,
        "audience": audience,
        "content_digest": link_content_digest(link),
        "issued_at": now + issued_offset,
        "not_before": now + issued_offset,
        "expires_at": now + ttl,
    }
    st.update(overrides)
    sig = base64.b64encode(priv.sign(canonical_bytes(SignedStatement(**st)))).decode()
    body = dict(link_fields)
    body["attested_by"] = issuer
    body["attestation"] = {"statement": st, "signature": sig}
    return body


def new_key():
    return Ed25519PrivateKey.generate()


def write_registry(path, registry):
    path.write_text(json.dumps(registry))
    return str(path)
