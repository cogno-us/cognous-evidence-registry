# Changelog

## 2026-10-23 — clean-checkout gate trusts the pinned tree; source-key folds invisible characters and URL paths (scan6 F1, F3)

- **Behaviour change, F1:** `chain/python/bitrep_checkout.py` builds the tracked set from `git ls-tree -r` at the pin instead of
  `git ls-files` (the index), and refuses any staged difference between the index and HEAD (`git diff --cached`). A file added with
  `git add` but not committed is now refused as an untracked importable file, as an uncommitted one already was. Modified tracked
  files were already refused by the content hash check. The BitRep pin is unchanged.
- **Behaviour change, F3:** `EvidenceService._source_key` removes control (Cc), format (Cf), private-use (Co), unassigned (Cn) and
  default-ignorable/blank characters (Hangul fillers U+115F/U+1160/U+3164/U+FFA0, braille blank U+2800, variation selectors,
  tag characters), treats every Z* and whitespace character as a plain space, folds slash lookalikes (U+2215, U+2044, U+29F8,
  U+2571) to `/`, drops trailing dots, collapses doubled slashes in DOIs, and for http(s) URLs normalises the path (`.`/`..`
  segments, empty segments, percent-encoded unreserved characters). Reserved encodings such as `%2f` stay distinct. Existing tests
  that encoded the old behaviour were changed: `https://example.org/paper//` is now the same source as `.../paper`
  (tests/test_source_key_folding.py) and `doi:10.1234/abc.` is now the same DOI as `doi:10.1234/abc` (tests/test_link_attestation.py).
  Weights and status thresholds are unchanged. The `the_index` pin moves again at the separate refreeze; nothing was refrozen here.

## 2026-10-22 — clean-checkout gate sees nested repos; wider source-key folding (scan5 C-T1-4, C-T2-5)

- **Behaviour change, C-T1-4:** `chain/python/bitrep_checkout.py` no longer relies on `git ls-files --others`, which lists an
  untracked directory holding its own `.git` as one opaque entry. It walks the tree (symlinks not followed, nested `.git`
  directories included) and refuses any untracked importable file, untracked symlink or nested git repository. Under
  `__pycache__` only `*.pyc` is tolerated; any other importable suffix there is refused. `.pyd` is added to the
  importable suffixes. The BitRep pin is unchanged (the `the_index` pin changes only through the separate refreeze).
- **Behaviour change, C-T2-5:** `EvidenceService._source_key` also folds generic http(s) URLs (scheme, leading `www.`, default
  port, host case, trailing host dot, fragment, one trailing slash; query kept), arXiv spellings `export.arxiv.org`,
  `arxiv.org/html/` and `alphaxiv.org/abs|pdf|overview/`, `hdl.handle.net/10.x/y` as a DOI, and a small map of
  Cyrillic/Greek lookalike letters. The docstring claim that errors only ever count fewer sources is replaced by a statement of
  what is and is not folded. Weights and status thresholds are unchanged; other aliases are still not resolved.

## 2026-10-22 — source-key unification and dangling links (scan4 C-1, C-2)

- **Behaviour change, C-1:** `EvidenceService._source_key` folds DOI spellings (`doi:`, `info:doi/`, `urn:doi:`,
  bare, doi.org/www/dx URLs, case, percent-encoding, trailing slash) and arXiv spellings (`arxiv:`, abs/pdf URLs,
  version, old-style ids) to one key, so one source in several spellings no longer inflates weight or independence.
  A DOI against a publisher URL stays un-unified (documented limit). BitRep pin 981036c3 and the vendored verifier are unchanged.
- **Behaviour change, C-2:** `POST /api/v1/evidence/links` returns 404 for a nonexistent claim, `claim_id_2` or
  evidence record (after attestation verification; nothing stored). The service method is unchanged.

## Unreleased — BitRep pin 981036c3

- Pin the BitRep checkout used by `chain/python/bitrep_adapter.py` to 981036c3 (was 5b5077d), so
  the chain adapter runs against the attestation revision locked in the hub component lock.
  Adapter, vendored-verifier header and documentation references are updated to match.
  `chain/VALIDATION.md` is unchanged as a historical record of the earlier pin.
- The chain qualification wrapper now calls the qualification workflow that pins 981036c3 and
  installs its hash-locked requirements on their own. No change to registry behaviour.

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
