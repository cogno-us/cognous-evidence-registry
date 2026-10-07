# Index blockchain reference profile v0.1 — Governor review

This profile defines the **local prototype**, not a deployed network or an audited
production protocol. It supersedes conflicting legacy documentation only for
`chain/`. It is not full conformance to the legacy reputation-based specification.
The target is shared blockchain state with direct participation, not API storage
with periodic hash anchoring. No production chain has been selected.

## Audit baseline and scope

Starting Index main: `3abba683c707ae95c7834036231ac55463cf1586`.
Repository instructions: `CONTRIBUTING.md`; no `AGENTS.md` found in repository or
workspace ancestors. Existing MIT license and history are retained. Only public
repository material and synthetic test data are used; no proprietary cognition
mechanisms or confidential evidence are imported.

| Baseline path | Actual authority / defect |
| --- | --- |
| `app/claims/service.py`, `app/api/claims.py` | Process-local global dictionaries; unrestricted PUT changes text/status and DELETE erases claims. No separate accepted-state guard. Confirmed, now blocked for every created claim with HTTP 409. |
| `api/claim_layer.py` | Separate in-memory implementation rejects same-ID writes but shallow copies and returned aliases allow mutation; status overwrote prior state. Now deep copies and local status history. Still no authenticated chain authority. |
| `api/link_layer.py` | Nonempty attestor ID is accepted without BitRep signature verification; optional reference callback can be omitted. Existing legacy code, explicitly not a blockchain admission route. |
| `app/evidence/service.py`, `protocol/epistemic_engine.py` | Local scoring / optional reputation inputs, not BitRep v1 reputation. Not used by this profile. |
| `app/governance/service.py` | Caller-provided voter identity/reputation and in-memory votes. Does not authorize contract upgrades or protocol truth. |
| `app/core/security.py` | RSA utilities are not an integrated BitRep v1 gate; ZK placeholder is not proof. No assurance use permitted. |
| README / `docs/roadmap-internal-notes.md` | Intended immutability, BitRep reputation, and decentralized governance exceed implementation. No chain integration, smart contracts or chain toolchain at baseline. |

Baseline participants cannot reconstruct accepted history independently after
process exit or destructive mutation. Host administrators can edit memory/storage.
The new contract is an additive, separate authority; old API records are **legacy,
unverified, non-protocol data**, not alternate writes to blockchain state.

## Authority and decentralization model

| Function | Participant / authority | Restriction and trust boundary |
| --- | --- | --- |
| Read/reconstruct | Anyone with chain access; own validating node preferred | Public state; third-party RPC may omit/falsify results or censor queries. Full historical logs must be available. |
| Register claims | Any transaction sender | Pays network fees outside local test; valid nonzero commitment, existing parent if supplied, duplicate check. Does not establish human identity. |
| Submit support/challenge | Any transaction sender | Existing claim, nonzero content/manifest commitments, relation 1 or 2. Allowed after withdrawal/supersession to preserve later criticism. |
| Attest | Any Ed25519 signer can issue an assertion off-chain | BitRep issuer assurance requires admission in the verifier's explicit trusted snapshot. Contract records optional statement commitment only. |
| Propose revision | Anyone | Register a new claim linked to an existing parent. Third-party proposal cannot mark the original superseded. |
| Withdraw/supersede | Original claim wallet author | Active only. Supersession requires an active same-author direct child. Reason commitment required; never deletes old content or challenges. |
| Validate transitions | Chain nodes execute contract; consensus selects canonical chain | Local Ganache is a single development node, not a decentralized validator network. |
| Lifecycle status | Fixed `index-lifecycle/1` contract rules | Active, withdrawn, superseded. None means supported, true, legitimate, or authorized. |
| Epistemic status | Independent derived views / explicit governed judgments | No automatic truth voting or reputation weighting in the reference contract. |
| Upgrade/parameters | Nobody within this deployment | No owner, admin, proxy, delegatecall, parameter setters, or upgrade function. New versions require a new deployment and explicit user adoption. Chain-level governance remains external. |
| Issuer admission | Each verifier's chosen trust-snapshot operator | Currently centralized within that trust domain. Publishing its hash does not decentralize admission. No universal admission governor is invented here. |
| Gateways/indexers | Optional operators | Caching, search, retrieval, replication and notifications; cannot change contract state without ordinary transactions. |

Wallet key theft allows that wallet's lifecycle actions; no administrator recovery
exists. Address control is not issuer legitimacy or institutional permission.
Access restrictions imposed by gateways do not change who may transact directly.
No economic Sybil defense beyond network resource pricing is claimed.

## Authoritative on-chain representation

