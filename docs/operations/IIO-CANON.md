---
Title: Canonicalization
Index_Key: IIO-CANON
Type: Index Operation
Layer: Governance Layer
Status: Proposed (not implemented)
Canonical: true
Version: 1.0
Parent: Index Integrity Operations (IIO)
---

# Canonicalization

## Dependencies

- `IIO-PARITY` — Canonicalization relies on Parity to confirm that the record being canonicalized is internally consistent before a canonical identifier is assigned.
- `ontology/core.json` — The set of valid `relation_type` and `status` values that may appear in a canonical record is drawn exclusively from the active terms in the core ontology.

---

## Description

Canonicalization is the Index Integrity Operation that establishes and enforces the single authoritative form of each record, identifier, and term across all layers of The Index. A record is *canonical* when its identifier resolves to exactly one live object, its fields conform to the active schema version, its status is drawn from the ontology vocabulary, and no duplicate or shadow representation of the same knowledge artifact exists at any other address.

Canonicalization is not deduplication in the data-warehouse sense; it is a governance-enforced property that the protocol maintains exactly one authoritative binding for each semantic entity. Multiple syntactic representations of the same claim are collapsed to a single canonical record, and all references to superseded representations are rebounded to the canonical address (see `IIO-REBIND`).

---

## Function

1. **Canonical identifier assignment** — When a new `Claim` or `Evidence` record is created, Canonicalization verifies that no existing record carries an equivalent `canonical_text` (for claims) or `source_identifier` (for evidence). If a duplicate is detected, the new record is rejected and the submitter is directed to the canonical record's `id`.

2. **Status vocabulary enforcement** — Canonicalization checks that every `Claim.status` value is a member of the active status vocabulary in `ontology/core.json` (`proposed`, `supported`, `contested`, or `refuted`). Records carrying non-vocabulary status values are flagged and quarantined until corrected.

3. **Relation-type vocabulary enforcement** — Canonicalization checks that every `Link.relation_type` value is a member of the active relation vocabulary in `ontology/core.json`. Links carrying non-vocabulary relation types are rejected at write time.

4. **Schema conformance validation** — Canonicalization verifies that every stored record conforms to the currently active JSON schema (`schema/claim.schema.json`, `schema/evidence.schema.json`, or `schema/link.schema.json`). Records that fail schema validation are quarantined and a governance proposal of type `SCHEMA_CHANGE` is emitted.

5. **Duplicate detection and merge marking** — When a governance-authorized merge identifies two records as representing the same semantic entity, Canonicalization designates one as the canonical record and marks the other as `merged_into: <canonical_id>`. All subsequent reads and links route to the canonical record.

---

## Invariants

1. For every semantic entity in The Index, exactly one `Claim` or `Evidence` record MUST be designated canonical; no two live records MAY represent the same entity without one being marked `merged_into`.
2. Every `Claim.status` value MUST be a member of the active status vocabulary in `ontology/core.json` at the time of the canonicalization check.
3. Every `Link.relation_type` value MUST be a member of the active relation vocabulary in `ontology/core.json` at the time of the canonicalization check.
4. Every stored record MUST conform to the active JSON schema for its type; schema-non-conformant records MUST be quarantined before they become visible to read endpoints.
5. A record marked `merged_into` MUST NOT be returned by any read endpoint as a primary result; all lookups MUST redirect to the canonical record.

---

## Failure Modes

| ID | Failure | Trigger | Severity |
|----|---------|---------|----------|
| F1 | **Duplicate canonical record** | Two live records exist with equivalent `canonical_text` or `source_identifier` and neither is marked `merged_into` | Critical |
| F2 | **Out-of-vocabulary status** | A `Claim.status` value does not appear in the active status vocabulary of `ontology/core.json` | High |
| F3 | **Out-of-vocabulary relation type** | A `Link.relation_type` value does not appear in the active relation vocabulary of `ontology/core.json` | High |
| F4 | **Schema non-conformance** | A stored record fails validation against its active JSON schema | High |
| F5 | **Dangling merge pointer** | A record's `merged_into` field references a record `id` that does not exist in the store | Critical |
| F6 | **Read bypass of merged record** | A read endpoint returns a record marked `merged_into` as a primary result rather than redirecting to the canonical record | Medium |

---

## Enforcement

- **At write time**: The `api/claim_layer.py` `ClaimStore.store()` method MUST reject records whose `canonical_text` matches an existing live claim, preventing Failure Mode F1.
- **At write time**: The `api/link_layer.py` `LinkStore._validate_invariants()` method MUST reject links whose `relation_type` is not in the active ontology vocabulary, preventing Failure Mode F3.
- **Scheduled scan**: A governance-layer canonicalization scan SHOULD run after each ontology update to identify records whose status or relation-type values have been rendered out-of-vocabulary by the update. Findings are surfaced as governance proposals of type `ONTOLOGY_UPDATE`.
- **Merge workflow**: When a merge is authorized by a governance proposal, the `merged_into` pointer MUST be written atomically with the removal of the duplicate from all live read indexes.

---

## Notes

- Canonicalization is the foundational identity operation. `IIO-REBIND` depends on it: a rebind can only target a canonical record.
- The distinction between *canonical* and *current* matters: a record can be canonical (the authoritative representation) while its content evolves through authorized governance mutations.
- Canonicalization checks are enforced at write time and during scheduled scans; they are not enforced lazily at read time, to avoid non-deterministic read latency.
- Future versions may incorporate content-addressed identifiers (e.g., IPFS CIDs) to make canonicality structurally self-evident rather than governance-enforced.
