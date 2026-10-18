---
Title: Lineage
Index_Key: IIO-LINEAGE
Type: Index Operation
Layer: Governance Layer
Status: Proposed (not implemented)
Canonical: true
Version: 1.0
Parent: Index Integrity Operations (IIO)
---

# Lineage

## Dependencies

- `IIO-PARITY` — Lineage chain construction depends on Parity to confirm that each record referenced in the chain is internally consistent and not a ghost or shadow record.
- `IIO-CHECKSUM` — The integrity of each node in a lineage chain is verified using the same per-record checksum mechanism that Lineage relies on to detect chain tampering.
- `ontology/core.json` — Mutation-type labels used to annotate lineage entries are drawn from the active governance vocabulary in the core ontology.

---

## Description

Lineage is the Index Integrity Operation that constructs, verifies, and preserves the complete ancestry chain of every record from its origin through all authorized mutations. A record's *lineage* is the ordered sequence of governance-authorized events — creation, status update, rebind, merge, schema migration — that produced the record's current state. The lineage chain is the authoritative audit trail for every object in The Index.

Lineage is not provenance in the scientific sense (which is recorded in `Evidence.provenance_chain`); it is protocol-layer provenance, capturing how the *protocol representation* of a knowledge artifact has evolved over time. A complete lineage chain allows any past state of a record to be reconstructed and any authorized mutation to be attributed to the governance proposal that authorized it.

---

## Function

1. **Creation entry recording** — When a `Claim` or `Evidence` record is first committed to the store, Lineage writes a creation entry to the record's lineage chain. The creation entry records the record's `id`, the submitter's BitRep identity (`created_by`), the timestamp, and the initial `immutable_hash` or `checksum`.

2. **Mutation entry recording** — Every authorized mutation to a record (status update via `ClaimStore.update_status()`, schema migration, merge, or rebind) MUST append an entry to the record's lineage chain before the mutation is applied. The entry records the mutation type, the authorizing governance proposal `id`, the actor's BitRep identity, the timestamp, and the before/after values of all mutated fields.

3. **Lineage chain integrity verification** — Lineage verifies that each entry in a record's lineage chain is internally consistent: the before-value of each entry MUST match the after-value of the immediately preceding entry. Any gap or inconsistency is a lineage chain break.

4. **Cross-record lineage linking** — For `Link` records created as part of a rebind, Lineage records a cross-reference between the old link's lineage chain and the new link's lineage chain, preserving the full history of the semantic relationship across the identifier change.

5. **Lineage-based state reconstruction** — Given a record's lineage chain, Lineage can reconstruct the record's state at any past timestamp by replaying the chain's mutation entries forward from the creation entry. This reconstruction MUST produce a state that passes an `IIO-PARITY` check.

---

## Invariants

1. Every `Claim` and `Evidence` record MUST have a lineage chain with at least one entry (the creation entry) from the moment it is committed to the store.
2. The lineage chain of a record MUST be append-only; no entry MAY be removed or modified after it is written.
3. Every mutation to a record MUST have a corresponding lineage entry written before the mutation is applied; a mutation with no lineage entry is a protocol violation.
4. The before-value of each lineage entry (except the creation entry) MUST equal the after-value of the immediately preceding entry for every mutated field.
5. A lineage chain MUST reference the authorizing governance proposal `id` for every entry that records a mutation; entries without an authorizing proposal reference are valid only for creation entries.

---

## Failure Modes

| ID | Failure | Trigger | Severity |
|----|---------|---------|----------|
| F1 | **Missing creation entry** | A `Claim` or `Evidence` record exists in the store with no lineage chain or an empty lineage chain | Critical |
| F2 | **Unauthorized mutation** | A record's current state differs from the state derivable from its lineage chain, indicating an unrecorded mutation | Critical |
| F3 | **Lineage chain break** | A lineage chain entry's before-value does not match the after-value of the preceding entry | Critical |
| F4 | **Missing proposal reference** | A mutation lineage entry carries no reference to an authorizing governance proposal `id` | High |
| F5 | **Lineage entry tampering** | A previously written lineage entry has been modified, detected by recomputing the entry's checksum | Critical |
| F6 | **Reconstruction failure** | Replaying a record's lineage chain forward from the creation entry does not reproduce the record's current state | High |

---

## Enforcement

- **At write time**: Every call to `api/claim_layer.py` `ClaimStore.store()` MUST create the initial lineage entry atomically with the record write. Every call to `ClaimStore.update_status()` MUST append a mutation lineage entry before updating the `status` field.
- **At write time**: Every call to `api/evidence_layer.py` `EvidenceStore.store()` MUST create the initial lineage entry atomically with the record write.
- **Governance integration**: Every executed governance proposal that authorizes a mutation MUST supply the proposal `id` to the lineage entry writer before the mutation is applied.
- **Scheduled verification**: A governance-layer lineage scan SHOULD run after each governance cycle to verify chain integrity (Invariant 4) and detect unauthorized mutations (Failure Mode F2) across all stored records.

---

## Notes

- Lineage is the foundational audit mechanism for The Index. Without complete lineage chains, it is impossible to distinguish an authorized mutation from unauthorized drift (see `IIO-DRIFT`).
- The distinction between scientific provenance (`Evidence.provenance_chain`) and protocol lineage (this operation) is important: provenance captures how a knowledge artifact was produced in the world; lineage captures how its representation in The Index was produced and evolved.
- Lineage chains are append-only by protocol invariant. Any storage implementation MUST enforce this constraint at the storage layer, not solely at the application layer.
- Future versions may incorporate Merkle-tree-based lineage commitments to enable efficient, cryptographically verifiable lineage proofs without replaying the full chain.
