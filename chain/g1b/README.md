# G1b: Verifier-attestation registration profile (development only)

Profile `cognous-registry-verifier-artifact-profile/1-dev`. **Development only, non-authorizing, unqualified.** It reuses the existing `IndexProtocol.sol`, `client.mjs`, `reconstruct.mjs` and the pinned BitRep adapter **unchanged**. It adds no contract, relation, evidence kind, admission rule or storage, and it does not change the G1 statement type/audience. Contract freeze: Hub #273 comment 6710722252.

## What it does
Given the G1 Verifier report (overall `abstain`) and a G1 signed envelope, it: verifies the envelope with the merged G1 profile under a per-run synthetic snapshot; registers one narrow claim and submits one evidence record on a **disposable loopback Ganache** chain; reconstructs the chain independently; and recomputes every commitment from the retained exact bytes.

Registered claim (exact UTF-8, no trailing newline): `The supplied artifact bytes with SHA-256 digest D contain a developer-format Verifier report whose declared overall outcome is ABSTAIN and whose declared Pack subject digest is P.`

| Registry field | Value |
|---|---|
| claim `content` | sha256 of the claim bytes; `parent` zero |
| evidence `content` | sha256 of the exact report bytes |
| evidence `manifest` | sha256 of the exact manifest bytes (sorted-key compact JSON; binds report sha256, **envelope sha256**, native `statement_digest`, type, audience, asserted Verifier revision, claim text/sha256/id, Pack subject digest, chain/contract/domain/code identity, submitter, relation text, nonclaims) |
| evidence `statement` | the native G1 statement digest (a different identity from the envelope digest); an **unverified** commitment, not on-chain signature admission |
| `relation` | `1`: the bytes support the assertion about **their own content**; never the Verifier's assessment |

Transaction hashes, evidence id and block identity are in a separate observation record (`evidence/`), never committed.

## Trust boundary of the signature facts
The supported path is `run()` → `pythonVerify()` → native G1 verification → `assess()`. `assess()` is an **internal composition/evaluation helper**: it takes a caller-supplied signature-verification object and only checks that object's report/envelope digests against the retained bytes. That binds the subject the object claims to describe; it does **not** authenticate the object. Facts supplied directly to `assess()` are therefore **not an independent trust root**, and `signature_valid_under_supplied_dev_snapshot` is only as reliable as the trusted development invocation that produced it. `assess()` is not an independent or authoritative verification interface; relying on it outside `run()` needs a separate interface decision.

## Outcomes (no aggregate success)
Separate facts: `artifact_identity_matched`, `signature_valid_under_supplied_dev_snapshot` (observer-relative `issuer_signature_only`), `registry_record_observed_provisional`.
`PRESENT_PROVISIONAL`: independent reconstruction finds the originally registered claim and evidence ids and all byte/commitment comparisons succeed. `MISMATCH`: record found, a comparison fails. `UNKNOWN`: no confirmed record (unacknowledged write, RPC error, reconstruction error, missing retained bytes); **writes are never retried**; a duplicate revert is never read as inclusion. `REFUSED`: before any write (overall not `abstain`, malformed input, signature not valid under the snapshot).

## Run (disposable, local)
`node --test g1b/spot_checks.test.mjs` from `chain/` after `npm ci`, with `PYTHON` (pydantic + cryptography), `BITREP_ROOT` (git checkout holding BitRep `981036c3` objects), `G1_ROOT` (Attestation checkout at `b7d23dc7`, whose two G1 files are verified by git blob id before use) and optional `G1B_EVIDENCE_DIR`. `npm test` remains the intentional relocation notice.

## Not established
Durable custody, consensus finality, authority, that execution occurred or was independently verified, Evidence Pack genuineness, producer identity, Verifier correctness. The signature is **not chain/domain-bound**; the snapshot fingerprint is submitter-supplied; the ganache wallets are public deterministic test keys. Statement type/audience adoption, chain-bound issuance, general evidence kinds and persistent custody remain Registry Governor decisions.

## Rollback
Delete `chain/g1b/`. Records written to a disposable chain vanish with it; on any persistent chain they could not be erased (not authorized).

## Evidence and review history (preserved)
- `evidence/run1/` original run of the three frozen checks (all passed) before review.
- `evidence/run2_after_review/` re-run after hardening for independent-review objections: **check 1 FAILED** because the hardening changed the `finality` field value the frozen assertion expects (`provisional`); preserved as original adverse evidence. The code (not the oracle) was corrected.
- `evidence/run3_final/` final re-run of the same frozen checks (all passed).
- Independent read-only boundary review (not formal qualification) objections and resolutions are recorded in the PR and Hub #273.

## Known limits (not exercised by the three checks)
The altered-envelope and altered-manifest comparison branches, a post-broadcast timeout with a mined record, and `REFUSED` paths are implemented but not exercised; the claim-lifecycle and chain-identity comparisons are read-side only. Transitive imports of the blob-pinned G1 profile are limited to the already-authenticated BitRep modules and the standard library (not independently verified here).
