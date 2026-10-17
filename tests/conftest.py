"""
Test configuration and fixtures.
"""

import pytest
from fastapi.testclient import TestClient

from app.claims.service import ClaimsService
from app.evidence.service import EvidenceService
from app.governance.service import GovernanceService
from app.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI application."""
    # Reset service instances between tests
    from app.claims import service as claims_svc
    from app.evidence import service as evidence_svc
    from app.governance import service as governance_svc

    claims_svc.claims_service = ClaimsService()
    evidence_svc.evidence_service = EvidenceService()
    governance_svc.governance_service = GovernanceService()

    # Update the imported services in the API modules
    from app.api import claims, evidence, governance

    claims.claims_service = claims_svc.claims_service
    evidence.evidence_service = evidence_svc.evidence_service
    governance.governance_service = governance_svc.governance_service

    return TestClient(app)


@pytest.fixture
def claims_service():
    """Create a fresh claims service instance for testing."""
    return ClaimsService()


@pytest.fixture
def evidence_service():
    """Create a fresh evidence service instance for testing."""
    return EvidenceService()


@pytest.fixture
def governance_service():
    """Create a fresh governance service instance for testing."""
    return GovernanceService()


@pytest.fixture
def sample_claim_data():
    """Sample claim data for testing."""
    return {
        "canonical_text": "Quantum entanglement persists over macroscopic distances",
        "semantic_representation": {"subject": "quantum_entanglement", "predicate": "persists"},
        "domains": ["quantum_physics", "experimental_physics"],
        "created_by": "test_user_123",
    }


@pytest.fixture
def sample_evidence_data():
    """Sample evidence data for testing."""
    return {
        "type": "experiment",
        "source_identifier": "doi:10.1234/test",
        "metadata": {"methodology": "double-blind RCT", "sample_size": 1000, "uncertainty": 0.05},
        "submitted_by": "test_user_456",
    }


@pytest.fixture
def sample_proposal_data():
    """Sample governance proposal data for testing."""
    return {
        "title": "Add new relation type: partially_supports",
        "description": "Propose adding a new relation type for partial support",
        "proposal_type": "relation_type",
        "proposed_changes": {"new_relation": "partially_supports"},
        "proposer": "test_user_789",
    }


@pytest.fixture
def signer(tmp_path, monkeypatch):
    """Throwaway issuer key + operator trust snapshot (BITREP_TRUST_REGISTRY) for link tests."""
    from tests.attest_helpers import make_registry, new_key, sign_link, write_registry

    priv = new_key()
    path = tmp_path / "trust.json"
    monkeypatch.setenv(
        "BITREP_TRUST_REGISTRY", write_registry(path, make_registry(priv))
    )

    class Signer:
        key = priv
        registry_path = path

        @staticmethod
        def sign(link_fields, **kw):
            return sign_link(priv, link_fields, **kw)

        @staticmethod
        def set_registry(registry):
            write_registry(path, registry)

    return Signer
