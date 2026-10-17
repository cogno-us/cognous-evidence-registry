"""
Pydantic models for The Index.

This module defines the core data models used throughout the application:
- Claims: Scientific statements with canonical text and semantic structure
- Evidence: Empirical or theoretical artifacts supporting claims
- Links: Relationships between claims and evidence
- Epistemic Status: Computed assessment of claim standing
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClaimStatus(str, Enum):
    """Status categories for claims."""

    PROPOSED = "proposed"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    REFUTED = "refuted"
    DEPRECATED = "deprecated"


class EvidenceType(str, Enum):
    """Types of evidence."""

    EXPERIMENT = "experiment"
    OBSERVATION = "observation"
    DATASET = "dataset"
    SIMULATION = "simulation"
    THEOREM = "theorem"
    META_ANALYSIS = "meta_analysis"


class RelationType(str, Enum):
    """Relationship types between claims and evidence."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    WEAKLY_SUPPORTS = "weakly_supports"
    REFINES = "refines"
    GENERALIZES = "generalizes"
    DEPENDS_ON = "depends_on"
    CONFLICTS_WITH = "conflicts_with"


class ClaimBase(BaseModel):
    """Base model for claims."""

    canonical_text: str = Field(..., description="Human-readable claim text")
    semantic_representation: Optional[Dict[str, Any]] = Field(
        None, description="Machine-readable semantic structure"
    )
    domains: List[str] = Field(default_factory=list, description="Domain tags")


class ClaimCreate(ClaimBase):
    """Model for creating a new claim."""

    created_by: str = Field(..., description="BitRep identity of creator")


class ClaimUpdate(BaseModel):
    """Model for updating a claim."""

    canonical_text: Optional[str] = None
    semantic_representation: Optional[Dict[str, Any]] = None
    domains: Optional[List[str]] = None
    status: Optional[ClaimStatus] = None


class Claim(ClaimBase):
    """Complete claim model with metadata."""

    id: str = Field(..., description="Unique claim identifier")
    status: ClaimStatus = Field(
        default=ClaimStatus.PROPOSED, description="Current epistemic status"
    )
    created_by: str = Field(..., description="BitRep identity of creator")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "claim_001",
                "canonical_text": "Quantum entanglement persists over macroscopic distances",
                "semantic_representation": {
                    "subject": "quantum_entanglement",
                    "predicate": "persists",
                },
                "domains": ["quantum_physics", "experimental_physics"],
                "status": "proposed",
                "created_by": "bitrep_id_123",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        }
    )


class EvidenceMetadata(BaseModel):
    """Metadata for evidence."""

    methodology: Optional[str] = None
    sample_size: Optional[int] = None
    uncertainty: Optional[float] = None
    instrumentation: Optional[str] = None
    replication_history: Optional[List[str]] = None


class EvidenceBase(BaseModel):
    """Base model for evidence."""

    type: EvidenceType = Field(..., description="Type of evidence")
    source_identifier: str = Field(..., description="External identifier (DOI, arXiv ID, etc.)")
    metadata: EvidenceMetadata = Field(default_factory=EvidenceMetadata)


class EvidenceCreate(EvidenceBase):
    """Model for submitting new evidence."""

    submitted_by: str = Field(..., description="BitRep identity of submitter")


class Evidence(EvidenceBase):
    """Complete evidence model with metadata."""

    id: str = Field(..., description="Unique evidence identifier")
    submitted_by: str = Field(..., description="BitRep identity of submitter")
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Computed quality score")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "evidence_001",
                "type": "experiment",
                "source_identifier": "doi:10.1234/example",
                "metadata": {"methodology": "double-blind RCT", "sample_size": 1000},
                "submitted_by": "bitrep_id_456",
                "quality_score": 0.85,
                "created_at": "2024-01-01T00:00:00Z",
            }
        }
    )


class LinkBase(BaseModel):
    """Base model for links between claims and evidence."""

    claim_id: str = Field(..., description="ID of the claim")
    evidence_id: Optional[str] = Field(None, description="ID of the evidence")
    claim_id_2: Optional[str] = Field(
        None, description="ID of second claim (for claim-claim links)"
    )
    relation_type: RelationType = Field(..., description="Type of relationship")
    strength: float = Field(default=1.0, ge=0.0, le=1.0, description="Strength of the relationship")

    @model_validator(mode="after")
    def validate_link_targets(self) -> "LinkBase":
        """Ensure either evidence_id or claim_id_2 is provided, but not both."""
        if self.evidence_id is None and self.claim_id_2 is None:
            raise ValueError("Either evidence_id or claim_id_2 must be provided")
        if self.evidence_id is not None and self.claim_id_2 is not None:
            raise ValueError("Only one of evidence_id or claim_id_2 can be provided")
        return self


class LinkCreate(LinkBase):
    """Model for creating a new link."""

    attested_by: str = Field(
        ..., description="BitRep issuer of the attestation; must equal attestation.statement.issuer"
    )
    attestation: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "BitRep v1 attestation envelope {statement, signature} binding this link "
            "(profile: docs/BITREP_LINK_ATTESTATION.md). Required by POST /evidence/links."
        ),
    )


class Link(LinkBase):
    """Complete link model with metadata."""

    id: str = Field(..., description="Unique link identifier")
    attested_by: str = Field(..., description="Verified BitRep issuer that attested the link")
    attestation_id: Optional[str] = Field(None, description="Issuer-scoped attestation id")
    attestation_statement_digest: Optional[str] = Field(
        None, description="sha256 commitment to the verified signed statement"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "link_001",
                "claim_id": "claim_001",
                "evidence_id": "evidence_001",
                "relation_type": "supports",
                "strength": 0.9,
                "attested_by": "bitrep_id_789",
                "timestamp": "2024-01-01T00:00:00Z",
            }
        }
    )


class EpistemicStatus(BaseModel):
    """Computed epistemic status for a claim."""

    claim_id: str = Field(..., description="ID of the claim")
    status: ClaimStatus = Field(..., description="Computed status category")
    supporting_weight: float = Field(default=0.0, description="Total weighted support")
    contradicting_weight: float = Field(default=0.0, description="Total weighted contradiction")
    independence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Diversity of evidence sources"
    )
    robustness_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Replication and methodological quality"
    )
    last_computed_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "claim_id": "claim_001",
                "status": "supported",
                "supporting_weight": 8.5,
                "contradicting_weight": 1.2,
                "independence_score": 0.75,
                "robustness_score": 0.82,
                "last_computed_at": "2024-01-01T00:00:00Z",
            }
        }
    )
