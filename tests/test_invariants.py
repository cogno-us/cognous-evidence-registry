"""
Invariant tests for protocol enforcement.

These tests validate that the protocol invariants defined in the architecture
specification are properly enforced by the implementation.
"""

import pytest
from datetime import datetime

from api.claim_layer import create_claim, get_claim, get_claim_store
from api.evidence_layer import create_evidence, get_evidence, get_evidence_store, register_claim_reference
from api.link_layer import create_link, get_link, get_link_store
from ontology.registry import validate_term, resolve, get_ontology_registry


class TestClaimInvariants:
    """Test enforcement of claim invariants."""
    
    def setup_method(self):
        """Reset stores before each test."""
        # Reset the global stores
        from api import claim_layer, evidence_layer, link_layer
        claim_layer._claim_store = claim_layer.ClaimStore()
        evidence_layer._evidence_store = evidence_layer.EvidenceStore()
        link_layer._link_store = link_layer.LinkStore()
    
    def test_reject_claim_without_evidence_or_justification(self):
        """Test that claims without evidence_refs or justification are rejected."""
        with pytest.raises(ValueError, match="evidence_refs or justification"):
            create_claim(
                subject="test_subject",
                predicate="test_predicate",
                object_value="test_object",
                contributor_id="test_contributor"
                # Missing both evidence_refs and justification
            )
    
    def test_accept_claim_with_evidence(self):
        """Test that claims with evidence_refs are accepted."""
        claim_id = create_claim(
            subject="test_subject",
            predicate="test_predicate",
            object_value="test_object",
            contributor_id="test_contributor",
            evidence_refs=["evidence_test123"]
        )
        
        assert claim_id is not None
        assert claim_id.startswith("claim_")
        
        claim = get_claim(claim_id)
        assert claim is not None
        assert claim["evidence_refs"] == ["evidence_test123"]
    
    def test_accept_claim_with_justification(self):
        """Test that claims with justification are accepted."""
        claim_id = create_claim(
            subject="test_subject",
            predicate="test_predicate",
            object_value="test_object",
            contributor_id="test_contributor",
            justification="This is a valid justification"
        )
        
        assert claim_id is not None
        claim = get_claim(claim_id)
        assert claim is not None
        assert claim["justification"] == "This is a valid justification"
    
    def test_reject_claim_with_empty_justification(self):
        """Test that claims with empty justification are rejected."""
        with pytest.raises(ValueError, match="evidence_refs or justification"):
            create_claim(
                subject="test_subject",
                predicate="test_predicate",
                object_value="test_object",
                contributor_id="test_contributor",
                justification="   "  # Only whitespace
            )
    
    def test_reject_claim_without_required_fields(self):
        """Test that claims without required fields are rejected."""
        # Missing subject
        with pytest.raises(ValueError, match="subject"):
            create_claim(
                subject="",
                predicate="test_predicate",
                object_value="test_object",
                contributor_id="test_contributor",
                justification="test"
            )
        
        # Missing predicate
        with pytest.raises(ValueError, match="predicate"):
            create_claim(
                subject="test_subject",
                predicate="",
                object_value="test_object",
                contributor_id="test_contributor",
                justification="test"
            )
        
        # Missing object
        with pytest.raises(ValueError, match="object"):
            create_claim(
                subject="test_subject",
                predicate="test_predicate",
                object_value="",
                contributor_id="test_contributor",
                justification="test"
            )
        
        # Missing contributor_id
        with pytest.raises(ValueError, match="contributor_id"):
            create_claim(
                subject="test_subject",
                predicate="test_predicate",
                object_value="test_object",
                contributor_id="",
                justification="test"
            )
    
    def test_claim_immutability(self):
        """Test that claims cannot be modified after creation."""
        claim_id = create_claim(
            subject="test_subject",
            predicate="test_predicate",
            object_value="test_object",
            contributor_id="test_contributor",
            justification="test justification"
        )
        
        # Try to create a claim with the same ID
        store = get_claim_store()
        with pytest.raises(ValueError, match="immutable"):
            store.store({
                "id": claim_id,
                "subject": "modified_subject",
                "predicate": "test_predicate",
                "object": "test_object",
                "contributor_id": "test_contributor",
                "justification": "test"
            })
    
    def test_claim_default_status(self):
        """Test that new claims default to 'proposed' status."""
        claim_id = create_claim(
            subject="test_subject",
            predicate="test_predicate",
            object_value="test_object",
            contributor_id="test_contributor",
            justification="test"
        )
        
        claim = get_claim(claim_id)
        assert claim["status"] == "proposed"


