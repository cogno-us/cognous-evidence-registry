# Vendored verbatim (imports rewritten only) from cogno-us/bitrep @ 981036c315856c71207984797b0c4e48d3b3921d
# (MIT License, Copyright (c) 2025 BitRep Contributors). Implements docs/VERIFICATION_CONTRACT_V1.md.
# Do not edit; re-vendor from a new BitRep pin instead. See docs/BITREP_LINK_ATTESTATION.md.

"""Versioned signing bytes and current-time signature verification, without storage."""
import base64
import hashlib
import json
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .models import AttestationEnvelope, SignedStatement, VerificationResult
from .trust import TrustRegistry, TrustUnavailable

PROTOCOL_VERSION = 'bitrep-attestation/1'
DOMAIN = b'BitRep attestation v1\n'


def canonical_bytes(statement: SignedStatement) -> bytes:
    """ASCII-only v1 fields, compact sorted JSON, no normalization or excluded fields."""
    return DOMAIN + json.dumps(
        statement.model_dump(), sort_keys=True, separators=(',', ':'), ensure_ascii=True
    ).encode('ascii')


def statement_digest(statement: SignedStatement) -> str:
    return 'sha256:' + hashlib.sha256(canonical_bytes(statement)).hexdigest()


def verify_attestation(att: AttestationEnvelope, registry: TrustRegistry,
                       now: int) -> VerificationResult:
    """Evaluate against current trusted state. `now` is server-supplied, never wire input."""
    if not registry.published_at <= now < registry.valid_until:
        raise TrustUnavailable('Trust snapshot not current')
    statement = att.statement
    digest = statement_digest(statement)

    def result(reason: str) -> VerificationResult:
        valid = reason == 'ok'
        return VerificationResult(
            outcome='verified' if valid else 'rejected', reason=reason,
            evaluated_at=now, key_status_at=now, statement_digest=digest,
            trust_snapshot=registry.fingerprint(),
            assurance='issuer_signature_only' if valid else 'none',
        )

    if statement.protocol_version != PROTOCOL_VERSION:
        return result('unsupported_version')
    if statement.algorithm != 'Ed25519':
        return result('unsupported_algorithm')
    if statement.audience != registry.audience:
        return result('audience_mismatch')
    key = next((k for k in registry.keys
                if (k.issuer, k.key_id) == (statement.issuer, statement.key_id)), None)
    if key is None:
        return result('unknown_key')
    # Conservative compromise semantics: revocation rejects even backdated statements.
    if key.revoked_at is not None and now >= key.revoked_at:
        return result('key_revoked')
    if now < key.valid_from:
        return result('key_not_yet_valid')
    if now >= key.valid_until:
        return result('key_expired')
    if not key.valid_from <= statement.issued_at < key.valid_until:
        return result('issuance_outside_key_validity')
    if statement.issued_at > now or statement.not_before > now:
        return result('not_yet_valid')
    if now >= statement.expires_at:
        return result('attestation_expired')
    try:
        signature = base64.b64decode(att.signature, validate=True)
        if len(signature) != 64 or base64.b64encode(signature).decode() != att.signature:
            return result('malformed_signature')
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key.public_key)).verify(
            signature, canonical_bytes(statement)
        )
    except (ValueError, InvalidSignature):
        return result('invalid_signature')
    return result('ok')
