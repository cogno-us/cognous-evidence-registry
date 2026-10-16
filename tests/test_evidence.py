"""
Unit tests for the Evidence service.
"""

from app.core.models import ClaimStatus, EvidenceCreate, LinkCreate, RelationType


def test_submit_evidence(evidence_service, sample_evidence_data):
    """Test submitting new evidence."""
    evidence_data = EvidenceCreate(**sample_evidence_data)
    evidence = evidence_service.submit_evidence(evidence_data)

    assert evidence.id.startswith("evidence_")
    assert evidence.type == sample_evidence_data["type"]
    assert evidence.source_identifier == sample_evidence_data["source_identifier"]
    assert evidence.submitted_by == sample_evidence_data["submitted_by"]
    assert 0.0 <= evidence.quality_score <= 1.0


def test_get_evidence(evidence_service, sample_evidence_data):
    """Test retrieving evidence by ID."""
    evidence_data = EvidenceCreate(**sample_evidence_data)
    created_evidence = evidence_service.submit_evidence(evidence_data)

    retrieved_evidence = evidence_service.get_evidence(created_evidence.id)
    assert retrieved_evidence is not None
    assert retrieved_evidence.id == created_evidence.id


def test_get_nonexistent_evidence(evidence_service):
    """Test retrieving evidence that doesn't exist."""
    evidence = evidence_service.get_evidence("nonexistent_id")
    assert evidence is None


def test_list_evidence(evidence_service, sample_evidence_data):
    """Test listing evidence."""
    # Create multiple evidence items
    for i in range(3):
        data = sample_evidence_data.copy()
        data["source_identifier"] = f"doi:10.1234/test_{i}"
        evidence_data = EvidenceCreate(**data)
        evidence_service.submit_evidence(evidence_data)

    evidence_list = evidence_service.list_evidence()
    assert len(evidence_list) == 3


def test_create_link_to_evidence(evidence_service, sample_evidence_data):
    """Test creating a link between claim and evidence."""
    # Submit evidence
    evidence_data = EvidenceCreate(**sample_evidence_data)
    evidence = evidence_service.submit_evidence(evidence_data)

    # Create link
    link_data = LinkCreate(
        claim_id="test_claim_123",
        evidence_id=evidence.id,
        relation_type=RelationType.SUPPORTS,
        strength=0.9,
        attested_by="test_user_789",
    )
    link = evidence_service.create_link(link_data)

    assert link.id.startswith("link_")
    assert link.claim_id == "test_claim_123"
    assert link.evidence_id == evidence.id
    assert link.relation_type == RelationType.SUPPORTS
    assert link.strength == 0.9


def test_create_link_between_claims(evidence_service):
    """Test creating a link between two claims."""
    link_data = LinkCreate(
        claim_id="claim_1",
        claim_id_2="claim_2",
        relation_type=RelationType.REFINES,
        strength=0.8,
        attested_by="test_user_789",
    )
    link = evidence_service.create_link(link_data)

    assert link.id.startswith("link_")
    assert link.claim_id == "claim_1"
    assert link.claim_id_2 == "claim_2"
    assert link.relation_type == RelationType.REFINES


def test_get_links_for_claim(evidence_service, sample_evidence_data):
    """Test retrieving all links for a claim."""
    # Create evidence and links
    evidence_data = EvidenceCreate(**sample_evidence_data)
    evidence = evidence_service.submit_evidence(evidence_data)

    claim_id = "test_claim_123"
    link_data = LinkCreate(
        claim_id=claim_id,
        evidence_id=evidence.id,
        relation_type=RelationType.SUPPORTS,
        strength=0.9,
        attested_by="test_user_789",
    )
    evidence_service.create_link(link_data)

    links = evidence_service.get_links_for_claim(claim_id)
    assert len(links) == 1
    assert links[0].claim_id == claim_id


def test_get_links_for_evidence(evidence_service, sample_evidence_data):
    """Test retrieving all links for evidence."""
    # Create evidence and links
    evidence_data = EvidenceCreate(**sample_evidence_data)
    evidence = evidence_service.submit_evidence(evidence_data)

    link_data = LinkCreate(
        claim_id="test_claim_123",
        evidence_id=evidence.id,
        relation_type=RelationType.SUPPORTS,
        strength=0.9,
        attested_by="test_user_789",
    )
    evidence_service.create_link(link_data)

    links = evidence_service.get_links_for_evidence(evidence.id)
    assert len(links) == 1
    assert links[0].evidence_id == evidence.id