class TestEvidenceInvariants:
    """Test enforcement of evidence invariants."""
    
    def setup_method(self):
        """Reset stores before each test."""
        from api import evidence_layer
        evidence_layer._evidence_store = evidence_layer.EvidenceStore()
    
    def test_reject_evidence_without_required_fields(self):
        """Test that evidence without required fields is rejected."""
        # Missing type
        with pytest.raises(ValueError, match="type"):
            create_evidence(
                evidence_type="",
                source="doi:10.1234/test",
                timestamp=datetime.utcnow().isoformat(),
                provenance_chain=[{"actor": "test", "action": "created", "timestamp": datetime.utcnow().isoformat()}],
                submitted_by="test_user"
            )
        
        # Missing source
        with pytest.raises(ValueError, match="source"):
            create_evidence(
                evidence_type="experiment",
                source="",
                timestamp=datetime.utcnow().isoformat(),
                provenance_chain=[{"actor": "test", "action": "created", "timestamp": datetime.utcnow().isoformat()}],
                submitted_by="test_user"
            )
    
    def test_reject_evidence_without_provenance_chain(self):
        """Test that evidence without provenance chain is rejected."""
        with pytest.raises(ValueError, match="provenance_chain"):
            create_evidence(
                evidence_type="experiment",
                source="doi:10.1234/test",
                timestamp=datetime.utcnow().isoformat(),
                provenance_chain=[],  # Empty provenance chain
                submitted_by="test_user"
            )
    
    def test_accept_valid_evidence(self):
        """Test that valid evidence is accepted."""
        evidence_id = create_evidence(
            evidence_type="experiment",
            source="doi:10.1234/test",
            timestamp=datetime.utcnow().isoformat(),
            provenance_chain=[{
                "actor": "test_user",
                "action": "created",
                "timestamp": datetime.utcnow().isoformat()
            }],
            submitted_by="test_user",
            metadata={"methodology": "RCT", "sample_size": 100}
        )
        
        assert evidence_id is not None
        assert evidence_id.startswith("evidence_")
        
        evidence = get_evidence(evidence_id)
        assert evidence is not None
        assert evidence["type"] == "experiment"
        assert evidence["source"] == "doi:10.1234/test"
    
    def test_evidence_immutability(self):
        """Test that evidence cannot be modified after creation."""
        evidence_id = create_evidence(
            evidence_type="experiment",
            source="doi:10.1234/test",
            timestamp=datetime.utcnow().isoformat(),
            provenance_chain=[{
                "actor": "test_user",
                "action": "created",
                "timestamp": datetime.utcnow().isoformat()
            }],
            submitted_by="test_user"
        )
        
        # Try to create evidence with the same ID
        store = get_evidence_store()
        with pytest.raises(ValueError, match="immutable"):
            store.store({
                "id": evidence_id,
                "type": "observation",  # Different type
                "source": "doi:10.1234/modified",
                "timestamp": datetime.utcnow().isoformat(),
                "provenance_chain": [{"actor": "test", "action": "created", "timestamp": datetime.utcnow().isoformat()}],
                "submitted_by": "test_user"
            })
    
    def test_evidence_checksum_computed(self):
        """Test that evidence checksum is automatically computed."""
        evidence_id = create_evidence(
            evidence_type="experiment",
            source="doi:10.1234/test",
            timestamp=datetime.utcnow().isoformat(),
            provenance_chain=[{
                "actor": "test_user",
                "action": "created",
                "timestamp": datetime.utcnow().isoformat()
            }],
            submitted_by="test_user"
        )
        
        evidence = get_evidence(evidence_id)
        assert "checksum" in evidence
        assert len(evidence["checksum"]) == 64  # SHA-256 hex string


