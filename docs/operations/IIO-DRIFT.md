---
Title: Drift Detection
Index_Key: IIO-DRIFT
Type: Index Operation
Layer: Governance Layer
Status: Proposed (not implemented)
Canonical: true
Version: 1.0
Parent: Index Integrity Operations (IIO)
---

# Drift Detection

## Dependencies

- `IIO-PARITY` — Drift Detection relies on Parity baselines to determine the last known valid state against which drift is measured.
- `IIO-CHECKSUM` — Per-record checksums serve as the primary signal for detecting silent field mutations.
- `ontology/core.json` — Status and relation-type vocabularies used to classify drift categories are drawn from the canonical core ontology.

---

## Description

Drift Detection is the Index Integrity Operation that identifies when one or more stored records, ontology terms, or protocol-layer values deviate from their last known valid state without a corresponding authorized governance action. A deviation is called *drift* rather than an intentional change if no governance proposal of an appropriate type (`RULE_CHANGE`, `SCHEMA_CHANGE`, or `ONTOLOGY_UPDATE`) has been executed to authorize it.

Drift Detection does not repair drift; it surfaces findings as governance proposals for human review. The distinction between drift and authorized change is maintained by the governance log: every authorized mutation MUST produce a finalized proposal record before the mutation is applied.

---

## Function

1. **Checksum-based field mutation detection** — For every `Evidence` record, Drift Detection recomputes the SHA-256 checksum from the record's stable fields and compares it against the stored `evidence.checksum`. Any mismatch that is not associated with an executed governance proposal is classified as drift.

2. **Status transition auditing** — For every `Claim` record, Drift Detection verifies that each transition in `Claim.status` is traceable to either an `EpistemicStatus` computation result or an explicit governance override. Transitions with no traceable cause are flagged.

3. **Ontology term deprecation propagation** — When a term in `ontology/core.json` is marked `deprecated`, Drift Detection identifies all `Link` records whose `relation_type` equals that term and emits a drift finding for each. The finding persists until a `RULE_CHANGE` proposal is executed to rebind or retire the affected links.

4. **Immutable hash verification** — For every `Link` record, Drift Detection recomputes the `immutable_hash` from the link's stable fields and compares it against the stored value. A mismatch constitutes an integrity drift finding of Critical severity.

5. **Schema version alignment** — Drift Detection checks that the schema version recorded in each stored record matches the version currently active in the protocol. Records serialized under a superseded schema version that have not been migrated are flagged as schema drift.

---

## Invariants

1. Every drift finding MUST be recorded as a governance proposal before any remediation is applied.
2. The drift-finding record MUST reference the affected record's `id`, the type of drift detected, and the timestamp of detection.
3. A drift finding MUST NOT be silently discarded; it MUST remain in the proposal queue until explicitly resolved by an authorized BitRep identity.
4. Checksum recomputation MUST use the same stable-field set and hashing algorithm (`SHA-256`) as the original computation performed at record creation.
5. A `Link` whose `immutable_hash` does not match the recomputed value MUST be quarantined from read endpoints until the discrepancy is resolved.

---

## Failure Modes

| ID | Failure | Trigger | Severity |
|----|---------|---------|----------|
| F1 | **Silent field mutation** | An `Evidence` record's stored checksum does not match the recomputed checksum, with no associated executed proposal | Critical |
| F2 | **Unauthorized status transition** | A `Claim.status` transition carries no traceable `EpistemicStatus` result or governance override | High |
| F3 | **Orphaned deprecated term** | A `Link.relation_type` matches a `deprecated` term in `ontology/core.json` with no pending rebind proposal | High |
| F4 | **Immutable hash corruption** | A `Link.immutable_hash` does not match the value recomputed from its stable fields | Critical |
| F5 | **Schema version mismatch** | A stored record carries a schema version that is no longer active and has not been migrated | Medium |
| F6 | **Unresolved drift backlog** | More than a configurable threshold of drift findings accumulate without resolution, indicating governance lag | High |

---

## Enforcement

- **At write time**: The `api/evidence_layer.py` `EvidenceStore.store()` method computes and persists the initial checksum, establishing the baseline against which Drift Detection compares.
- **At write time**: The `api/link_layer.py` `LinkStore.store()` method computes and persists the `immutable_hash`, establishing the baseline for link integrity.
- **Scheduled scan**: A governance-layer drift scan SHOULD run after each batch of writes. For each finding, a governance proposal of type `RULE_CHANGE` is emitted and surfaced for human review.
- **Ontology update gate**: Before any term deprecation is committed to `ontology/core.json`, the governance process MUST run a Drift Detection pre-check to enumerate all `Link` records that would immediately become drift findings upon the deprecation taking effect.

---

## Notes

- Drift Detection is a *reactive* operation: it detects divergence after it occurs. Proactive prevention is the responsibility of write-time validation in `IIO-PARITY` and `IIO-IMMUTABILITY`.
- The distinction between drift and authorized change is entirely determined by the governance log. An empty governance log means all deviations are drift.
- Drift findings are non-destructive: no record is modified or deleted as a result of detection. All remediation requires explicit attestation from a BitRep identity.
- Future versions may support continuous, event-driven drift detection triggered by individual write operations rather than batch scans.
