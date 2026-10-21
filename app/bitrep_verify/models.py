# Vendored verbatim (imports rewritten only) from cogno-us/bitrep @ 981036c315856c71207984797b0c4e48d3b3921d
# (MIT License, Copyright (c) 2025 BitRep Contributors). Implements docs/VERIFICATION_CONTRACT_V1.md.
# Do not edit; re-vendor from a new BitRep pin instead. See docs/BITREP_LINK_ATTESTATION.md.

"""Strict wire models for the proposed BitRep v1 verification contract."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Token = Annotated[str, Field(min_length=1, max_length=256, pattern=r'^[!-~]+$')]
Epoch = Annotated[int, Field(ge=0, le=9007199254740991)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)


class SignedStatement(StrictModel):
    protocol_version: Token
    algorithm: Token
    attestation_id: Token
    issuer: Token
    key_id: Token
    subject: Token
    statement_type: Token
    audience: Token
    content_digest: Annotated[str, Field(pattern=r'^sha256:[0-9a-f]{64}$')]
    issued_at: Epoch
    not_before: Epoch
    expires_at: Epoch

    @model_validator(mode='after')
    def ordered_times(self) -> 'SignedStatement':
        if not self.issued_at <= self.not_before < self.expires_at:
            raise ValueError('Require issued_at <= not_before < expires_at')
        return self


class AttestationEnvelope(StrictModel):
    statement: SignedStatement
    signature: Annotated[str, Field(min_length=88, max_length=88)]


class VerificationResult(StrictModel):
    result_version: Literal['bitrep-verification/1'] = 'bitrep-verification/1'
    outcome: Literal['verified', 'rejected']
    reason: str
    evaluated_at: Epoch
    statement_digest: str | None = None
    trust_snapshot: str | None = None
    key_status_at: Epoch
    assurance: Literal['issuer_signature_only', 'none']