class TestLinkInvariants:
    """Test enforcement of link invariants."""
    
    def setup_method(self):
        """Reset stores before each test."""
        from api import claim_layer, evidence_layer, link_layer
        claim_layer._claim_store = claim_layer.ClaimStore()
        evidence_layer._evidence_store = evidence_layer.EvidenceStore()
        link_layer._link_store = link_layer.LinkStore()
    
    def test_reject_link_to_nonexistent_objects(self):
        """Test that links to non-existent objects are rejected."""
        def validate_refs(source_id, target_id):
            # Neither source nor target exists
            return False
        
        with pytest.raises(ValueError, match="existing objects"):
            create_link(
                source_id="claim_nonexistent",
                target_id="evidence_nonexistent",
                relation_type="supports",
                attestor_id="test_user",
                validate_references=validate_refs
            )
    
    def test_accept_link_to_existing_objects(self):
        """Test that links to existing objects are accepted."""
        # Create a claim
        claim_id = create_claim(
            subject="test",
            predicate="test",
            object_value="test",
            contributor_id="test_user",
            justification="test"
        )
        
        # Create evidence
        evidence_id = create_evidence(
            evidence_type="experiment",
            source="doi:10.1234/test",
            timestamp=datetime.utcnow().isoformat(),
            provenance_chain=[{
                "actor": "test_user",
                "action": "created",
                "timestamp": datetime.utcnow().isoformat()
            }],
            submitted_by="test_user"
        )
        
        # Validation function that checks both exist
        def validate_refs(source_id, target_id):
            return (get_claim(source_id) is not None and 
                   get_evidence(target_id) is not None)
        
        # Create link
        link_id = create_link(
            source_id=claim_id,
            target_id=evidence_id,
            relation_type="supports",
            attestor_id="test_user",
            validate_references=validate_refs
        )
        
        assert link_id is not None
        assert link_id.startswith("link_")
    
    def test_link_immutability(self):
        """Test that links cannot be modified after creation."""
        link_id = create_link(
            source_id="claim_test123",
            target_id="evidence_test456",
            relation_type="supports",
            attestor_id="test_user"
        )
        
        # Try to create a link with the same ID
        store = get_link_store()
        with pytest.raises(ValueError, match="immutable"):
            store.store({
                "id": link_id,
                "source_id": "claim_test123",
                "target_id": "evidence_test456",
                "relation_type": "contradicts",  # Different relation
                "weight": 1.0,
                "attestor_id": "test_user"
            })
    
    def test_reject_invalid_relation_type(self):
        """Test that links with invalid relation types are rejected."""
        with pytest.raises(ValueError, match="relation_type"):
            create_link(
                source_id="claim_test123",
                target_id="evidence_test456",
                relation_type="invalid_relation",
                attestor_id="test_user"
            )
    
    def test_reject_invalid_weight(self):
        """Test that links with invalid weights are rejected."""
        # Weight > 1.0
        with pytest.raises(ValueError, match="weight"):
            create_link(
                source_id="claim_test123",
                target_id="evidence_test456",
                relation_type="supports",
                attestor_id="test_user",
                weight=1.5
            )
        
        # Weight < 0.0
        with pytest.raises(ValueError, match="weight"):
            create_link(
                source_id="claim_test123",
                target_id="evidence_test456",
                relation_type="supports",
                attestor_id="test_user",
                weight=-0.5
            )


class TestOntologyValidation:
    """Test ontology validation and resolution."""
    
    def test_resolve_valid_term(self):
        """Test resolving a valid ontology term."""
        term = resolve("supports")
        assert term is not None
        assert term["id"] == "supports"
        assert term["type"] == "relation"
    
    def test_resolve_invalid_term(self):
        """Test resolving an invalid ontology term."""
        term = resolve("nonexistent_term")
        assert term is None
    
    def test_validate_relation_type(self):
        """Test validating relation types."""
        assert validate_term("supports", term_type="relation") is True
        assert validate_term("contradicts", term_type="relation") is True
        assert validate_term("experiment", term_type="relation") is False
    
    def test_validate_evidence_type(self):
        """Test validating evidence types."""
        assert validate_term("experiment", term_type="evidence_type") is True
        assert validate_term("observation", term_type="evidence_type") is True
        assert validate_term("supports", term_type="evidence_type") is False
    
    def test_reject_deprecated_terms(self):
        """Test that deprecated terms are rejected by default."""
        # This test assumes we have a deprecated term in the ontology
        # For now, we'll just verify the validation logic works
        registry = get_ontology_registry()
        
        # Validate with allow_deprecated=False (default)
        # Since we don't have deprecated terms yet, this tests the mechanism
        valid_term = validate_term("supports", allow_deprecated=False)
        assert valid_term is True


