---
Title: Parity
Index_Key: IIO-PARITY
Type: Index Operation
Layer: Governance Layer
Status: Proposed (not implemented)
Canonical: true
Version: 1.0
Parent: Index Integrity Operations (IIO)
---

# Parity

## Dependencies

- `IIO-IMMUTABILITY` — Parity checks rely on the guarantee that records are immutable after creation; mutable records cannot be compared reliably.
- `IIO-CHECKSUM` — Parity verification uses per-record checksums as the atomic unit of comparison.
- `ontology/core.json` — Relation types and status values used in cross-layer comparisons are drawn from the canonical core ontology.

---

## Description

Parity is the Index Integrity Operation that asserts and verifies **structural and representational consistency** between corresponding records across The Index's layered architecture. A pair of Index objects (or two views of the same object) is said to be *in parity* when every semantically equivalent field carries an identical value, every cross-reference resolves symmetrically, and no ghost, orphan, or shadow record exists on either side of a boundary.

Parity is not equality: it is a governance-enforced property that two or more representations of the same knowledge artifact agree on all fields that the protocol designates as *synchronized*. Fields that are intentionally layer-local (e.g., computed quality scores internal to the evidence layer) are excluded from parity scope.

---

## Function

1. **Cross-layer field synchronisation** — For each claim that carries a linked evidence record, Parity asserts that the `source_id` held by the link record matches the authoritative `id` on the source `Claim` object, and that the `target_id` held by the link record matches the authoritative `id` on the target `Evidence` or `Claim` object.

2. **Status coherence** — Parity verifies that the `status` field on a `Claim` object is consistent with the computed `EpistemicStatus` produced by the epistemic engine. A claim whose computed status is `refuted` MUST NOT carry a stored status of `supported`.

3. **Ontology term alignment** — Parity checks that every `relation_type` value stored on a `Link` record resolves to a non-deprecated term in `ontology/core.json`. A link carrying a retired term violates parity.

4. **Provenance chain continuity** — For evidence objects, Parity verifies that the `provenance_chain` recorded at submission time is identical to the chain retrievable at read time. Any divergence indicates an integrity breach.

5. **Bidirectional reference integrity** — When a `Link` asserts `source_id → target_id`, Parity confirms the inverse lookup (all links for that target) also returns the same link record.

---

## Invariants

1. For every `Link` record `L`, `L.source_id` MUST reference an existing `Claim`, and `L.target_id` MUST reference an existing `Evidence` or `Claim`.
2. The stored `Claim.status` MUST equal the status category produced by the most recent `EpistemicStatus` computation for that claim, or the claim MUST be marked as pending a status update.
3. Every `relation_type` value persisted in any `Link` record MUST resolve to an active (non-deprecated) term in the canonical core ontology at the time of the parity check.
4. The SHA-256 checksum stored on an `Evidence` record MUST equal the checksum recomputed from the record's stable fields at any point after creation.
5. No orphan `Link` record MAY exist: every link MUST have at least one corresponding retrieval path from both its source and its target.

---

## Failure Modes

| ID | Failure | Trigger | Severity |
|----|---------|---------|----------|
| F1 | **Dangling link** | A `Link` references a `source_id` or `target_id` that no longer exists in the store (e.g., a partially failed write) | Critical |
| F2 | **Status drift** | `Claim.status` diverges from the most recent `EpistemicStatus.status` computation without a recorded governance override | High |
| F3 | **Deprecated relation term** | A `Link.relation_type` resolves to a term whose `status` is `deprecated` in `ontology/core.json` | High |
| F4 | **Checksum mismatch** | The recomputed SHA-256 of an `Evidence` record's stable fields does not match the stored `evidence.checksum` | Critical |
| F5 | **Asymmetric reference** | A `Link` appears in the source object's link list but not in the target object's link list (or vice versa) | High |
| F6 | **Provenance chain mutation** | The `provenance_chain` retrieved for an `Evidence` record differs from the chain recorded at submission time | Critical |

---

## Enforcement

- **At write time**: The `api/link_layer.py` `LinkStore.store()` method MUST invoke a reference-validation callback before committing a link, rejecting writes that would immediately violate Invariants 1 or 5.
- **At read time**: Any endpoint that returns an `EpistemicStatus` MUST recompute the status rather than serving a stale cached value, preventing Failure Mode F2 from becoming observable to consumers.
- **Scheduled scan**: A governance-layer integrity scan SHOULD run after each batch of writes to verify Invariants 3 and 4 across all stored records. Findings are surfaced as governance proposals of type `RULE_CHANGE` for human review.
- **Ontology update gate**: When `ontology/core.json` is updated to deprecate a relation term, the governance process MUST include a parity migration step that either re-maps or flags all `Link` records carrying that term before the update is marked `EXECUTED`.

---

## Notes

- Parity is a *governance-layer* operation, not a storage-layer constraint. Storage layers enforce immutability and checksums; the governance layer enforces agreement *between* layers and *across* time.
- The term "parity" is intentionally borrowed from distributed systems, where a parity bit detects single-bit errors. Here it generalises to multi-field, multi-record consistency detection.
- Parity checks are non-destructive. A failed parity check produces a finding record (surfaced as a governance proposal) but does NOT automatically modify or delete any record. All remediation requires explicit attestation from a BitRep identity.
- Future versions of this operation may incorporate Merkle-tree-based parity proofs to enable efficient incremental verification over large record sets.
