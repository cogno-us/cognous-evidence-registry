# Validation — local run, 2026-10-05

This records executed tests, not production assurance. Index starting commit:
`3abba683c707ae95c7834036231ac55463cf1586`; BitRep pinned clean checkout:
`5b5077dafde232a7801cb425c4efddcffb468723`. Result commit is the PR head containing
this document (avoids a self-referential commit hash).

## Environment and commands

- Linux container, Node v24.19.0, Python 3.12, Ganache 7.9.2, ethers 6.16.0.
- solc `0.8.30+commit.73712a01.Emscripten.clang`, optimizer 200 runs, Shanghai EVM.
- Pydantic 2.13.5, cryptography 46.0.0, pytest 9.1.1.
- Loopback HTTP RPC, disposable in-process chain ID 31337; second chain 31338.
- Two independent clients share one local node; no application API, public network,
  multi-validator consensus, paid funds, real identity records or real evidence.
- Ganache's native µWS module is unavailable on this Node build; it used its JS
  fallback. Latency measurements include that fallback.

Executed from repository root or `chain/` as shown:

```bash
# repository root
python -m pytest -o addopts='' -q --disable-warnings
# 85 passed, 235 warnings, 0.60 seconds
python -m ruff check chain/python app/claims/service.py tests/test_claims.py
# All checks passed
# chain/ with BITREP_ROOT pointing to clean pinned external checkout
python python/test_bitrep.py
# 12 tests, OK (0.013 seconds on final standalone run)
npm test
# 20 tests passed, 0 failures, 0 skipped; 6069 ms final measured run
# 19 subtests plus the enclosing end-to-end test
```

An initial wider lint pass found pre-existing whitespace/exception-style issues in
`api/claim_layer.py` and FastAPI `Query` default B008 in `app/api/claims.py`; no
repository-wide lint pass is claimed. New adapter formatting/import issues found
then were fixed. Python warnings are legacy utcnow and dependency deprecations.
No tests failed in the executed initial or final test runs. No CI execution is
claimed by this local record; remote check status must be read separately.

## Executed blockchain cases

1. Register claim directly through chain; inspect author/content.
2. Duplicate claim rejected.
3. Empty content commitment / missing parent rejected.
4. Commit evidence, read it through independent indexer, reconstruct expected
   BitRep subject/audience/type/content/statement digest, verify with pinned code.
5. Duplicate evidence rejected.
6. Missing claim / invalid evidence relation rejected.
7. Independent wallet submits contradiction; lifecycle stays active (no truth vote).
8. Copied support from another wallet remains visibly duplicate content, not
   independent corroboration; no score is computed.
9. Missing / altered bytes fail content checks.
10. Revision registration preserves original content.
11. Unauthorized withdrawal and supersession rejected.
12. Invalid successor / empty lifecycle reason rejected.
13. Same-author supersession preserves original content and successor; terminal
    lifecycle cannot then be withdrawn.
14. Withdrawal retains revision bytes/record.
15. Separate read-only indexer matches every stored claim/evidence field; event
    history count and provisional label match.
16. Unknown upgrade selector reverts; contract bytecode unchanged.
17. Cross-deployment domain replay rejected.
18. Cross-chain domain replay rejected even at identical contract address; a raw
    transaction signed for chain 31337 is rejected on 31338.
19. Snapshot rollback removes orphan logs/state, depth filter delays visibility,
    replacement branch does not resurrect orphaned claim.

## Executed BitRep adapter cases

- Exact upstream fixture canonical bytes and complete expected result.
- Altered and unavailable evidence bytes.
- Expected subject, statement type, audience, content digest and statement digest.
- Chain/deployment audience replay.
- Expired and not-yet-valid statements.
- Revoked issuer key.
- Invalid signature.
- Untrusted snapshot fingerprint.
- Unsigned verification-result JSON rejected as an attestation.
- Duplicate JSON members.
- Expired/unavailable trust snapshot.
- Tampered signed statement even when expected statement digest is updated.

Fixed vector time 1800000000 is synthetic reproduction, not current assurance.
The live chain fixture is freshly signed and evaluated at local wall time.
No BitRep source files are changed; existing crypto and policy checks are reused.

## Legacy regression results

85 repository tests pass, including updated expectations for destructive PUT/DELETE
(409; record remains readable), deep-copy protection for created/read/listed/searched
claims and nested fields, plus alternate-store status history retaining prior states.
Existing governance/evidence/model tests remain passing; this does not confer chain
or signature assurance on the legacy services.

## Actual local measurements

Receipt time measures local send (including estimation) through mined receipt, not
network finality. Fees are synthetic Ganache wei; no real funds were spent. Values
are individual observations, not throughput benchmarks or production estimates.
Deployment and transaction gas depends on byte values/compiler/environment.

| Operation | Gas used | Synthetic fee (wei) | Local receipt ms |
| --- | ---: | ---: | ---: |
| deploy | 823053 | 911466896484375 | 143.27 |
| register | 96416 | 94158872322368 | 155.14 |
| support | 163228 | 139609013355604 | 156.33 |
| challenge | 142949 | 107147633513877 | 142.2 |
| copied-support | 163228 | 107200060004180 | 190.79 |
| revision | 118885 | 68424257707910 | 150.46 |
| supersede | 61586 | 31050209125292 | 109.37 |
| withdraw | 32462 | 14329152733902 | 121.83 |
| orphan-register | 96416 | 32850023882528 | 128.45 |
| replacement-register | 96404 | 32845935346532 | 138.82 |

## Untested or deliberately unimplemented

- Production chain deployment, real consensus finality, validator faults, live peer
  reorgs/censorship, dishonest RPC and authenticated block/receipt proof validation.
- Concurrent mid-scan reorg timing (hash-change detection is implemented, but only
  rollback/rebuild and replacement branch are exercised).
- Contract audit, fuzzing/formal verification, production scale, long-term historical
  log retention, pagination/checkpointed indexer performance and operational recovery.
- Native Ed25519 verification, proof bridge, on-chain issuer admission/revocation or
  signed verification receipts. Contract commitments never imply verified status.
- Production snapshot freshness/rollback defense, signed publication and issuer vetting.
- Off-chain replication, confidentiality, content-store availability SLAs and real
  provenance/source-independence assessment. Local fixture availability only.
- Full legacy API migration, evidence-withdrawal lifecycle, production epistemic
  weighting, governance/recovery procedures and multiple interoperating node clients.

These are explicit boundaries, not successful placeholder implementations.