Contract source is the executable transition rule. Protocol release identity must
pin source commit, compiler settings, runtime bytecode hash, chain ID, deployment
address and deployment block/hash. `POLICY = SHA256(ASCII("index-lifecycle/1"))`
is a version label, **not** a hash of a complete policy document or bytecode.

`DOMAIN = keccak256(abi.encode("index-domain/1", chainId, contractAddress, POLICY))`.
Every write requires this domain. Ordinary wallet transactions also bind calldata,
recipient, chain ID and nonce. Same chain ID/address/code on a cloned fork is not
a distinct replay domain; canonical chain selection/finality is an external input.

Claim ID is `keccak256(abi.encode(DOMAIN,"claim",sender,contentSHA256,parentId))`.
Records retain author, content commitment, parent, lifecycle and successor. Same
sender/content/parent is a rejected duplicate. Different senders are different
assertions, not independent facts. A revision gets a new ID. Parent references
must preexist, preventing cycles. No global content ownership or truth registry.

Evidence submission ID is `keccak256(abi.encode(DOMAIN,"evidence",sender,claimId,
contentSHA256,manifestSHA256,statementSHA256,relation))`. All fields are stored and
emitted. `statementSHA256` may be zero (no associated BitRep statement). Nonzero
means **unverified commitment**, never a caller-supplied verified flag. Relations
are 1=support assertion and 2=contradiction/challenge assertion. These are attributed
opinions about evidence, not adjudications. Exact duplicates reject; semantic
copies under other IDs remain visible and must not inflate corroboration.

`Registered`, `EvidenceSubmitted`, and `LifecycleChanged` events expose all values
needed to reconstruct records and historical lifecycle transitions. Reason hashes
are preserved in events. Original commitments and provenance links never change.
Withdrawal is an author statement, not erasure or retraction by every other party.
Terminal records cannot be reactivated; a later correction is a new linked claim.
Evidence correction means a new committed artifact/manifest plus a later assertion;
there is no evidence delete, automatic invalidation, or evidence-withdrawal endpoint
in this bounded slice. Such lifecycle extensions require a new reviewed profile.

## Off-chain bytes, addressing and availability

Content commitments are SHA-256 of **exact bytes**. No implicit Unicode, newline,
JSON-key, archive, compression, or MIME normalization occurs. Clients must choose
and record encoding before hashing; `client.mjs` accepts byte arrays only. On-chain
`bytes32` stores the 32 digest bytes; BitRep uses `sha256:` + lowercase 64 hex.
A content address is `sha256:<hex>`; it is not automatically an IPFS CID.

Large evidence, claim text, methodology, provenance manifests, attestation envelopes,
trust snapshots, personal data and confidential material stay off-chain. A proposed
`index-evidence-manifest/1` exact-byte JSON object should record content digest,
media type, source lineage IDs, acquisition/measurement context, dependency/copy
relationships and retrieval locations/replica policy. This is a proposed metadata
profile, not a contract-enforced JSON schema. The prototype uses synthetic local
bytes; it does not deploy IPFS or an evidence hosting/replication service.

Retrievers use the digest as lookup key in independently configured content stores;
verify bytes after fetching, regardless of location. A manifest can list HTTPS/IPFS
replicas but URLs and access tokens MUST NOT be put on-chain. Mirror operators must
retain original bytes, attestations, manifests, snapshots and old versions. At least
two independently controlled replicas and an archive are recommended for deployment,
not implemented availability guarantees. BitRep envelopes can be looked up by
statement digest; recompute signed-statement digest and verify the envelope on receipt.

Missing objects produce **unavailable/no usable content assurance**, not falsehood,
zero evidence weight, or deletion. Invalid bytes produce commitment mismatch. Chain
records survive loss of content. Claim/evidence bytes cannot be recovered from hashes;
only the committed graph can be reconstructed from chain alone. Availability is a
time- and observer-specific observation, not a permanent property established by a
successful fetch. Replication, permissioned retrieval and deletion of off-chain
copies cannot erase past dissemination or public chain links.

Hashes can disclose low-entropy material by guessing and reveal relationship patterns.
Never assume hashing anonymizes confidential content. Prefer no public commitment at
all when disclosure risk is unacceptable. Any future salted/encrypted commitment
profile needs a precise byte/key/access model; this profile does not claim privacy.

## Reconstruction, reorganization and derived views

`reconstruct.mjs` reads only chain logs using a separate JSON-RPC client, sorts by
block/transaction/log order and rebuilds from genesis through a chosen block depth.
It records block hashes and lifecycle reasons and checks the end-block hash before
and after scanning. A detected mid-scan reorganization causes retry. Rebuilding
rather than retaining a mutable cache removes orphaned records after a reorg. This
bounded implementation is inefficient for a large chain; pagination, checkpoints
with rollback and archival-node operation remain deployment work.

