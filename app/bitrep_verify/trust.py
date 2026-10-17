# Vendored verbatim (imports rewritten only) from cogno-us/bitrep @ 5b5077dafde232a7801cb425c4efddcffb468723
# (MIT License, Copyright (c) 2025 BitRep Contributors). Implements docs/VERIFICATION_CONTRACT_V1.md.
# Do not edit; re-vendor from a new BitRep pin instead. See docs/BITREP_LINK_ATTESTATION.md.

"""Operator-managed trust snapshot. Public identity endpoints cannot enroll keys."""
import base64
import hashlib
import json
import os
from pathlib import Path
from typing import Annotated
from pydantic import Field, model_validator
from .models import Epoch, StrictModel, Token


class TrustUnavailable(Exception):
    """No usable operator trust configuration is available."""


def strict_json(raw: bytes) -> object:
    """Reject duplicate object members and non-JSON constants before parsing models."""
    def pairs(items: list) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate member')
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError('non-JSON constant')

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


class TrustedKey(StrictModel):
    issuer: Token
    key_id: Token
    public_key: str
    valid_from: Epoch
    valid_until: Epoch
    revoked_at: Epoch | None = None

    @model_validator(mode='after')
    def valid_key(self) -> 'TrustedKey':
        decoded = base64.b64decode(self.public_key, validate=True)
        if len(decoded) != 32 or base64.b64encode(decoded).decode() != self.public_key:
            raise ValueError('Expected canonical base64 Ed25519 public key')
        if self.valid_from >= self.valid_until:
            raise ValueError('Invalid key validity interval')
        return self


class TrustRegistry(StrictModel):
    registry_version: Annotated[str, Field(pattern=r'^bitrep-trust/1$')]
    audience: Token
    published_at: Epoch
    valid_until: Epoch
    keys: list[TrustedKey]

    @model_validator(mode='after')
    def unique_keys(self) -> 'TrustRegistry':
        ids = [(key.issuer, key.key_id) for key in self.keys]
        if len(ids) != len(set(ids)) or self.published_at >= self.valid_until:
            raise ValueError('Duplicate key ID or invalid snapshot interval')
        return self

    def fingerprint(self) -> str:
        raw = json.dumps(self.model_dump(), sort_keys=True, separators=(',', ':')).encode()
        return 'sha256:' + hashlib.sha256(raw).hexdigest()


def load_registry() -> TrustRegistry:
    """Read every request, failing closed; no network or caller-supplied trust roots."""
    try:
        path = os.environ['BITREP_TRUST_REGISTRY']
        raw = Path(path).read_bytes()
        return TrustRegistry.model_validate(strict_json(raw))
    except (KeyError, OSError, ValueError) as exc:
        raise TrustUnavailable('Trust registry missing or invalid') from exc
