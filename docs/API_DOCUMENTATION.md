> **Legacy API:** process-local, non-authoritative for blockchain state. Existing
> claim PUT/DELETE now return 409 to preserve accepted history. Use the local
> [blockchain protocol](../chain/README.md) for explicit revisions/lifecycle events.
> Legacy identity strings and scores do not establish BitRep verification.

# API Documentation

The Index provides a RESTful API for managing claims, evidence, links, and governance proposals.

**Base URL**: `http://localhost:8000/api/v1`

**Interactive Documentation**: `http://localhost:8000/docs`

## Table of Contents

- [Authentication](#authentication)
- [Claims API](#claims-api)
- [Evidence API](#evidence-api)
- [Governance API](#governance-api)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

## Authentication

**Current Status**: Placeholder authentication

In the current version, authentication is placeholder-based. Production systems will integrate with BitRep for cryptographic identity verification.

Required headers (placeholder):
```
X-User-ID: your_bitrep_identity
```

## Claims API

### Create Claim

Creates a new scientific claim.

**Endpoint**: `POST /claims/`

**Request Body**:
```json
{
  "canonical_text": "Quantum entanglement persists over macroscopic distances",
  "semantic_representation": {
    "subject": "quantum_entanglement",
    "predicate": "persists"
  },
  "domains": ["quantum_physics", "experimental_physics"],
  "created_by": "bitrep_id_123"
}
```

**Response** (201 Created):
```json
{
  "id": "claim_abc123",
  "canonical_text": "Quantum entanglement persists over macroscopic distances",
  "semantic_representation": {
    "subject": "quantum_entanglement",
    "predicate": "persists"
  },
  "domains": ["quantum_physics", "experimental_physics"],
  "status": "proposed",
  "created_by": "bitrep_id_123",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Get Claim

Retrieves a specific claim by ID.

**Endpoint**: `GET /claims/{claim_id}`

**Response** (200 OK):
```json
{
  "id": "claim_abc123",
  "canonical_text": "Quantum entanglement persists over macroscopic distances",
  "status": "supported",
  ...
}
```

**Error Response** (404 Not Found):
```json
{
  "detail": "Claim not found"
}
```

### List Claims

Lists claims with optional filtering and pagination.

**Endpoint**: `GET /claims/`

**Query Parameters**:
- `status` (optional): Filter by status (proposed, supported, contested, refuted, deprecated)
- `domain` (optional): Filter by domain tag
- `limit` (optional, default=100, max=1000): Maximum results
- `offset` (optional, default=0): Pagination offset

**Example**: `GET /claims/?status=supported&domain=quantum_physics&limit=50`

**Response** (200 OK):
```json
[
  {
    "id": "claim_abc123",
    "canonical_text": "...",
    "status": "supported",
    ...
  },
  ...
]
```

### Update Claim

Updates an existing claim.

**Endpoint**: `PUT /claims/{claim_id}`

**Request Body**:
```json
{
  "canonical_text": "Updated claim text",
  "status": "supported"
}
```

**Response** (200 OK): Updated claim object

### Delete Claim

Deletes a claim.

**Endpoint**: `DELETE /claims/{claim_id}`

**Response** (204 No Content)

### Search Claims

Searches claims by text query.

**Endpoint**: `GET /claims/search/`

**Query Parameters**:
- `q` (required): Search query string
- `limit` (optional, default=100): Maximum results

**Example**: `GET /claims/search/?q=quantum%20mechanics`

**Response** (200 OK): Array of matching claims

## Evidence API

### Submit Evidence

Submits new evidence to the system.

**Endpoint**: `POST /evidence/`

**Request Body**:
```json
{
  "type": "experiment",
  "source_identifier": "doi:10.1234/example",
  "metadata": {
    "methodology": "double-blind RCT",
    "sample_size": 1000,
    "uncertainty": 0.05,
    "instrumentation": "quantum detector v2.0",
    "replication_history": ["study_001", "study_002"]
  },
  "submitted_by": "bitrep_id_456"
}
```

**Evidence Types**:
- `experiment`: Experimental results
- `observation`: Observational data
- `dataset`: Data collection
- `simulation`: Computational simulation
- `theorem`: Mathematical proof
- `meta_analysis`: Meta-analysis of multiple studies

**Response** (201 Created):
```json
{
  "id": "evidence_xyz789",
  "type": "experiment",
  "source_identifier": "doi:10.1234/example",
  "metadata": {...},
  "submitted_by": "bitrep_id_456",
  "quality_score": 0.85,
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Get Evidence

Retrieves specific evidence by ID.

**Endpoint**: `GET /evidence/{evidence_id}`

**Response** (200 OK): Evidence object

### List Evidence

Lists all evidence with pagination.

**Endpoint**: `GET /evidence/`

**Query Parameters**:
- `limit` (optional, default=100): Maximum results
- `offset` (optional, default=0): Pagination offset

**Response** (200 OK): Array of evidence objects

### Create Link

Creates a link between a claim and evidence (or another claim).

**Endpoint**: `POST /evidence/links`

**Request Body** (Claim-Evidence Link):
```json
{
  "claim_id": "claim_abc123",
  "evidence_id": "evidence_xyz789",
  "relation_type": "supports",
  "strength": 0.9,
  "attested_by": "bitrep_id_789"
}
```

**Request Body** (Claim-Claim Link):
```json
{
  "claim_id": "claim_abc123",
  "claim_id_2": "claim_def456",
  "relation_type": "refines",
  "strength": 0.8,
  "attested_by": "bitrep_id_789"
}
```

**Relation Types**:
- `supports`: Evidence supports the claim
- `contradicts`: Evidence contradicts the claim
- `weakly_supports`: Weak support
- `refines`: One claim refines another
- `generalizes`: One claim generalizes another
- `depends_on`: One claim depends on another
- `conflicts_with`: Claims are in conflict

**Response** (201 Created):
```json
{
  "id": "link_123abc",
  "claim_id": "claim_abc123",
  "evidence_id": "evidence_xyz789",
  "relation_type": "supports",
  "strength": 0.9,
  "attested_by": "bitrep_id_789",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

### Get Links for Claim

Retrieves all links associated with a claim.

**Endpoint**: `GET /evidence/links/claim/{claim_id}`

**Response** (200 OK): Array of link objects

### Get Links for Evidence

Retrieves all links associated with evidence.

**Endpoint**: `GET /evidence/links/evidence/{evidence_id}`

**Response** (200 OK): Array of link objects

### Get Epistemic Status

Computes and retrieves the epistemic status for a claim.

**Endpoint**: `GET /evidence/epistemic-status/{claim_id}`

**Response** (200 OK):
```json
{
  "claim_id": "claim_abc123",
  "status": "supported",
  "supporting_weight": 8.5,
  "contradicting_weight": 1.2,
  "independence_score": 0.75,
  "robustness_score": 0.82,
  "last_computed_at": "2024-01-01T00:00:00Z"
}
```

**Status Categories**:
- `proposed`: Initial status, minimal evidence
- `supported`: Strong supporting evidence (weight > 2.0)
- `contested`: Mixed or conflicting evidence
- `refuted`: Strong contradicting evidence (weight > 3.0)
- `deprecated`: No longer relevant

**Weight Calculation**:
Weight = Evidence Quality Score × Link Strength × Reputation (from BitRep)

## Governance API

### Create Proposal

Creates a new governance proposal.

**Endpoint**: `POST /governance/proposal`

**Request Body**:
```json
{
  "title": "Add new relation type: partially_supports",
  "description": "Proposal to add a new relation type for partial support",
  "proposal_type": "relation_type",
  "proposed_changes": {
    "new_relation": "partially_supports",
    "description": "For evidence that provides partial support"
  },
  "proposer": "bitrep_id_123"
}
```

**Proposal Types**:
- `schema_change`: Database schema modifications
- `ontology_update`: Concept taxonomy changes
- `relation_type`: New or modified relation types
- `rule_change`: System rule modifications
- `parameter_update`: Configuration parameter changes

**Response** (201 Created):
```json
{
  "id": "proposal_abc123",
  "title": "Add new relation type: partially_supports",
  "description": "...",
  "proposal_type": "relation_type",
  "proposed_changes": {...},
  "proposer": "bitrep_id_123",
  "status": "draft",
  "created_at": "2024-01-01T00:00:00Z",
  "voting_starts_at": null,
  "voting_ends_at": null,
  "executed_at": null,
  "yes_votes": 0.0,
  "no_votes": 0.0,
  "abstain_votes": 0.0
}
```

### Activate Proposal

Activates a proposal for voting.

**Endpoint**: `POST /governance/proposal/{proposal_id}/activate`

**Query Parameters**:
- `voting_duration_days` (optional, default=7, range=1-30): Voting period in days

**Response** (200 OK):
```json
{
  "id": "proposal_abc123",
  "status": "active",
  "voting_starts_at": "2024-01-01T00:00:00Z",
  "voting_ends_at": "2024-01-08T00:00:00Z",
  ...
}
```

### Get Proposal

Retrieves a specific proposal by ID.

**Endpoint**: `GET /governance/proposal/{proposal_id}`

**Response** (200 OK): Proposal object

### List Proposals

Lists governance proposals with optional filtering.

**Endpoint**: `GET /governance/proposal`

**Query Parameters**:
- `status` (optional): Filter by status (draft, active, passed, rejected, executed)
- `limit` (optional, default=100): Maximum results
- `offset` (optional, default=0): Pagination offset

**Response** (200 OK): Array of proposal objects

### Cast Vote

Casts a reputation-weighted vote on a proposal.

**Endpoint**: `POST /governance/vote`

**Request Body**:
```json
{
  "proposal_id": "proposal_abc123",
  "voter": "bitrep_id_456",
  "choice": "yes",
  "reputation": 100.0
}
```

**Vote Choices**:
- `yes`: Support the proposal
- `no`: Oppose the proposal
- `abstain`: Abstain from voting

**Quadratic Voting**:
Weighted Vote = sqrt(Reputation Score)

This reduces the influence of high-reputation voters and promotes democratic decision-making.

**Response** (201 Created):
```json
{
  "id": "vote_xyz789",
  "proposal_id": "proposal_abc123",
  "voter": "bitrep_id_456",
  "choice": "yes",
  "reputation": 100.0,
  "weighted_vote": 10.0,
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**Error Response** (400 Bad Request):
```json
{
  "detail": "Voting not allowed. Proposal may not be active, voting period ended, or already voted."
}
```

### Finalize Proposal

Finalizes a proposal after voting ends.

**Endpoint**: `POST /governance/finalize`

**Request Body**:
```json
{
  "proposal_id": "proposal_abc123",
  "finalizer": "bitrep_id_789"
}
```

**Response** (200 OK):
```json
{
  "id": "proposal_abc123",
  "status": "passed",
  "executed_at": "2024-01-08T00:00:00Z",
  "yes_votes": 30.0,
  "no_votes": 5.0,
  ...
}
```

**Passing Criteria**:
- Voting period must have ended
- Yes/(Yes+No) ratio must exceed quorum threshold (default: 50%)

### Get Proposal Votes

Retrieves all votes for a specific proposal.

**Endpoint**: `GET /governance/proposal/{proposal_id}/votes`

**Response** (200 OK): Array of vote objects

## Error Handling

The API uses standard HTTP status codes:

- `200 OK`: Successful request
- `201 Created`: Resource successfully created
- `204 No Content`: Successful deletion
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

**Error Response Format**:
```json
{
  "detail": "Error message description"
}
```

**Validation Error Format**:
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Rate Limiting

**Current Status**: Not implemented

Future versions will implement rate limiting based on:
- IP address
- BitRep identity
- Reputation score

Expected limits:
- Standard users: 100 requests/minute
- High-reputation users: 1000 requests/minute

## Versioning

The API uses URL versioning:
- Current version: `/api/v1`
- Future versions will use `/api/v2`, etc.

Breaking changes will only occur in major version updates.

## Pagination

All list endpoints support pagination:
- `limit`: Maximum results per page (default: 100, max: 1000)
- `offset`: Number of results to skip (default: 0)

**Example**:
```
GET /claims/?limit=50&offset=100
```

Returns claims 101-150.

## Best Practices

### 1. Use Appropriate HTTP Methods
- `GET`: Retrieve resources
- `POST`: Create resources
- `PUT`: Update resources
- `DELETE`: Delete resources

### 2. Handle Errors Gracefully
Always check HTTP status codes and handle errors appropriately.

### 3. Use Pagination for Large Result Sets
Don't request all data at once. Use pagination for better performance.

### 4. Cache Responses When Appropriate
Cache epistemic status computations and claim data when possible.

### 5. Provide Complete Metadata
Include as much metadata as possible when submitting evidence for better quality scoring.

## Client Libraries

**Coming Soon**: Official client libraries for:
- Python
- JavaScript/TypeScript
- Go
- Rust

## Support

For API support:
- GitHub Issues: [https://github.com/clarity-index/the-index/issues](https://github.com/clarity-index/the-index/issues)
- Documentation: [https://github.com/clarity-index/the-index/docs](https://github.com/clarity-index/the-index/docs)
