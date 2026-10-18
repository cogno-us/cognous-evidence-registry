# INDEX_MAP.md — Table of Contents for The Index

This file is the authoritative Table of Contents for The Index protocol documentation. It maps every major conceptual area to its canonical documentation entry point.

---

## Core Concepts

| Concept | Description | Reference |
|---------|-------------|-----------|
| Claims | Atomic scientific assertions with canonical text and semantic structure | [README.md](README.md#core-concepts) |
| Evidence | Empirical or theoretical support linked to claims | [README.md](README.md#core-concepts) |
| Links | Attested relationships between claims and evidence | [README.md](README.md#core-concepts) |
| Epistemic Status | Reputation-weighted validity assessment computed per claim | [README.md](README.md#core-concepts) |
| BitRep Identity | Decentralized identity and reputation substrate | [The_Index_Whitepaper.md](The_Index_Whitepaper.md) |
| Governance | Community-driven proposal and voting system for protocol evolution | [README.md](README.md#governance) |
| Ontology | Shared vocabulary of relation types, status values, and evidence types | [../ontology/README.md](../ontology/README.md) |

---

## Index Operations

All Index Operations follow the canonical schema defined in [operations/README.md](operations/README.md).

### Index Integrity Operations (IIO)

| Index_Key | Title | Status | Version | Description |
|-----------|-------|--------|---------|-------------|
| [IIO-PARITY](operations/IIO-PARITY.md) | Parity | Proposed (not implemented) | 1.0 | Asserts and verifies structural and representational consistency between corresponding records across layers |
| [IIO-DRIFT](operations/IIO-DRIFT.md) | Drift Detection | Proposed (not implemented) | 1.0 | Identifies record deviations from their last known valid state without an authorized governance action |
| [IIO-CANON](operations/IIO-CANON.md) | Canonicalization | Proposed (not implemented) | 1.0 | Establishes and enforces the single authoritative form of each record, identifier, and term |
| [IIO-REBIND](operations/IIO-REBIND.md) | Rebinding | Proposed (not implemented) | 1.0 | Updates all live link and reference records when a canonical identifier or ontology term is superseded |
| [IIO-TRAVERSE](operations/IIO-TRAVERSE.md) | Traversal Optimization | Proposed (not implemented) | 1.0 | Ensures all graph traversal paths through the link layer are consistent, complete, and non-redundant |
| [IIO-LINEAGE](operations/IIO-LINEAGE.md) | Lineage | Proposed (not implemented) | 1.0 | Constructs, verifies, and preserves the complete ancestry chain of every record from origin through all authorized mutations |

---

## Invariants

The following are design targets for The Index protocol; the Index Operations that would enforce them are proposed and not implemented, and the legacy stores do not enforce I-1 or I-2 (see `chain/PROTOCOL.md`: reference existence is not enforced on the default path).

| ID | Invariant | Enforced By |
|----|-----------|-------------|
| I-1 | Every `Link` record's `source_id` MUST reference a live `Claim` | IIO-PARITY, IIO-TRAVERSE |
| I-2 | Every `Link` record's `target_id` MUST reference a live `Evidence` or `Claim` | IIO-PARITY, IIO-TRAVERSE |
| I-3 | `Claim.status` MUST be consistent with the most recent `EpistemicStatus` computation | IIO-PARITY, IIO-DRIFT |
| I-4 | Every `Link.relation_type` MUST resolve to an active term in `ontology/core.json` | IIO-PARITY, IIO-CANON |
| I-5 | The SHA-256 checksum of every `Evidence` record MUST match its stored value | IIO-PARITY, IIO-DRIFT |
| I-6 | Every record MUST have a complete, append-only lineage chain from creation | IIO-LINEAGE |
| I-7 | Exactly one canonical record MAY exist for each semantic entity | IIO-CANON |
| I-8 | All traversal index entries MUST reflect the primary link store | IIO-TRAVERSE |

---

## Governance Layer

| Resource | Description | Reference |
|----------|-------------|-----------|
| Proposal Types | `RULE_CHANGE`, `SCHEMA_CHANGE`, `ONTOLOGY_UPDATE` | [app/governance/models.py](../app/governance/models.py) |
| Governance Service | Proposal lifecycle, voting, and execution | [app/governance/service.py](../app/governance/service.py) |
| Governance API | REST endpoints for proposal management | [app/api/governance.py](../app/api/governance.py) |
| Governance Operations | IIO operations triggered by governance events | [IIO-REBIND](operations/IIO-REBIND.md), [IIO-DRIFT](operations/IIO-DRIFT.md) |

---

## Substrate Boundaries

The Index is layered. The table below defines what each layer owns and what it delegates.

| Layer | Owns | Delegates To |
|-------|------|--------------|
| Storage Layer | Immutability, checksum computation, primary store writes | — |
| Link Layer | Link record CRUD, traversal index maintenance | Storage Layer |
| Claim Layer | Claim lifecycle, status updates, canonical text | Storage Layer |
| Evidence Layer | Evidence ingestion, provenance chain, quality scoring | Storage Layer |
| Governance Layer | Proposal lifecycle, voting, mutation authorization | All lower layers |
| Protocol Layer | Epistemic engine, cross-layer invariant enforcement | All lower layers |

Cross-boundary operations:
- A **Parity** check spans the Claim, Evidence, and Link layers simultaneously.
- A **Rebind** operation is authorized by the Governance layer and executed across the Link and Storage layers.
- A **Lineage** entry is written by the Governance layer and stored alongside the record it describes.

---

## Future Expansion Slots

The following operation slots are reserved for future IIO entries. They are documented here to prevent namespace collisions and to signal planned protocol evolution.

| Reserved Index_Key | Planned Operation | Rationale |
|--------------------|-------------------|-----------|
| `IIO-MERGE` | Record Merge | Formal operation for collapsing duplicate records under a canonical identifier; currently handled procedurally within IIO-CANON |
| `IIO-ARCHIVE` | Archival | Governance-controlled retirement of records from the live graph to cold storage while preserving lineage |
| `IIO-ATTEST` | Attestation Verification | Formal operation for verifying BitRep cryptographic attestations on `Link` records |
| `IIO-MIGRATE` | Schema Migration | Formal operation for migrating record populations across schema versions |
| `IIO-QUORUM` | Quorum Verification | Formal operation for verifying that governance votes meet the required quorum threshold |
