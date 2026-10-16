"""
Unit tests for the Governance service.
"""

from datetime import datetime, timedelta

import pytest

from app.governance.models import (
    ProposalCreate,
    ProposalFinalize,
    ProposalStatus,
    VoteChoice,
    VoteCreate,
)


def test_create_proposal(governance_service, sample_proposal_data):
    """Test creating a governance proposal."""
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)

    assert proposal.id.startswith("proposal_")
    assert proposal.title == sample_proposal_data["title"]
    assert proposal.status == ProposalStatus.DRAFT
    assert proposal.proposer == sample_proposal_data["proposer"]
    assert proposal.yes_votes == 0.0
    assert proposal.no_votes == 0.0


def test_activate_proposal(governance_service, sample_proposal_data):
    """Test activating a proposal for voting."""
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)

    activated = governance_service.activate_proposal(proposal.id, voting_duration_days=7)

    assert activated is not None
    assert activated.status == ProposalStatus.ACTIVE
    assert activated.voting_starts_at is not None
    assert activated.voting_ends_at is not None


def test_activate_nonexistent_proposal(governance_service):
    """Test activating a proposal that doesn't exist."""
    result = governance_service.activate_proposal("nonexistent_id")
    assert result is None


def test_get_proposal(governance_service, sample_proposal_data):
    """Test retrieving a proposal by ID."""
    proposal_data = ProposalCreate(**sample_proposal_data)
    created_proposal = governance_service.create_proposal(proposal_data)

    retrieved_proposal = governance_service.get_proposal(created_proposal.id)
    assert retrieved_proposal is not None
    assert retrieved_proposal.id == created_proposal.id


def test_list_proposals(governance_service, sample_proposal_data):
    """Test listing proposals."""
    # Create multiple proposals
    for i in range(3):
        data = sample_proposal_data.copy()
        data["title"] = f"Test proposal {i}"
        proposal_data = ProposalCreate(**data)
        governance_service.create_proposal(proposal_data)

    proposals = governance_service.list_proposals()
    assert len(proposals) == 3


def test_list_proposals_with_status_filter(governance_service, sample_proposal_data):
    """Test listing proposals filtered by status."""
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)
    governance_service.activate_proposal(proposal.id)

    active_proposals = governance_service.list_proposals(status=ProposalStatus.ACTIVE)
    assert len(active_proposals) == 1
    assert active_proposals[0].status == ProposalStatus.ACTIVE


def test_cast_vote_with_quadratic_scaling(governance_service, sample_proposal_data):
    """Test casting a vote with quadratic scaling."""
    # Create and activate proposal
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)
    governance_service.activate_proposal(proposal.id)

    # Cast vote with reputation 100
    vote_data = VoteCreate(
        proposal_id=proposal.id, voter="test_voter_1", choice=VoteChoice.YES, reputation=100.0
    )
    vote = governance_service.cast_vote(vote_data)

    assert vote is not None
    assert vote.id.startswith("vote_")
    assert vote.choice == VoteChoice.YES
    # With quadratic scaling: sqrt(100) = 10
    assert vote.weighted_vote == 10.0


def test_cast_vote_updates_proposal_tallies(governance_service, sample_proposal_data):
    """Test that casting votes updates proposal tallies."""
    # Create and activate proposal
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)
    governance_service.activate_proposal(proposal.id)

    # Cast yes vote
    vote1 = VoteCreate(
        proposal_id=proposal.id, voter="test_voter_1", choice=VoteChoice.YES, reputation=100.0
    )
    governance_service.cast_vote(vote1)

    # Cast no vote
    vote2 = VoteCreate(
        proposal_id=proposal.id, voter="test_voter_2", choice=VoteChoice.NO, reputation=25.0
    )
    governance_service.cast_vote(vote2)

    # Check updated proposal
    updated_proposal = governance_service.get_proposal(proposal.id)
    assert updated_proposal.yes_votes == 10.0  # sqrt(100)
    assert updated_proposal.no_votes == 5.0  # sqrt(25)


