"""
Governance models for proposals and voting.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProposalType(str, Enum):
    """Types of governance proposals."""

    SCHEMA_CHANGE = "schema_change"
    ONTOLOGY_UPDATE = "ontology_update"
    RELATION_TYPE = "relation_type"
    RULE_CHANGE = "rule_change"
    PARAMETER_UPDATE = "parameter_update"


class ProposalStatus(str, Enum):
    """Status of a governance proposal."""

    DRAFT = "draft"
    ACTIVE = "active"
    PASSED = "passed"
    REJECTED = "rejected"
    EXECUTED = "executed"


class VoteChoice(str, Enum):
    """Vote choices."""

    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


class ProposalCreate(BaseModel):
    """Model for creating a governance proposal."""

    title: str = Field(..., description="Proposal title")
    description: str = Field(..., description="Detailed description")
    proposal_type: ProposalType = Field(..., description="Type of proposal")
    proposed_changes: Dict[str, Any] = Field(..., description="Proposed changes as structured data")
    proposer: str = Field(..., description="BitRep identity of proposer")


class Proposal(ProposalCreate):
    """Complete governance proposal model."""

    id: str = Field(..., description="Unique proposal identifier")
    status: ProposalStatus = Field(default=ProposalStatus.DRAFT)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    voting_starts_at: Optional[datetime] = None
    voting_ends_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None

    # Vote tallies
    yes_votes: float = Field(default=0.0, description="Total yes vote weight")
    no_votes: float = Field(default=0.0, description="Total no vote weight")
    abstain_votes: float = Field(default=0.0, description="Total abstain vote weight")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "proposal_001",
                "title": "Add new relation type: 'partially_supports'",
                "description": "Propose adding a new relation type for partial support",
                "proposal_type": "relation_type",
                "proposed_changes": {"new_relation": "partially_supports"},
                "proposer": "bitrep_id_123",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "yes_votes": 15.5,
                "no_votes": 3.2,
            }
        }
    )


class VoteCreate(BaseModel):
    """Model for casting a vote."""

    proposal_id: str = Field(..., description="ID of the proposal")
    voter: str = Field(..., description="BitRep identity of voter")
    choice: VoteChoice = Field(..., description="Vote choice")
    reputation: float = Field(
        ..., ge=0.0, allow_inf_nan=False, description="Voter's reputation score"
    )


class Vote(VoteCreate):
    """Complete vote model."""

    id: str = Field(..., description="Unique vote identifier")
    weighted_vote: float = Field(..., description="Reputation-weighted vote with quadratic scaling")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "vote_001",
                "proposal_id": "proposal_001",
                "voter": "bitrep_id_456",
                "choice": "yes",
                "reputation": 100.0,
                "weighted_vote": 10.0,
                "timestamp": "2024-01-01T00:00:00Z",
            }
        }
    )


class ProposalFinalize(BaseModel):
    """Model for finalizing a proposal."""

    proposal_id: str = Field(..., description="ID of the proposal to finalize")
    finalizer: str = Field(..., description="BitRep identity of finalizer")
