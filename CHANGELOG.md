# Changelog

## 2026-11-03 - R1-B3: the trusted BitRep object read starts no git process and is bounded (csf_518b8599e95b7919b55fe371, csf_d7e271587bb3dc0dec7ac96f)

- **Behaviour change (security):** `materialize_pinned` / `verify_anchored` / `verify_commit` / `verified_tree_entries` no longer run
  `git cat-file --batch`. A repository-local `.git/config` could declare a partial clone / promisor remote (for example
  `remote.X.promisor=true`, `extensions.partialClone`, a `ext::` URL and `protocol.ext.allow=always`); git then lazily fetched a missing anchored
  object and executed the attacker's helper before Python authenticated a single byte. The `.git/objects` directory is now treated as untrusted
  bytes read by a minimal in-process reader: loose objects (zlib) and pack/idx v2 files (OFS_DELTA and REF_DELTA inside the same pack), looking up
  only the specific object ids asked for. Each candidate is re-hashed (`sha1("<type> <size>\0" + raw)`) against the id from the trusted anchors or an
  already authenticated parent; a missing object is an error, never a fetch. Configuration, promisor/remote/protocol settings,
  `objects/info/alternates`, `GIT_*` variables, refs, HEAD, tags, packed-refs, `refs/replace`, grafts, shallow files and `.git` gitfiles are never
  consulted. The detached read-only copy, anchors, exact-bytes/CRLF/submodule/symlink rules and the post-load module location check are unchanged.
- **Bounds (csf_d7e271587bb3dc0dec7ac96f):** object size 256 KiB, compressed input 320 KiB per object, 4 MiB authenticated bytes in total,
  16 MiB inflated work (incl. delta streams and bases), 512 objects, 512 entries per tree (2048 in total), 128 trees, delta depth 50, 32 packs,
  200 000 objects per pack index. Inflation uses `zlib.decompressobj` with `max_length`, so a bomb is refused before it is buffered. Only commit,
  tree and blob objects are accepted. Any malformed pack, index or object raises `ValueError`.
- **Compatibility:** `materialize_pinned`, `load_bitrep`, `verify_*`, `TrustedObjects` and `checkout_problems` keep their signatures. An object
  store that relied on `objects/info/alternates` (the genuine objects living in another directory) is now refused: copy or repack the objects into
  the checkout's own `.git/objects`. sha256 repositories, pack index v1, thin/promisor packs and `.git` gitfiles are not supported.
  `checkout_problems` (an optional working-tree audit) still uses hardened git; it is not on the import path.

## 2026-11-03 - R1-B2: BitRep commit, tree and blob identities are independent trusted anchors (csf_2549122f435d297f245f3c12)

- **Behaviour change (security):** `materialize_pinned(root, pin, dest=None, *, anchors)` no longer asks the checkout's object database what the
  pinned commit or tree is. `anchors` (`TrustedObjects`) come from committed trusted code, `chain/python/bitrep_trusted_objects.py`: the commit
  id `981036c315856c71207984797b0c4e48d3b3921d`, its root tree id `96d9a687597c8a5e63c55a52c92fbfef35b791ba` and the full manifest of the
  71 `(mode, path, blob id)` entries of that tree. The loader hashes the raw commit object (`commit <len>\0` + bytes) in-process and compares it
  to the pinned commit id, checks its `tree` line, re-hashes every tree object from the root down (`tree <len>\0` + bytes), requires the
  resulting entry set to equal the manifest exactly (paths, modes, blob ids), and re-hashes every blob against the manifest. The object database,
  alternates, replace refs, refs, tags, HEAD, grafts and shallow files may only supply bytes; they never define an expected id. A symbolic or
  abbreviated pin, or a pin different from `anchors.commit`, is refused. Scrubbed environment, no filters and detached materialization are
  unchanged; BitRep envelope and attestation digest semantics, CRLF policy (exact bytes), the CLI and the `PIN` constant are unchanged.
- The anchors are **source-authentication anchors, not operational authority**: they identify which exact BitRep bytes may be imported and
  grant nothing (no trust registry, no signing or acceptance authority).
- Reproducible derivation: `python chain/python/derive_bitrep_trusted_objects.py <known-good clone> <commit> --write` (a test regenerates
  and compares when a clone is available, `BITREP_KNOWN_GOOD`).
