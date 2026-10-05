"""
Unit tests for the Claims service.
"""

import pytest

from app.core.models import ClaimCreate, ClaimStatus, ClaimUpdate


def test_create_claim(claims_service, sample_claim_data):
    """Test creating a new claim."""
    claim_data = ClaimCreate(**sample_claim_data)
    claim = claims_service.create_claim(claim_data)

    assert claim.id.startswith("claim_")
    assert claim.canonical_text == sample_claim_data["canonical_text"]
    assert claim.status == ClaimStatus.PROPOSED
    assert claim.created_by == sample_claim_data["created_by"]
    assert claim.domains == sample_claim_data["domains"]


def test_get_claim(claims_service, sample_claim_data):
    """Test retrieving a claim by ID."""
    claim_data = ClaimCreate(**sample_claim_data)
    created_claim = claims_service.create_claim(claim_data)

    retrieved_claim = claims_service.get_claim(created_claim.id)
    assert retrieved_claim is not None
    assert retrieved_claim.id == created_claim.id
    assert retrieved_claim.canonical_text == created_claim.canonical_text


def test_get_nonexistent_claim(claims_service):
    """Test retrieving a claim that doesn't exist."""
    claim = claims_service.get_claim("nonexistent_id")
    assert claim is None


def test_list_claims(claims_service, sample_claim_data):
    """Test listing claims."""
    # Create multiple claims
    for i in range(3):
        data = sample_claim_data.copy()
        data["canonical_text"] = f"Test claim {i}"
        claim_data = ClaimCreate(**data)
        claims_service.create_claim(claim_data)

    claims = claims_service.list_claims()
    assert len(claims) == 3


def test_list_claims_with_status_filter(claims_service, sample_claim_data):
    """Test listing claims filtered by status."""
    claim_data = ClaimCreate(**sample_claim_data)
    claim = claims_service.create_claim(claim_data)

    with pytest.raises(ValueError):
        claims_service.update_claim(claim.id, ClaimUpdate(status=ClaimStatus.SUPPORTED))
    assert claims_service.list_claims(status=ClaimStatus.SUPPORTED) == []
    assert len(claims_service.list_claims(status=ClaimStatus.PROPOSED)) == 1


def test_list_claims_with_domain_filter(claims_service, sample_claim_data):
    """Test listing claims filtered by domain."""
    claim_data = ClaimCreate(**sample_claim_data)
    claims_service.create_claim(claim_data)

    physics_claims = claims_service.list_claims(domain="quantum_physics")
    assert len(physics_claims) == 1
    assert "quantum_physics" in physics_claims[0].domains


def test_update_claim(claims_service, sample_claim_data):
    """Test updating a claim."""
    claim_data = ClaimCreate(**sample_claim_data)
    claim = claims_service.create_claim(claim_data)

    update = ClaimUpdate(canonical_text="Updated claim text", status=ClaimStatus.SUPPORTED)
    with pytest.raises(ValueError):
        claims_service.update_claim(claim.id, update)
    assert claims_service.get_claim(claim.id) == claim


def test_update_nonexistent_claim(claims_service):
    """Test updating a claim that doesn't exist."""
    update = ClaimUpdate(canonical_text="Updated text")
    result = claims_service.update_claim("nonexistent_id", update)
    assert result is None


def test_delete_claim(claims_service, sample_claim_data):
    """Test deleting a claim."""
    claim_data = ClaimCreate(**sample_claim_data)
    claim = claims_service.create_claim(claim_data)

    with pytest.raises(ValueError):
        claims_service.delete_claim(claim.id)
    assert claims_service.get_claim(claim.id) == claim


def test_delete_nonexistent_claim(claims_service):
    """Test deleting a claim that doesn't exist."""
    success = claims_service.delete_claim("nonexistent_id")
    assert success is False


def test_search_claims(claims_service, sample_claim_data):
    """Test searching claims by text."""
    # Create claims with different text
    data1 = sample_claim_data.copy()
    data1["canonical_text"] = "Quantum mechanics is fundamental"
    claims_service.create_claim(ClaimCreate(**data1))

    data2 = sample_claim_data.copy()
    data2["canonical_text"] = "Classical physics explains macroscopic phenomena"
    claims_service.create_claim(ClaimCreate(**data2))

    # Search for "quantum"
    results = claims_service.search_claims("quantum")
    assert len(results) == 1
    assert "quantum" in results[0].canonical_text.lower()


def test_no_mutable_claim_aliases(claims_service, sample_claim_data):
    original = claims_service.create_claim(ClaimCreate(**sample_claim_data))
    expected = original.model_copy(deep=True)
    for claim in [
        original,
        claims_service.get_claim(original.id),
        claims_service.list_claims()[0],
        claims_service.search_claims("Quantum")[0],
    ]:
        claim.canonical_text = "tampered"
        claim.domains.append("tampered")
        claim.semantic_representation["subject"] = "tampered"
    assert claims_service.get_claim(original.id) == expected