Clients must independently pin network, deployment and code identity. Reading an
arbitrary address with this ABI does not certify it. An RPC server is not a consensus
proof. An own validating node or separately verified authenticated chain evidence is
required for stronger verification. Comparing two clients against one local node
proves algorithmic reconstruction, not resistance to a dishonest node.

`confirmations=N` is a depth filter, never advertised as consensus finality. The
local test exercises snapshot rollback, replacement branch and delayed visibility.
Live peer forks, censorship, validator outages, finalized-checkpoint behavior and
RPC dishonesty are untested. A production reader must select chain-specific finalized
checkpoints and retain observed/canonical/finalized distinctions; no such adapter is
claimed here. Block timestamps do not prove issuer signing time.

Recomputable graph views pin deployment, end-block hash, policy/source version and
all bytes used. Epistemic assessment additionally pins content/manifest bytes, local
assessment code, trust snapshot and verification time, provenance/dependency clusters,
explicit weights and uncertainty rules. This slice emits no supported/refuted score.
Same content hash is a duplicate signal; differing bytes do not prove independence.
Copied publications, shared datasets, common instrumentation and coordinated issuers
require source analysis. Unknown independence stays unknown. Multiple wallets,
signatures or issuer IDs do not multiply evidential weight. Governed judgments must
identify their responsible institution and policy separately from protocol inclusion.

## BitRep integration and exact blocked boundary

Pinned repository: `cogno-us/cognous-evidence-attestation`, commit
`5b5077dafde232a7801cb425c4efddcffb468723`. Read/used:
`docs/VERIFICATION_CONTRACT_V1.md`, `models/verification.py`,
`utils/verification.py`, `utils/trust.py`, `tests/fixtures/verification-v1.json`.
No BitRep source or signature scheme is changed or copied into The Index.

`python/bitrep_adapter.py` loads a clean pinned checkout in a separate process,
uses upstream strict parsing/canonicalization/Ed25519 verification, recomputes the
exact content commitment and statement digest, and compares expected subject, type
and audience against independent chain/policy inputs. It authenticates the snapshot
only by comparison with a fingerprint the local operator already trusts out of band.
A fingerprint supplied by the evidence submitter is NOT a trust root.

Audience: `index:eip155:<decimal chainId>:<lowercase contract address>:v1`.
Subject: audience + `:claim:<64 lowercase claim-ID hex without 0x>`.
Relation 1 requires `index-support/1`; relation 2 requires `index-challenge/1`.
The Ed25519 signature binds those fields and the evidence content, not the wallet
sender or the manifest's lineage claims. Relaying another issuer's genuine statement
is permitted; it does not make that issuer the transaction sender. Manifest content
and authorship attribution have their own weaker commitment/transaction semantics.

The adapter accepts `bitrep-attestation/1` and freshly computes
`bitrep-verification/1`; copied result JSON cannot satisfy its input schema. Snapshot
operator controls issuer/key admission and revocation. No reputation score, source
independence or institutional permission is provided by BitRep v1. CLI evaluates at
current local wall time. Fixed-time tests are reproducibility exercises, not a newly
implemented historical trust decision or proof of signing time. Pinning a snapshot
permits reproducibility but does not guarantee it is the latest authorized snapshot.
Snapshot distribution, anti-rollback, authenticated publication, clock security and
revocation freshness remain governed deployment requirements.

The current-time verifier checks key validity at issuance and now, not-before/expiry,
and conservative revocation, including previously issued statements. An assertion
may remain included/finalized on-chain after it expires or is revoked. Current
assurance must then be rejected; original inclusion history remains. Never substitute
chain timestamp for verifier `now`, or equate inclusion with current validity.

| Integration choice | Feasibility and trust / availability assumptions |
| --- | --- |
| Native Ed25519 verification (e.g. Solana precompile) | Can verify exact BitRep signed bytes if instruction offsets/messages/keys are bound correctly. Still needs explicit issuer admission, current snapshot/revocation policy, clock semantics, and available evidence. Native signature verification alone does not solve these. Not implemented. |
| Independent off-chain verification (implemented) | Anyone can run the pinned code and compare exact inputs under an authenticated chosen snapshot. Results remain observer-specific, unsigned and time-dependent. Chain stores commitments only; no privileged verifier bridge or central API is required. |
| Governed signed receipts / quorum | Requires a new, domain-separated signed receipt format, named authorized verifier keys, threshold and revocation policy. Contract would trust those governors; must not be described as trustless. Current BitRep unsigned JSON cannot implement this. Not implemented. |
| Cryptographic proof bridge | A reviewed proof system could bind canonicalization, Ed25519, trust-root membership, revocation and time policy to public inputs. Requires verifier/circuit audits and snapshot legitimacy rules; proving against an arbitrary trust root is insufficient. Not implemented. |

