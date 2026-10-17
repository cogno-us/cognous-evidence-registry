# Changelog

## Unreleased — V1 validation remediation (#23, #24)

- **Behaviour change (breaking for unsigned clients), #23:** `POST /api/v1/evidence/links`
  now requires a BitRep v1 `attestation` envelope bound to the link and verified against the
  operator trust snapshot (`BITREP_TRUST_REGISTRY`). Unsigned, forged, unknown-issuer, expired,
  revoked, wrong-audience or mismatched attestations get 401/422 and nothing is stored;
  no trust snapshot gives 503. `attested_by` must equal the signed issuer. Idempotent
  resubmission returns 200; attestation-id reuse for a different statement returns 409.
  Link responses gain optional `attestation_id` and `attestation_statement_digest`.
  Minimal BitRep verifier vendored at pin 5b5077d into `app/bitrep_verify/`.
  `EvidenceService.create_link` itself is unchanged and does not verify identity.
- **Behaviour change, #24:** `independence_score` counts distinct `source_identifier`
  (not evidence ids); five records from one source now give 0.2, not 1.0.
- `requires-python` raised to `>=3.10`. See docs/BITREP_LINK_ATTESTATION.md for migration.

## Unreleased — decentralized reference slice

- Add a non-upgradeable local EVM protocol for permissionless claim registration,
  evidence assertions/challenges, revision lineage and author lifecycle events.
- Add independent log reconstruction, direct-chain end-to-end tests and measured
  local transaction costs/receipt latency; no public chain deployment.
- Integrate pinned BitRep v1 via independent off-chain verification; explicitly
  leave contract-enforced issuer verification blocked, with no success stub.
- Disable destructive legacy claim PUT/DELETE (409), prevent returned object aliases
  mutating stored claims, and preserve alternate-store local status history.
- Correct implementation/assurance labels and document authority, privacy,
  availability, trust, chain-selection, migration and Governor decisions.
- Retain original MIT license and history. No adjacent repository modifications.
- F5b security repairs (legacy demo surfaces only): direct-run API binds to
  loopback; vote reputation must be finite; evidence/link stores and
  EvidenceService copy records in and out; supplied evidence checksums and link
  hashes must match the computed value; link weights must be finite non-bool
  numbers. Docs now state the legacy API is unauthenticated and loopback-only and
  correct SECURITY.md overclaims and reporting route.