def test_cast_vote_prevents_double_voting(governance_service, sample_proposal_data):
    """Test that a voter cannot vote twice on the same proposal."""
    # Create and activate proposal
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)
    governance_service.activate_proposal(proposal.id)

    # Cast first vote
    vote1 = VoteCreate(
        proposal_id=proposal.id, voter="test_voter_1", choice=VoteChoice.YES, reputation=100.0
    )
    result1 = governance_service.cast_vote(vote1)
    assert result1 is not None

    # Try to cast second vote with same voter
    vote2 = VoteCreate(
        proposal_id=proposal.id, voter="test_voter_1", choice=VoteChoice.NO, reputation=100.0
    )
    result2 = governance_service.cast_vote(vote2)
    assert result2 is None  # Should be rejected


def test_cast_vote_on_inactive_proposal(governance_service, sample_proposal_data):
    """Test that voting on inactive proposal is rejected."""
    # Create proposal but don't activate it
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)

    vote_data = VoteCreate(
        proposal_id=proposal.id, voter="test_voter_1", choice=VoteChoice.YES, reputation=100.0
    )
    result = governance_service.cast_vote(vote_data)
    assert result is None


def test_finalize_proposal_passed(governance_service, sample_proposal_data):
    """Test finalizing a proposal that passes."""
    # Create and activate proposal
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)
    activated = governance_service.activate_proposal(proposal.id, voting_duration_days=1)

    # Cast votes in favor
    for i in range(3):
        vote = VoteCreate(
            proposal_id=proposal.id,
            voter=f"test_voter_{i}",
            choice=VoteChoice.YES,
            reputation=100.0,
        )
        governance_service.cast_vote(vote)

    # Manually set voting_ends_at to past
    activated.voting_ends_at = datetime.utcnow() - timedelta(hours=1)

    # Finalize proposal
    finalize_data = ProposalFinalize(proposal_id=proposal.id, finalizer="test_finalizer")
    finalized = governance_service.finalize_proposal(finalize_data)

    assert finalized is not None
    assert finalized.status == ProposalStatus.PASSED


def test_finalize_proposal_rejected(governance_service, sample_proposal_data):
    """Test finalizing a proposal that is rejected."""
    # Create and activate proposal
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)
    activated = governance_service.activate_proposal(proposal.id, voting_duration_days=1)

    # Cast votes against
    for i in range(3):
        vote = VoteCreate(
            proposal_id=proposal.id, voter=f"test_voter_{i}", choice=VoteChoice.NO, reputation=100.0
        )
        governance_service.cast_vote(vote)

    # Manually set voting_ends_at to past
    activated.voting_ends_at = datetime.utcnow() - timedelta(hours=1)

    # Finalize proposal
    finalize_data = ProposalFinalize(proposal_id=proposal.id, finalizer="test_finalizer")
    finalized = governance_service.finalize_proposal(finalize_data)

    assert finalized is not None
    assert finalized.status == ProposalStatus.REJECTED


def test_finalize_proposal_before_voting_ends(governance_service, sample_proposal_data):
    """Test that finalization is rejected if voting hasn't ended."""
    # Create and activate proposal
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)
    governance_service.activate_proposal(proposal.id, voting_duration_days=7)

    # Try to finalize immediately
    finalize_data = ProposalFinalize(proposal_id=proposal.id, finalizer="test_finalizer")
    result = governance_service.finalize_proposal(finalize_data)
    assert result is None


def test_get_votes_for_proposal(governance_service, sample_proposal_data):
    """Test retrieving all votes for a proposal."""
    # Create and activate proposal
    proposal_data = ProposalCreate(**sample_proposal_data)
    proposal = governance_service.create_proposal(proposal_data)
    governance_service.activate_proposal(proposal.id)

    # Cast multiple votes
    for i in range(3):
        vote = VoteCreate(
            proposal_id=proposal.id,
            voter=f"test_voter_{i}",
            choice=VoteChoice.YES,
            reputation=100.0,
        )
        governance_service.cast_vote(vote)

    votes = governance_service.get_votes_for_proposal(proposal.id)
    assert len(votes) == 3


@pytest.mark.parametrize("bad", [float("inf"), float("nan")])
def test_vote_rejects_non_finite_reputation(bad):
    """Infinite or NaN reputation must not be accepted for a vote."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        VoteCreate(proposal_id="p", voter="v", choice=VoteChoice.YES, reputation=bad)
