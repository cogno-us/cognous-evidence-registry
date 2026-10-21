# Link attestation and source independence (issues #23, #24)

Status: remediation of two V1 validation findings. Cross-component adoption of the BitRep
verification contract is still **proposed** pending Governor review (see BitRep
`docs/VERIFICATION_CONTRACT_V1.md`). This is not a production-readiness claim.

## #23 - `POST /api/v1/evidence/links` verifies the attestor

Before: any `attested_by` string was stored. Now every link (claim-evidence and claim-claim)
must carry a BitRep v1 envelope in `attestation` (`{"statement": {...}, "signature": "..."}`),
verified before anything is stored.

### Design

- **Verifier**: the three BitRep modules the contract specifies (`models/verification.py`,
  `utils/trust.py`, `utils/verification.py`) are vendored unchanged except for imports into
  `app/bitrep_verify/`, from cogno-us/bitrep commit
  `981036c315856c71207984797b0c4e48d3b3921d` (the same pin used by
  `chain/python/bitrep_adapter.py`; MIT licence retained in `LICENSE.bitrep`). BitRep is not
  an installable package (top-level `models`/`utils`), so vendoring is the smallest honest
  option. `tests/test_link_attestation.py` checks the vendored code against BitRep's own
  published vector. Update by re-vendoring from a new pin, never by editing in place.
- **Trust**: operator-controlled snapshot file named by `BITREP_TRUST_REGISTRY` (BitRep
  contract), re-read on every request. Missing/invalid/expired snapshot fails closed (503).
  No issuer is trusted by default. Time is the server clock; no clock skew allowance.
- **Verified means issuer signature only**, under that snapshot, now. Not truth, not authority.

### Index-side link profile (provisional)

| Statement field | Required value |
|---|---|
| `statement_type` | `index.link.v1` |
| `subject` | the link's `claim_id` |
| `issuer` | the link's `attested_by` |
| `content_digest` | `sha256:` + SHA-256 of the canonical link bytes |
| `audience` | the trust snapshot's audience (checked by BitRep) |

Canonical link bytes: compact JSON, sorted keys, ASCII, of
`{"claim_id","claim_id_2","evidence_id","relation_type"(value),"strength"(float)}`
with absent targets as `null`. An attestation therefore cannot be reused for a different link.

### Responses

| Status | `detail.reason` | Meaning |
|---|---|---|
| 201 | | link stored (`attestation_id`, `attestation_statement_digest` added to the Link) |
| 200 | | same issuer + attestation id + statement resubmitted: existing link returned, nothing stored |
| 401 | `attestation_required` | no `attestation` (unsigned / `attested_by` only) |
| 422 | `malformed_attestation` | not a strict v1 envelope |
| 422 | BitRep reason | `unknown_key`, `invalid_signature`, `malformed_signature`, `attestation_expired`, `not_yet_valid`, `key_revoked`, `key_expired`, `key_not_yet_valid`, `issuance_outside_key_validity`, `audience_mismatch`, `unsupported_version`, `unsupported_algorithm` |
| 422 | `attestation_binding_mismatch` | statement type/subject/issuer/content digest does not match the submitted link |
| 409 | `attestation_id_conflict` | issuer reused an attestation id for a different signed statement |
| 503 | `trust_unavailable` | no usable trust snapshot; not a judgement on the link |

Not covered: the replay index is in-memory like the rest of this legacy service; issuer
enrollment, snapshot freshness/anti-rollback and authenticated transport remain deployment
decisions listed in the BitRep contract. Duplicate JSON members in the HTTP body are resolved
by the framework (last wins) before verification; what is verified is exactly what is stored.

## #24 - independence counts distinct sources

`independence_score = min(distinct_sources / 5, 1)` where a source is the evidence
`source_identifier` (whitespace-collapsed, case-folded), not the evidence id. Five records
sharing one source now score 0.2 (was 1.0). Weights, robustness and status thresholds are
unchanged; in particular duplicate links/records still add weight (known limit, not part of
this change).

## Migration

1. Provision issuer keys and a trust snapshot; set `BITREP_TRUST_REGISTRY`.
2. Clients must sign each link (statement type `index.link.v1`) and send it in `attestation`.
   `attested_by` stays required and must equal the signed issuer.
3. Previously stored links are not altered or re-verified.
4. `requires-python` is now `>=3.10` (vendored BitRep models use `X | None` annotations).
5. Epistemic status values change for claims whose evidence shares sources.