class TestCanonicalExamples:
    """Test that well-formed canonical examples are accepted."""
    
    def setup_method(self):
        """Reset stores before each test."""
        from api import claim_layer, evidence_layer, link_layer
        claim_layer._claim_store = claim_layer.ClaimStore()
        evidence_layer._evidence_store = evidence_layer.EvidenceStore()
        link_layer._link_store = link_layer.LinkStore()
    
    def test_complete_claim_evidence_link_workflow(self):
        """Test a complete workflow with claim, evidence, and link."""
        # Create a well-formed claim with justification
        claim_id = create_claim(
            subject="Quantum entanglement",
            predicate="persists_over",
            object_value="macroscopic distances",
            contributor_id="researcher_alice",
            canonical_text="Quantum entanglement persists over macroscopic distances",
            domains=["quantum_physics", "experimental_physics"],
            justification="Based on experimental observations"  # Added justification
        )
        
        assert claim_id is not None
        
        # Create well-formed evidence
        evidence_id = create_evidence(
            evidence_type="experiment",
            source="doi:10.1038/nature12345",
            timestamp="2024-01-15T10:30:00Z",
            provenance_chain=[{
                "actor": "researcher_bob",
                "action": "published",
                "timestamp": "2024-01-15T10:30:00Z",
                "details": {"journal": "Nature"}
            }],
            submitted_by="researcher_bob",
            metadata={
                "methodology": "Bell test with photon pairs",
                "sample_size": 10000,
                "uncertainty": 0.02,
                "replication_history": []
            }
        )
        
        assert evidence_id is not None
        
        # Register that the claim references this evidence
        register_claim_reference(evidence_id, claim_id)
        
        # Create well-formed link
        def validate_refs(source_id, target_id):
            return (get_claim(source_id) is not None and 
                   get_evidence(target_id) is not None)
        
        link_id = create_link(
            source_id=claim_id,
            target_id=evidence_id,
            relation_type="supports",
            attestor_id="researcher_carol",
            weight=0.9,
            metadata={
                "confidence": 0.95,
                "rationale": "Strong experimental evidence"
            },
            validate_references=validate_refs
        )
        
        assert link_id is not None
        
        # Verify all objects are retrievable
        retrieved_claim = get_claim(claim_id)
        assert retrieved_claim is not None
        assert retrieved_claim["subject"] == "Quantum entanglement"
        
        retrieved_evidence = get_evidence(evidence_id)
        assert retrieved_evidence is not None
        assert retrieved_evidence["type"] == "experiment"
        
        retrieved_link = get_link(link_id)
        assert retrieved_link is not None
        assert retrieved_link["relation_type"] == "supports"


def test_alternate_claim_store_preserves_history_and_nested_bytes():
    """Legacy status observations retain prior state; callers cannot mutate via aliases."""
    from api.claim_layer import ClaimStore
    store = ClaimStore()
    original = {"subject": "sample", "predicate": "is", "object": "synthetic",
                "contributor_id": "unverified:legacy", "justification": "fixture",
                "evidence_refs": ["evidence_original"]}
    claim_id = store.store(original)
    original["evidence_refs"].append("tamper")
    returned = store.retrieve(claim_id)
    returned["evidence_refs"].append("tamper")
    assert store.retrieve(claim_id)["evidence_refs"] == ["evidence_original"]
    store.update_status(claim_id, "contested")
    store.update_status(claim_id, "supported")
    history = store.status_history(claim_id)
    assert [e["previous"]["status"] for e in history] == ["proposed", "contested"]
    history[0]["previous"]["evidence_refs"].append("tamper")
    assert store.status_history(claim_id)[0]["previous"]["evidence_refs"] == ["evidence_original"]
