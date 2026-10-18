---
Title: Traversal Optimization
Index_Key: IIO-TRAVERSE
Type: Index Operation
Layer: Governance Layer
Status: Proposed (not implemented)
Canonical: true
Version: 1.0
Parent: Index Integrity Operations (IIO)
---

# Traversal Optimization

## Dependencies

- `IIO-PARITY` — Traversal Optimization requires all link records to be in parity before path indexes are built; traversing a graph with parity violations produces incorrect or incomplete results.
- `IIO-LINEAGE` — Lineage chain completeness is a prerequisite for full-depth ancestor and descendant traversals; Traversal Optimization depends on Lineage to ensure no ancestry edge is missing.

---

## Description

Traversal Optimization is the Index Integrity Operation that ensures all graph traversal paths through the link layer are consistent, complete, and non-redundant. The link graph of The Index — composed of `Link` records connecting `Claim` and `Evidence` objects — must support efficient and correct traversals in both directions (source → target and target → source), across multiple relation types, and at arbitrary depth without producing duplicate or missing results.

Traversal Optimization does not modify the semantic content of any record; it maintains and validates the auxiliary index structures that the `LinkStore` uses to answer traversal queries (`list_by_source`, `list_by_target`, `list_by_relation`). A traversal inconsistency is a state in which these indexes return results that do not match the ground truth stored in the primary link store.

---

## Function

1. **Forward index consistency** — For every `Link` record `L`, Traversal Optimization verifies that `L.id` appears in `_links_by_source[L.source_id]` in the `LinkStore`. Any link absent from the forward index is an index gap and constitutes a traversal inconsistency.

2. **Reverse index consistency** — For every `Link` record `L`, Traversal Optimization verifies that `L.id` appears in `_links_by_target[L.target_id]` in the `LinkStore`. Any link absent from the reverse index is a reverse index gap.

3. **Relation-type index consistency** — For every `Link` record `L`, Traversal Optimization verifies that `L.id` appears in `_links_by_relation[L.relation_type]` in the `LinkStore`. Any link absent from the relation-type index is a relation index gap.

4. **Stale index entry removal** — Traversal Optimization identifies entries in the three traversal indexes (`_links_by_source`, `_links_by_target`, `_links_by_relation`) that reference link IDs which no longer exist in the primary store (e.g., following a rebind that marked an old link as rebound). Stale entries are flagged and removed under governance authorization.

5. **Depth-bounded reachability verification** — For a governance-specified sample of `Claim` records, Traversal Optimization executes a bounded-depth traversal (forward and reverse) and verifies that every reachable `Link` and terminal `Evidence` record is live and passes an `IIO-PARITY` check.

---

## Invariants

1. For every `Link` record `L` in the primary store, `L.id` MUST appear in `_links_by_source[L.source_id]`, `_links_by_target[L.target_id]`, and `_links_by_relation[L.relation_type]`.
2. No entry in any traversal index (`_links_by_source`, `_links_by_target`, `_links_by_relation`) MAY reference a link ID that does not exist in the primary link store.
3. The set of link IDs reachable from a given `source_id` via `list_by_source()` MUST equal the set of link IDs reachable from the same `source_id` via a full scan of the primary store filtered by `source_id`.
4. All traversal indexes MUST be updated atomically with every write to the primary link store; no window MAY exist during which the indexes are inconsistent with the primary store.
5. Depth-bounded traversals MUST NOT return duplicate link records regardless of the number of traversal paths that lead to the same link.

---

## Failure Modes

| ID | Failure | Trigger | Severity |
|----|---------|---------|----------|
| F1 | **Forward index gap** | A `Link` exists in the primary store but is absent from `_links_by_source` | High |
| F2 | **Reverse index gap** | A `Link` exists in the primary store but is absent from `_links_by_target` | High |
| F3 | **Relation index gap** | A `Link` exists in the primary store but is absent from `_links_by_relation` | High |
| F4 | **Stale index entry** | A traversal index entry references a link ID that no longer exists in the primary store | Medium |
| F5 | **Duplicate traversal result** | A bounded-depth traversal returns the same `Link` record more than once | Medium |
| F6 | **Non-atomic index update** | A write to the primary link store completes but one or more index updates fail, leaving indexes inconsistent | Critical |

---

## Enforcement

- **At write time**: The `api/link_layer.py` `LinkStore.store()` method updates all three traversal indexes (`_links_by_source`, `_links_by_target`, `_links_by_relation`) in the same call that writes the link to the primary store, preventing Failure Mode F6.
- **Scheduled scan**: A traversal consistency scan SHOULD run after each batch of writes, invoking the forward, reverse, and relation-type consistency checks across the full link store. Gaps are surfaced as governance findings of type `RULE_CHANGE`.
- **Post-rebind sweep**: After any `IIO-REBIND` batch, a targeted traversal scan MUST be run against all indexes to detect and remove stale entries for rebound link IDs.
- **Depth-bounded sampling**: A configurable sample of reachability traversals SHOULD run on each governance review cycle to catch accumulated index drift that point-in-time write checks cannot detect.

---

## Notes

- Traversal Optimization is an *auxiliary integrity* operation: it validates the indexes that accelerate query execution rather than the primary data records themselves.
- Index gaps (Failure Modes F1–F3) do not corrupt the primary store; they cause queries to return incomplete results. This makes them lower severity than primary-store corruption but high enough to warrant prompt remediation.
- The `LinkStore`'s in-memory index architecture makes non-atomic updates (Failure Mode F6) a critical risk; the enforcement requirement for atomic index updates is non-negotiable.
- Future versions may extend Traversal Optimization to cover cross-layer traversals spanning the claim, evidence, and governance layers simultaneously.