def test_compute_epistemic_status_supported(evidence_service, sample_evidence_data):
    """Test computing epistemic status for a supported claim."""
    claim_id = "test_claim_123"

    # Create multiple supporting evidence
    for i in range(4):
        data = sample_evidence_data.copy()
        data["source_identifier"] = f"doi:10.1234/test_{i}"
        evidence_data = EvidenceCreate(**data)
        evidence = evidence_service.submit_evidence(evidence_data)

        link_data = LinkCreate(
            claim_id=claim_id,
            evidence_id=evidence.id,
            relation_type=RelationType.SUPPORTS,
            strength=0.9,
            attested_by=f"test_user_{i}",
        )
        evidence_service.create_link(link_data)

    status = evidence_service.compute_epistemic_status(claim_id)
    assert status.claim_id == claim_id
    assert status.status == ClaimStatus.SUPPORTED
    assert status.supporting_weight > 2.0
    assert status.contradicting_weight == 0.0


def test_compute_epistemic_status_contested(evidence_service, sample_evidence_data):
    """Test computing epistemic status for a contested claim."""
    claim_id = "test_claim_123"

    # Create supporting evidence
    data1 = sample_evidence_data.copy()
    evidence1 = evidence_service.submit_evidence(EvidenceCreate(**data1))
    link1 = LinkCreate(
        claim_id=claim_id,
        evidence_id=evidence1.id,
        relation_type=RelationType.SUPPORTS,
        strength=0.8,
        attested_by="test_user_1",
    )
    evidence_service.create_link(link1)

    # Create contradicting evidence with higher weight
    data2 = sample_evidence_data.copy()
    data2["source_identifier"] = "doi:10.1234/test_2"
    evidence2 = evidence_service.submit_evidence(EvidenceCreate(**data2))
    link2 = LinkCreate(
        claim_id=claim_id,
        evidence_id=evidence2.id,
        relation_type=RelationType.CONTRADICTS,
        strength=0.9,
        attested_by="test_user_2",
    )
    evidence_service.create_link(link2)

    status = evidence_service.compute_epistemic_status(claim_id)
    assert status.claim_id == claim_id
    assert status.contradicting_weight > 0.0


def test_quality_score_calculation(evidence_service):
    """Test that quality score is calculated based on metadata."""
    # Evidence with minimal metadata
    data1 = {
        "type": "experiment",
        "source_identifier": "doi:10.1234/test_1",
        "metadata": {},
        "submitted_by": "test_user",
    }
    evidence1 = evidence_service.submit_evidence(EvidenceCreate(**data1))

    # Evidence with rich metadata
    data2 = {
        "type": "experiment",
        "source_identifier": "doi:10.1234/test_2",
        "metadata": {
            "methodology": "RCT",
            "sample_size": 1000,
            "uncertainty": 0.05,
            "replication_history": ["study_1", "study_2"],
        },
        "submitted_by": "test_user",
    }
    evidence2 = evidence_service.submit_evidence(EvidenceCreate(**data2))

    # Evidence with rich metadata should have higher quality score
    assert evidence2.quality_score > evidence1.quality_score


def test_no_mutable_evidence_or_link_aliases(evidence_service, sample_evidence_data):
    """EvidenceService copies records in and out, mirroring ClaimsService."""
    original = evidence_service.submit_evidence(EvidenceCreate(**sample_evidence_data))
    expected = original.model_copy(deep=True)
    for evidence in [
        original,
        evidence_service.get_evidence(original.id),
        evidence_service.list_evidence()[0],
    ]:
        evidence.quality_score = 0.0
        evidence.metadata.methodology = "tampered"
    assert evidence_service.get_evidence(original.id) == expected

    link = evidence_service.create_link(
        LinkCreate(
            claim_id="claim_x",
            evidence_id=original.id,
            relation_type=RelationType.SUPPORTS,
            strength=0.9,
            attested_by="test_user",
        )
    )
    expected_link = link.model_copy(deep=True)
    for returned in [
        link,
        evidence_service.get_links_for_claim("claim_x")[0],
        evidence_service.get_links_for_evidence(original.id)[0],
    ]:
        returned.strength = 0.0
    assert evidence_service.get_links_for_claim("claim_x")[0] == expected_link
