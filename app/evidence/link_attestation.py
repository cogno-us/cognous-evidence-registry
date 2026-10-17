"""
Link attestation verification (issue #23).

``POST /evidence/links`` previously stored any caller-chosen ``attested_by`` string.
Links now must carry a BitRep v1 attestation envelope, verified here with the vendored
BitRep verifier (``app.bitrep_verify``, contract: BitRep docs/VERIFICATION_CONTRACT_V1.md).

Profile (provisional, Index-side; BitRep treats ``statement_type`` as opaque):

* ``statement.statement_type`` == ``index.link.v1``
* ``statement.subject``        == the link's ``claim_id``
* ``statement.issuer``         == the link's ``attested_by``
* ``statement.content_digest`` == ``sha256:`` + SHA-256 of ``link_content_bytes(link)``
* ``statement.audience``       == audience of the operator trust snapshot (checked by BitRep)

"Verified" means issuer signature only, under the operator trust snapshot named by
``BITREP_TRUST_REGISTRY``, evaluated at the server's current time. It says nothing about
whether the link is true or the issuer is authoritative.
"""

import hashlib
import json
import time
from typing import Optional

from pydantic import ValidationError

from app.bitrep_verify.models import AttestationEnvelope, VerificationResult
from app.bitrep_verify.trust import TrustUnavailable, load_registry, strict_json
from app.bitrep_verify.verification import verify_attestation
from app.core.models import LinkCreate

LINK_STATEMENT_TYPE = "index.link.v1"


class AttestationError(Exception):
    """Attestation rejected; carries the HTTP status and a machine-readable reason."""

    def __init__(self, status_code: int, reason: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason
        self.message = message


def link_content_bytes(link: LinkCreate) -> bytes:
    """Canonical bytes committed to by ``content_digest`` (compact, sorted-key JSON, ASCII)."""
    body = {
        "claim_id": link.claim_id,
        "claim_id_2": link.claim_id_2,
        "evidence_id": link.evidence_id,
        "relation_type": link.relation_type.value,
        "strength": float(link.strength),
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def link_content_digest(link: LinkCreate) -> str:
    return "sha256:" + hashlib.sha256(link_content_bytes(link)).hexdigest()


def verify_link_attestation(
    link: LinkCreate, now: Optional[int] = None
) -> "tuple[AttestationEnvelope, VerificationResult]":
    """Verify ``link.attestation`` or raise AttestationError. Fails closed."""
    if not link.attestation:
        raise AttestationError(
            401,
            "attestation_required",
            "Links require a signed BitRep v1 attestation in the 'attestation' field; "
            "attested_by alone is not accepted.",
        )
    try:
        envelope = AttestationEnvelope.model_validate(
            strict_json(json.dumps(link.attestation).encode())
        )
    except (ValidationError, ValueError) as exc:
        raise AttestationError(
            422, "malformed_attestation", f"Attestation is not a valid BitRep v1 envelope: {exc}"
        ) from exc

    try:
        registry = load_registry()
        result = verify_attestation(envelope, registry, int(time.time()) if now is None else now)
    except TrustUnavailable as exc:
        raise AttestationError(
            503, "trust_unavailable", "Issuer trust snapshot is unavailable; refusing to accept links."
        ) from exc

    if result.outcome != "verified" or result.reason != "ok" or result.result_version != (
        "bitrep-verification/1"
    ):
        raise AttestationError(
            422, result.reason, f"Attestation rejected by BitRep verification: {result.reason}"
        )

    st = envelope.statement
    expected = {
        "statement_type": LINK_STATEMENT_TYPE,
        "subject": link.claim_id,
        "issuer": link.attested_by,
        "content_digest": link_content_digest(link),
    }
    for field, want in expected.items():
        if getattr(st, field) != want:
            raise AttestationError(
                422,
                "attestation_binding_mismatch",
                f"Attestation field '{field}' does not match the submitted link.",
            )
    return envelope, result