**Blocked boundary:** contract-enforced BitRep issuer validity. This EVM slice has no
reviewed Ed25519 verifier/proof bridge or decentralized authenticated trust-registry
profile. It never upgrades an unverified commitment to verified state. This is an
explicit functioning-subset delivery, not a success stub. Changing BitRep to secp256k1
is NOT proposed as an implicit workaround. Any historical profile, signed receipts,
registry publication or bridge interface goes to Governor first.

## Chain/toolchain decision (reversible ADR-001)

No chain was established in the repository. Recommend an Ethereum-compatible
non-upgradeable contract for this local reference experiment: small state machine,
reproducible compilation, direct clients, logs and well-supported testing. Use
Solidity 0.8.30, ethers 6.16.0 and Ganache 7.9.2 (Shanghai rules). These pinned versions
are a local test environment, not a current production-node recommendation.

| Criterion | Ethereum L1 candidate | Solana candidate |
| --- | --- | --- |
| Independent use | Direct transactions and own execution/consensus nodes | Direct instructions and own validator/RPC infrastructure |
| Finality / censorship | PoS finality, canonical-chain and validator participation assumptions; inclusion can be delayed/censored | Commitment/finality selection, validator and RPC availability assumptions; inclusion can be delayed/censored |
| Ed25519 | No Ed25519 facility used by this EVM profile; a reviewed verifier/bridge is additional work | Native Ed25519 precompile is a useful fit, but must bind verified instruction bytes to protocol inputs |
| Cost / operations | Persistent storage and event fees; node/archive operations. No production cost quote measured | Account storage, transaction/compute costs and validator/indexing operations. No production cost quote measured |
| Upgrades | This design has no proxy/admin; new deployment/adoption only | Program upgrade authority must be explicitly governed or removed; blockchain placement alone does not remove it |
| Data availability | Chain state/log history plus independently replicated off-chain bytes | Account state/history/indexing plus independently replicated off-chain bytes |
| Tooling | Chosen for bounded Solidity/JS testing; no new consensus implementation | Credible alternate for native signature work; introduces a different program/account toolchain |

Production selection is reserved to Governor after volume, archival availability,
finality and native BitRep enforcement requirements are agreed. Rollups could reduce
execution expense but add sequencer, escape-path, upgrade and settlement assumptions;
none are chosen or measured. Do not create a chain or speculative token.

Primary references consulted 2026-10-05:
- https://ethereum.org/developers/docs/consensus-mechanisms/pos/
- https://solana.com/docs/core/programs/precompiles
- https://solana.com/docs/programs/deploying

## Migration and compatibility

1. Preserve existing storage/export backups and licenses; do not rewrite repository
   history or silently reinterpret legacy IDs as blockchain IDs. The old in-memory
   API is not durable; snapshot it before process shutdown if migrating live data.
2. Inventory records and exact source bytes. Export original IDs, provenance and
   lifecycle history where it exists; mark missing history unknown, never invent it.
3. Review disclosure before publishing any commitment. Existing raw objects remain
   off-chain with an explicit retention/replication/access policy.
4. Obtain new wallet transactions for protocol registration and issuer-signed BitRep
   assertions where needed. Importer's wallet attribution is not historical author
   authentication. Old IDs may appear only in an explicit off-chain migration manifest.
5. Record old-to-new ID mappings, chain/deployment/block hashes and fresh commitment
   checks. No legacy `verified`, local score or reputation field is promoted to assurance.
6. Run independent reconstruction; only then make a future API a read projection and
   transaction convenience layer. This PR does not wire the legacy API to a node or
   claim it has become decentralized. PUT/DELETE now intentionally return 409; clients
   must use the new protocol lifecycle instead. No silent destructive compatibility.
7. For upgrades, deploy a separately reviewed version and let participants choose
   migration links. No force migration, administrator rewrite or contract upgrade.

## Governor decisions

- Approve/reject the bounded profile and terminal lifecycle rules, including wallet
  loss/recovery and separate evidence lifecycle requirements.
- Select production network only after finality, censorship, archival, fee, capacity
  and privacy requirements; local EVM selection is reversible.
- Decide whether issuer verification must gate on-chain admission. If yes, choose and
  commission the missing bridge/native implementation plus a governed trust profile.
- Assign issuer admission/snapshot publication, freshness/anti-rollback, revocation
  distribution and snapshot archive responsibility without labeling it decentralized.
- Approve audience/subject/type strings and any BitRep signed-receipt or historical
  extension before cross-repository work.
- Approve provenance/independence and evidence-manifest schema, retention and governed
  assessment policies. No hidden truth votes or account-count corroboration.
- Review the PR, required checks and merge under normal repository protections.
