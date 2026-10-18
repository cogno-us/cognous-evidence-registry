---
Title: Rebinding
Index_Key: IIO-REBIND
Type: Index Operation
Layer: Governance Layer
Status: Proposed (not implemented)
Canonical: true
Version: 1.0
Parent: Index Integrity Operations (IIO)
---

# Rebinding

## Dependencies

- `IIO-CANON` — Rebinding can only target a record that has been designated canonical; the destination of every rebind MUST pass a Canonicalization check before the rebind is committed.
- `IIO-LINEAGE` — Every rebind operation MUST be recorded in the affected record's lineage chain so that the full history of identifier changes is recoverable.
- `IIO-PARITY` — After a rebind is applied, a Parity check MUST be run across all records that held a reference to the rebound identifier to confirm that no dangling references remain.

---

## Description

Rebinding is the Index Integrity Operation that updates all live link and reference records when a canonical identifier or ontology term is superseded by an authorized replacement. A *rebind* occurs when a governance-authorized action (executed via a `RULE_CHANGE` or `ONTOLOGY_UPDATE` proposal) changes the identifier under which a record or term is addressed, requiring all existing references to be atomically migrated to the new identifier.

Rebinding preserves the semantic continuity of the knowledge graph: no claim-to-evidence or claim-to-claim relationship is silently broken by an identifier change. The protocol guarantees that after a successful rebind, every `Link` that referenced the old identifier resolves to the same semantic target via the new identifier.

---

## Function

1. **Reference enumeration** — Before applying a rebind, Rebinding enumerates all `Link` records whose `source_id` or `target_id` equals the identifier being rebound. This enumeration is performed via `LinkStore.list_by_source()` and `LinkStore.list_by_target()` in `api/link_layer.py`.

2. **Atomic reference migration** — For each enumerated `Link`, Rebinding writes a new `Link` record with the updated identifier, carries over all other fields unchanged, recomputes the `immutable_hash` for the new record, and marks the old record as `rebound_to: <new_link_id>`.

3. **Ontology term rebinding** — When a `relation_type` term is deprecated and replaced in `ontology/core.json`, Rebinding updates all `Link` records whose `relation_type` equals the deprecated term to carry the replacement term, subject to explicit governance authorization.

4. **Canonical redirect registration** — After every rebind, a redirect entry is written to the canonical address registry mapping the old identifier to the new one. Subsequent lookups for the old identifier MUST follow the redirect and return the record at the new address.

5. **Post-rebind parity verification** — After the full rebind batch is committed, a Parity check is triggered across all affected records to confirm that no dangling references to the old identifier remain.

---

## Invariants

1. A rebind MUST be authorized by an executed governance proposal (`RULE_CHANGE` or `ONTOLOGY_UPDATE`) before any reference migration is applied.
2. The destination identifier of every rebind MUST designate an existing canonical record that passes an `IIO-CANON` check at the time of the rebind.
3. Every `Link` updated by a rebind MUST have its `immutable_hash` recomputed after the field update; the old `immutable_hash` MUST be recorded in the lineage entry for the link.
4. The old identifier MUST remain resolvable via the canonical redirect registry for the full retention period specified by the active governance rule; it MUST NOT return a 404 response.
5. After a rebind is committed, a post-rebind Parity scan MUST confirm zero dangling references to the old identifier before the rebind is marked complete.

---

## Failure Modes

| ID | Failure | Trigger | Severity |
|----|---------|---------|----------|
| F1 | **Unauthorized rebind** | A reference migration is applied without a corresponding executed governance proposal | Critical |
| F2 | **Dangling old reference** | One or more `Link` records still reference the old identifier after the rebind batch is committed | Critical |
| F3 | **Non-canonical rebind target** | The destination identifier of a rebind does not designate a live canonical record | High |
| F4 | **Hash recomputation omission** | A rebound `Link` record's `immutable_hash` is not recomputed after the identifier field is updated | High |
| F5 | **Missing redirect entry** | The old identifier is not registered in the canonical redirect registry after the rebind | High |
| F6 | **Partial batch failure** | A rebind batch applies to some but not all enumerated references, leaving the graph in a split state | Critical |

---

## Enforcement

- **Pre-rebind gate**: Before executing a rebind, the governance process MUST verify that the destination identifier exists and passes `IIO-CANON`. The rebind MUST be rejected if this check fails.
- **Atomic batch execution**: All reference migrations in a rebind batch MUST be applied atomically. If any single migration fails, the entire batch MUST be rolled back and the failure surfaced as a governance finding.
- **Post-rebind scan**: `api/link_layer.py` `LinkStore.list_by_source()` and `LinkStore.list_by_target()` MUST be invoked with the old identifier after the rebind to confirm zero remaining references. Any non-empty result triggers Failure Mode F2.
- **Redirect durability**: The canonical redirect registry MUST persist redirect entries for a retention period no shorter than the governance-specified retention window, ensuring backward compatibility for external consumers.

---

## Notes

- Rebinding is a *destructive* write operation in the sense that it modifies existing records, unlike most other IIO operations which are non-destructive. This is why governance authorization and lineage recording are mandatory prerequisites.
- The Rebinding operation is the primary mechanism by which ontology evolution (term deprecation and replacement) is propagated into the live link graph without silent data loss.
- A rebind does not change the semantic content of any claim or evidence record; it only updates the addresses by which records refer to each other.
- Future versions may support symbolic rebind references (forwarding pointers at the storage layer) to avoid full record rewriting in high-volume rebind scenarios.
