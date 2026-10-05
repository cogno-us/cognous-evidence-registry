> **Legacy design specification.** This document is preserved for history. It does
> not establish implemented decentralization, BitRep reputation or cryptographic
> assurance. The bounded blockchain reference profile and explicit divergences are
> in [chain/PROTOCOL.md](../chain/PROTOCOL.md).

# INDEX_ARCHITECTURE.md
## The Index — A Normative Protocol Specification for Verifiable Scientific Knowledge

**Version:** 1.0  
**Status:** Draft Specification  
**Date:** 2024-01-23

---

## Table of Contents

1. [Scope and Introduction](#1-scope-and-introduction)
2. [Terminology and Definitions](#2-terminology-and-definitions)
3. [Core Principles](#3-core-principles)
4. [Core Data Model](#4-core-data-model)
5. [Claim Lifecycle](#5-claim-lifecycle)
6. [API Surfaces](#6-api-surfaces)
7. [Ontology Integration](#7-ontology-integration)
8. [Provenance and Attestation](#8-provenance-and-attestation)
9. [Governance Hooks](#9-governance-hooks)
10. [Security and Integrity Considerations](#10-security-and-integrity-considerations)
11. [Versioning and Evolution](#11-versioning-and-evolution)

---

## 1. Scope and Introduction

### 1.1 Purpose

The Index is a normative protocol specification for representing, linking, and evaluating verifiable scientific knowledge. This document defines the requirements and architecture for implementations of The Index protocol.

### 1.2 Scope

This specification defines:

- Core data models for claims, evidence, and relationships
- Protocol invariants that implementations MUST enforce
- API surfaces for interacting with The Index
- Integration requirements with BitRep identity substrate
- Governance mechanisms for protocol evolution

This specification does NOT define:

- Specific storage backends or database schemas
- User interface requirements
- Authentication mechanisms (delegated to BitRep)
- Specific cryptographic algorithms (delegated to BitRep)

### 1.3 Relationship to BitRep

The Index MUST be built on top of BitRep, which provides:

- Cryptographic identities for all contributors
- Attestation mechanisms for provenance
- Reputation scoring for weighted evidence
- Governance infrastructure for protocol evolution
- Privacy and selective disclosure capabilities

Implementations of The Index MUST NOT implement their own identity, attestation, or reputation systems.

### 1.4 Conformance Keywords

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in RFC 2119.

**Glossary of Normative Keywords:**

- **MUST** / **REQUIRED** / **SHALL**: This word means that the definition is an absolute requirement of the specification.
- **MUST NOT** / **SHALL NOT**: This phrase means that the definition is an absolute prohibition of the specification.
- **SHOULD** / **RECOMMENDED**: This word means that there may exist valid reasons in particular circumstances to ignore a particular item, but the full implications must be understood and carefully weighed before choosing a different course.
- **SHOULD NOT** / **NOT RECOMMENDED**: This phrase means that there may exist valid reasons in particular circumstances when the particular behavior is acceptable or even useful, but the full implications should be understood and the case carefully weighed before implementing any behavior described with this label.
- **MAY** / **OPTIONAL**: This word means that an item is truly optional. One implementation may choose to include the item because a particular marketplace requires it or because the implementation feels that it enhances the product while another implementation may omit the same item.

---

## 2. Terminology and Definitions

### 2.1 Core Terms

**Claim**: An atomic scientific statement with structured semantic representation (subject-predicate-object) and attribution to a BitRep identity.

**Evidence**: An empirical or theoretical artifact that supports, contradicts, or refines claims. Evidence MUST be linked to at least one claim.

**Link**: An attested relationship between a claim and evidence, or between two claims. Links MUST specify a relation type and MAY include strength weighting.

**Epistemic Status**: A computed assessment of a claim's standing based on weighted evidence and link relationships.

**Contributor**: A participant in The Index identified by a BitRep identity. All actions MUST be attributed to a contributor.

**Protocol Invariant**: A requirement that implementations MUST enforce at all times to maintain protocol integrity.

### 2.2 Epistemic Terms

**Supporting Weight**: The sum of weighted supporting links for a claim, adjusted by contributor reputation.

**Contradicting Weight**: The sum of weighted contradicting links for a claim, adjusted by contributor reputation.

**Independence**: A measure of diversity in evidence sources and contributor identities for a claim.

**Robustness**: A measure of replication, methodological quality, and cross-domain consistency for a claim.

---

## 3. Core Principles

### 3.1 Verifiability

All claims, evidence, and links MUST be:
- Attributed to a BitRep identity
- Cryptographically signed via BitRep attestations
- Independently verifiable by any observer

Implementations MUST reject unsigned or unattributed contributions.

### 3.2 Modularity

The protocol MUST maintain clear separation between:
- The claim layer (scientific statements)
- The evidence layer (supporting artifacts)
- The link layer (relationships)
- The governance layer (protocol evolution)

These layers MUST interoperate through well-defined interfaces.

### 3.3 Epistemic Transparency

The epistemic status of any claim MUST be:
- Computable from public data
- Derived using deterministic algorithms
- Reproducible by independent implementations

Implementations MUST NOT use subjective judgment or hidden signals in status computation.

### 3.4 Decentralization

The protocol MUST NOT require:
- Central authority for truth determination
- Privileged administrators with special powers
- Single points of failure

Protocol evolution MUST occur through decentralized governance.

### 3.5 Reputation Weighting

Evidence and links MUST be weighted by the BitRep reputation of contributors. Implementations MUST apply reputation weighting consistently in epistemic status computation.

### 3.6 Deterministic Computation

Epistemic status computation MUST be deterministic. Given identical input data and algorithm parameters, all implementations MUST produce identical results.

### 3.7 Schema Validation and Rejection

**Protocol Guarantee: Schema Violations Result in Rejection**

Implementations MUST enforce strict schema validation for all objects. This guarantee ensures data integrity and protocol compliance:

1. **Schema Violations MUST Result in Rejection**:
   - Any object that does not conform to its JSON schema MUST be rejected
   - Rejection MUST occur before persistence to storage
   - Rejection responses MUST include descriptive error messages
   - HTTP 400 Bad Request MUST be returned for schema violations

2. **Required Field Validation**:
   - All required fields MUST be present
   - Required fields MUST NOT be null or undefined
   - String fields MUST meet minimum length requirements
   - Enum fields MUST have values from the defined set

3. **Format Validation**:
   - IDs MUST match specified patterns (e.g., `claim_[a-zA-Z0-9_-]+`)
   - Timestamps MUST be valid ISO 8601 format
   - URLs MUST be properly formatted where applicable
   - Numeric values MUST be within specified ranges

4. **Reference Validation**:
   - All referenced objects (evidence_refs, claim_id, etc.) MUST exist in the system
   - Circular references MUST be detected and rejected where prohibited
   - Orphaned references MUST be prevented

5. **Ontology Validation**:
   - Predicates MUST reference valid ontology terms
   - Relation types MUST be defined in the core or registered ontologies
   - Evidence types MUST be recognized evidence categories
   - Deprecated ontology terms MUST be rejected for new submissions

---

## 4. Core Data Model

### 4.1 Claim Object

A Claim MUST contain the following required fields:

- `id` (string): Unique identifier matching pattern `claim_[a-zA-Z0-9_-]+`
- `subject` (string): The subject of the claim (non-empty)
- `predicate` (string): The relationship or property being asserted (non-empty)
- `object` (string): What is being asserted about the subject (non-empty)
- `contributor_id` (string): BitRep identity of the creator (non-empty)
- `timestamp` (ISO 8601 datetime): When the claim was created

A Claim MUST contain at least one of:
- `evidence_refs` (array of strings): References to evidence (minimum 1 element if present)
- `justification` (string): Textual justification (non-empty if present)

**Protocol Invariant**: Claims MUST have either evidence_refs OR justification.

A Claim MAY contain:
- `canonical_text` (string): Human-readable claim text
- `semantic_representation` (object): Machine-readable semantic structure
- `domains` (array of strings): Domain tags
- `status` (enum): One of: proposed, supported, contested, refuted, deprecated
- `created_at` (ISO 8601 datetime): Creation timestamp
- `updated_at` (ISO 8601 datetime): Last update timestamp
- `provenance` (object): Attestation and signature information

Implementations MUST validate that all claims conform to these requirements.

### 4.2 Evidence Object

An Evidence object MUST contain:

- `id` (string): Unique identifier matching pattern `evidence_[a-zA-Z0-9_-]+`
- `type` (enum): One of: experiment, observation, dataset, simulation, theorem, meta_analysis
- `source_identifier` (string): External identifier (DOI, arXiv ID, etc.)
- `submitted_by` (string): BitRep identity of submitter
- `created_at` (ISO 8601 datetime): Submission timestamp

An Evidence object MAY contain:

- `metadata` (object): Domain-specific metadata including:
  - `methodology` (string)
  - `sample_size` (integer)
  - `uncertainty` (float)
  - `instrumentation` (string)
  - `replication_history` (array of strings)
- `quality_score` (float, 0.0-1.0): Computed quality assessment

Evidence MUST be linked to at least one claim to be included in the epistemic graph.

### 4.3 Link Object

A Link MUST contain:

- `id` (string): Unique identifier
- `claim_id` (string): ID of the claim being linked
- `relation_type` (enum): One of: supports, contradicts, weakly_supports, refines, generalizes, depends_on, conflicts_with
- `attested_by` (string): BitRep identity creating the link
- `timestamp` (ISO 8601 datetime): Link creation time

A Link MUST contain exactly one of:
- `evidence_id` (string): ID of linked evidence (for claim-evidence links)
- `claim_id_2` (string): ID of second claim (for claim-claim links)

A Link MAY contain:
- `strength` (float, 0.0-1.0): Relationship strength (default 1.0)

**Protocol Invariant**: Links MUST connect to either evidence OR another claim, never both.

### 4.4 Epistemic Cache

Implementations SHOULD maintain an epistemic cache for performance. A cache entry MUST contain:

- `claim_id` (string): ID of the claim
- `status` (enum): Computed status category
- `supporting_weight` (float): Total weighted support
- `contradicting_weight` (float): Total weighted contradiction
- `independence_score` (float, 0.0-1.0): Evidence diversity measure
- `robustness_score` (float, 0.0-1.0): Quality and replication measure
- `last_computed_at` (ISO 8601 datetime): Cache timestamp

Implementations MUST invalidate cache entries when underlying data changes.

### 4.5 Immutability

**Protocol Guarantee: Immutability of Core Objects**

Claims, evidence, and links MUST be immutable after acceptance into the protocol. This guarantee ensures:

1. **Claims MUST be immutable** after acceptance:
   - All required fields (id, subject, predicate, object, contributor_id, timestamp) MUST NOT be modified
   - Evidence references and justification content MUST NOT be modified
   - Original semantic representation MUST NOT be altered

2. **Evidence objects MUST be immutable**:
   - All fields (id, type, source_identifier, metadata) MUST NOT be modified after creation
   - Provenance chain MUST remain intact and unmodified
   - Checksum values MUST remain constant

3. **Links MUST be append-only**:
   - Links MUST NOT be edited after creation
   - Links MUST NOT be deleted
   - New links MAY be added at any time
   - Link metadata (relation_type, weight, timestamp) MUST be immutable

**Permitted Modifications:**

The following modifications are permitted as they do not violate immutability guarantees:

- **Claim status updates**: Status field MAY be updated via deterministic epistemic computation
- **Cache recomputation**: Computed values in epistemic cache MAY be recalculated
- **Metadata corrections**: Non-semantic metadata MAY be corrected via governance proposals (requires community approval)

**Enforcement Requirements:**

Implementations MUST:
- Preserve creation timestamps for all objects
- Preserve original content in its entirety
- Reject any modification attempts to immutable fields with appropriate error messages
- Maintain audit logs of all access attempts to core objects

---

## 5. Claim Lifecycle

### 5.1 Creation Phase

When a claim is created, implementations MUST:

1. Validate all required fields are present
2. Verify contributor_id corresponds to valid BitRep identity
3. Enforce evidence_refs OR justification requirement
4. Assign unique claim ID
5. Set status to "proposed"
6. Record creation timestamp
7. Store claim persistently

### 5.2 Linking Phase

After creation, contributors MAY:

- Submit evidence and create claim-evidence links
- Create claim-claim links to establish relationships
- Update link strength values

All links MUST be attested by a BitRep identity.

### 5.3 Evaluation Phase

Implementations MUST periodically or on-demand:

1. Compute supporting_weight from supporting links
2. Compute contradicting_weight from contradicting links
3. Calculate independence_score from source diversity
4. Calculate robustness_score from quality metrics
5. Determine status category based on weights
6. Update epistemic cache

### 5.4 Status Categories and State Transitions

**Protocol Guarantee: Deterministic Status Computation**

Status computation MUST be deterministic. Given identical input data (claims, evidence, links, and reputation scores), all implementations MUST produce identical status values.

**Status Definitions:**

Implementations MUST assign status based on these criteria:

- **proposed**: Default initial status. A claim has insufficient supporting or contradicting evidence for evaluation. This is the entry state for all new claims.
  
- **supported**: A claim has strong evidential support. The supporting_weight significantly exceeds contradicting_weight. This indicates the claim is well-established with substantial backing.
  
- **contested**: A claim has comparable supporting and contradicting evidence. The supporting_weight and contradicting_weight are within a similar range, indicating active scientific debate or uncertainty.
  
- **refuted**: A claim has been substantially contradicted. The contradicting_weight significantly exceeds supporting_weight, indicating the claim is considered invalid or false based on current evidence.
  
- **deprecated**: A claim has been superseded, retracted, or removed from active consideration via governance mechanisms. The claim remains in the system for historical purposes but is no longer actively evaluated.

**State Transition Rules:**

Implementations MUST follow these transition rules:

1. **proposed → supported**: 
   - MUST occur when: `supporting_weight > threshold_support AND supporting_weight / (contradicting_weight + 1.0) > ratio_support`
   - Recommended thresholds: `threshold_support = 3.0`, `ratio_support = 2.0`

2. **proposed → contested**:
   - MUST occur when: `supporting_weight > threshold_min AND contradicting_weight > threshold_min AND abs(supporting_weight - contradicting_weight) < threshold_contested`
   - Recommended thresholds: `threshold_min = 1.0`, `threshold_contested = 1.0`

3. **proposed → refuted**:
   - MUST occur when: `contradicting_weight > threshold_refute AND contradicting_weight / (supporting_weight + 1.0) > ratio_refute`
   - Recommended thresholds: `threshold_refute = 3.0`, `ratio_refute = 2.0`

4. **supported ↔ contested ↔ refuted**:
   - Bidirectional transitions are permitted as new evidence is added
   - Transitions MUST be recomputed whenever the link graph changes
   - Status MUST reflect current state of evidence

5. **Any Status → deprecated**:
   - MUST occur only through governance approval or contributor retraction
   - This is a terminal state transition for active evaluation
   - Deprecated claims MUST NOT transition back to other statuses

**Supersession via Explicit Links:**

Claims MAY be superseded through explicit link relationships:

- A claim with `relation_type: refines` pointing to it from a newer claim SHOULD be marked as having a refinement
- A claim with `relation_type: generalizes` pointing to it from a newer claim SHOULD be marked as having a generalization
- Supersession does NOT automatically change status but MAY influence weight calculations
- Governance MAY deprecate superseded claims based on community consensus

**Immutability of State Transitions:**

- Status transitions MUST be logged with timestamp and reason
- Historical status values MUST be preserved for audit purposes
- Status computation MUST be reproducible from stored link weights and timestamps

### 5.5 Deprecation

Claims MAY be deprecated through:
- Governance proposal and vote
- Contributor retraction (for their own claims)
- Community consensus mechanisms

Deprecated claims MUST remain in the graph but SHOULD be marked clearly.

---

## 6. API Surfaces

### 6.1 Required Endpoints

Implementations MUST provide the following HTTP REST API endpoints:

#### 6.1.1 Claim Endpoints

- `POST /claims` - Create a new claim
  - MUST validate protocol invariants
  - MUST return 400 for invalid claims
  - MUST return 201 with claim object on success

- `GET /claims/{id}` - Retrieve a specific claim
  - MUST return 404 if not found
  - MUST return 200 with claim object if found

- `GET /claims` - List claims with filtering
  - MUST support pagination (limit, offset)
  - SHOULD support filtering by status, domain, contributor
  - MUST return 200 with array of claims

- `GET /claims/search` - Search claims by text
  - MUST support full-text search on canonical_text
  - MUST return 200 with array of matching claims

#### 6.1.2 Evidence Endpoints

- `POST /evidence` - Submit new evidence
  - MUST validate required fields
  - MUST return 201 with evidence object on success

- `GET /evidence/{id}` - Retrieve specific evidence
  - MUST return 404 if not found
  - MUST return 200 with evidence object if found

- `GET /evidence` - List evidence with filtering
  - MUST support pagination
  - SHOULD support filtering by type, source

#### 6.1.3 Link Endpoints

- `POST /links` - Create a new link
  - MUST validate claim and evidence/claim_2 exist
  - MUST enforce protocol invariants
  - MUST return 201 with link object on success

- `GET /links` - List links
  - MUST support filtering by claim_id
  - MUST support filtering by relation_type
  - MUST return 200 with array of links

#### 6.1.4 Epistemic Status Endpoints

- `GET /claims/{id}/status` - Get computed epistemic status
  - MUST return current cached status if available
  - SHOULD trigger recomputation if cache is stale
  - MUST return 200 with status object

- `POST /claims/{id}/status/compute` - Force status recomputation
  - MUST recompute from current graph state
  - MUST update cache
  - MUST return 200 with updated status

### 6.2 Optional Endpoints

Implementations MAY provide:

- `GET /graph` - Query subgraphs
- `GET /claims/{id}/dependencies` - Dependency analysis
- `GET /claims/{id}/evidence` - Evidence network for claim
- Graph traversal and visualization endpoints

### 6.3 Error Handling

Implementations MUST return appropriate HTTP status codes:

- 400: Bad Request (invalid input, protocol violations)
- 404: Not Found (resource does not exist)
- 409: Conflict (duplicate IDs, constraint violations)
- 500: Internal Server Error (implementation errors)

Error responses SHOULD include descriptive messages.

---

## 7. Ontology Integration

### 7.1 Ontology Requirements

Implementations SHOULD support a hierarchical ontology for:

- Domain classification
- Predicate vocabularies
- Relation type taxonomies
- Evidence type categorization

### 7.2 Core Ontology

The protocol MUST define a core ontology including:

- Fundamental relation types (supports, contradicts, etc.)
- Basic evidence types (experiment, observation, etc.)
- Standard epistemic status categories

### 7.3 Extended Ontologies

Implementations MAY support extended ontologies for:

- Discipline-specific domains
- Specialized evidence types
- Custom relation types

Extended ontologies MUST be registered through governance.

### 7.4 Ontology Evolution

Ontology changes MUST follow governance procedures:

1. Proposal submission with rationale
2. Community review period
3. Reputation-weighted voting
4. Implementation migration path

Breaking ontology changes MUST be versioned.

---

## 8. Provenance and Attestation

### 8.1 Identity Requirements

All contributions MUST be attributed to a BitRep identity. Implementations MUST:

- Verify BitRep identity signatures
- Reject contributions without valid attribution
- Store contributor_id with all objects

### 8.2 Attestation Anchoring

Claims, evidence, and links SHOULD be anchored as BitRep attestations. Implementations SHOULD:

- Generate attestation for each contribution
- Store attestation ID in provenance metadata
- Support attestation verification

### 8.3 Reputation Integration

Implementations MUST integrate BitRep reputation for:

- Link strength weighting in epistemic computation
- Governance vote weighting
- Quality score calculation

Implementations MUST fetch current reputation scores from BitRep.

### 8.4 Provenance Tracking

Implementations MUST maintain complete provenance chains:

- Original contributor and timestamp
- Modification history (if applicable)
- Attestation signatures
- Reputation scores at time of contribution

---

## 9. Governance Hooks

### 9.1 Governance Scope

Governance MUST cover:

- Schema evolution (adding/modifying fields)
- Ontology updates (new domains, relations, types)
- Protocol parameter changes (status thresholds, weights)
- Conflict resolution (disputed claims, spam)

### 9.2 Proposal Mechanism

Implementations MUST support:

- Proposal submission by any contributor
- Structured proposal format with rationale
- Community review period (RECOMMENDED: 7-14 days)
- Outcome recording in governance log

### 9.3 Voting Mechanism

Implementations MUST implement:

- Reputation-weighted voting via BitRep
- Quadratic scaling (vote_weight = sqrt(reputation))
- Transparent vote tallying
- Quorum requirements

### 9.4 Execution

Approved proposals MUST trigger:

- Automatic schema/ontology updates (if applicable)
- Migration scripts for breaking changes
- Notification to all implementations
- Version increment

---

## 10. Security and Integrity Considerations

### 10.1 Cryptographic Security

Implementations MUST:

- Use BitRep cryptographic signatures for all attestations
- Verify signatures before accepting contributions
- Support signature verification by third parties

Implementations MUST NOT:

- Accept unsigned contributions
- Implement custom cryptographic schemes
- Store private keys

### 10.2 Input Validation

Implementations MUST validate all inputs:

- Field type and format validation
- Length limits on text fields
- Numeric range validation
- Pattern matching for IDs

Implementations MUST reject invalid inputs with descriptive errors.

### 10.3 Sybil Resistance

Implementations MUST leverage BitRep reputation for Sybil resistance:

- Weight contributions by reputation
- Apply diminishing returns for multiple contributions from same identity
- Support community flagging of suspicious behavior

### 10.4 Privacy Considerations

Implementations SHOULD support:

- Selective disclosure via BitRep
- Pseudonymous contribution (real identity hidden)
- Confidential evidence submission with delayed reveal

Implementations MUST NOT:

- Expose private BitRep identity information
- Link pseudonymous identities without consent
- Share data with unauthorized parties

### 10.5 Integrity Guarantees

Implementations MUST ensure:

- Immutability of core objects (claims, evidence, links)
- Deterministic epistemic computation
- Auditability of all actions
- Provenance chain integrity

---

## 11. Versioning and Evolution

### 11.1 Versioning Scheme

The Index protocol uses semantic versioning: MAJOR.MINOR.PATCH

- **MAJOR**: Breaking changes to core data models or protocol invariants
- **MINOR**: Backward-compatible feature additions
- **PATCH**: Bug fixes and clarifications

Current version: 1.0.0

### 11.2 Breaking Changes

Breaking changes MUST:

- Increment MAJOR version
- Provide migration documentation
- Include deprecation period (RECOMMENDED: 6 months minimum)
- Be approved through governance vote

Examples of breaking changes:
- Modifying required fields in core data models
- Changing protocol invariants
- Removing API endpoints
- Incompatible ontology restructuring

### 11.3 Backward Compatibility

Implementations SHOULD maintain backward compatibility for:

- Reading older data formats
- Supporting deprecated API endpoints during transition
- Honoring legacy attestations

### 11.4 Evolution Principles

Protocol evolution MUST follow these principles:

1. **Minimal Disruption**: Prefer additive changes over breaking changes
2. **Community Consensus**: Major changes require governance approval
3. **Migration Support**: Provide tools for transitioning implementations
4. **Documentation**: Update specification and migration guides
5. **Transparency**: Announce changes with rationale and timeline

### 11.5 Implementation Compliance

Implementations MUST declare their protocol version and MUST comply with all MUST/REQUIRED directives for that version.

Implementations SHOULD implement RECOMMENDED features but MAY omit them with justification.

Implementations MAY extend the protocol with additional features but MUST NOT violate protocol invariants.

---

## 12. Conclusion

This specification defines The Index as a protocol for verifiable scientific knowledge built on the BitRep identity substrate. Compliant implementations MUST enforce all protocol invariants, provide required API surfaces, and participate in decentralized governance.

The protocol is designed to evolve through community governance while maintaining integrity, transparency, and decentralization. All implementations share responsibility for upholding these principles.

---

**Document History:**
- Version 1.0 (2024-01-23): Initial normative specification