- **How to update the BitRep pin:** (1) obtain the new commit from a clone you trust; (2) run the derivation tool with the new commit id and
  review the diff of `bitrep_trusted_objects.py`; (3) change `PIN` in `chain/python/bitrep_adapter.py` to the same commit (the adapter refuses if
  `PIN != bitrep_trusted_objects.COMMIT`); (4) update `PRODUCTION_PIN` in `tests/test_bitrep_checkout.py` and the pinned tree/file-count
  assertions in `tests/test_r1b2_trusted_object_anchors.py`. All four change in one commit.
- `checkout_problems` (the worktree audit) is unchanged and still resolves `HEAD` through git; the adapter no longer relies on it for authenticity.
- Note: on git 2.43 git itself re-hashes trees and commits when parsing them, so forged tree/commit objects in a pack are already stopped by
  git; this change removes dependence on that behaviour and on any git version, config or object-format feature.

## 2026-11-03 - R1-B: BitRep source verification hardened; BitRep is imported from a detached authenticated copy (csf_612ced4ef93a62df3d54b797, csf_db3f244ab2fd16c3a657eb5d)

- **Behaviour change (security):** `chain/python/bitrep_checkout.py` no longer re-hashes differing files through git filters. The
  `hash-object --stdin-paths` call (which ran repository-configured clean filters and accepted the filtered hash) is gone; blob ids are
  computed in-process from raw on-disk bytes. A CRLF-mutated or otherwise edited tracked file is refused, never normalised.
- Every git subprocess uses a scrubbed environment (`GIT_CONFIG_NOSYSTEM`, global/system config -> null device, no replace objects, no
  inherited `GIT_*`) and `-c core.fsmonitor=false core.hooksPath=/dev/null core.attributesFile=/dev/null`; only filter-free plumbing is used.
- New `materialize_pinned(root, pin, dest=None)` copies the pinned commit's blobs from the object database (`cat-file --batch`, each blob
  re-hashed) into a private read-only directory. `bitrep_adapter.load_bitrep()` now puts only that copy on `sys.path` (and checks the
  imported modules live inside it), so untracked or shadowing files, later edits to the checkout and lazy imports cannot change executed
  bytes. `BITREP_ROOT` is only a source of Git objects; the adapter no longer requires the worktree to be clean (it never executes it).
  `checkout_problems(root, pin)` keeps its signature and meaning. BitRep envelope and attestation digest semantics, the pin, and the CLI are
  unchanged. Evidence Registry/BitRep remains excluded from private-preview claims.
- Tests: tests/test_r1b_source_verification.py.

## 2026-10-22 — source-key: host normalised before DOI/arXiv matching, reserved encodings and DOI suffixes kept distinct (wave 7, T2-D, T2-E)

- **Behaviour change, T2-D (same source, distinct keys):** `EvidenceService._source_key` normalises the URL host before the DOI and
  arXiv patterns run: trailing dots, empty or default port, userinfo (dropped for DOI/arXiv, kept for other URLs), IDNA full stops
  (U+3002, U+FF0E, U+FF61) and a percent-encoded host (reserved `%2F %3F %23 %40 %3A %5B %5D %25` stay encoded). So
  `https://doi.org./10.1000/abc`, `doi.org:443/...`, `user@doi.org`, `arxiv.org./abs/...`, `arxiv.org:443/abs/...`, `example。org` and
  `%65xample.org` fold like their plain spellings. Percent-encoded non-ASCII is decoded before the Unicode folds (`/%C3%A4` is `/ä`), and
  tab, newline and carriage return inside an http(s) URL are removed as WHATWG does (in other text they remain spaces). The result is
  iterated to a fixed point; idempotence over the characters a fold can touch is tested.
- **Behaviour change, T2-E (different sources merged):** `%3F`, `%23` and `%25` in a DOI stay encoded, so `10.1000/a%3Fb` no longer
  becomes `10.1000/a`. A DOI suffix is opaque: `//` inside it and a trailing dot are no longer dropped (the 2026-10-23 changes did
  that); case is still folded (also after percent-decoding) and trailing slashes are still dropped. The trailing-dot drop on the last
  URL path segment is reverted: `/a.` and `/a` can be different resources and nothing justifies merging them. Existing tests that
  encoded the merges were changed in tests/test_scan6_source_key.py (`test_trailing_dot_folds` is now
  `test_trailing_dot_in_doi_suffix_stays_distinct`; the `//` DOI cases and `https://example.org/a.` were removed from the folding lists).
  New tests are in tests/test_scan7_source_key.py. Weights and status thresholds are unchanged. No pin, lock or refreeze file was touched.
- **Not changed (documented):** dependence of Cn (unassigned) stripping on the Python `unicodedata` version, and accent folding of hosts.

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
