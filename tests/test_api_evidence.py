"""
Integration tests for the Evidence API.
"""


def test_submit_evidence_endpoint(client, sample_evidence_data):
    """Test POST /api/v1/evidence/ endpoint."""
    response = client.post("/api/v1/evidence/", json=sample_evidence_data)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["type"] == sample_evidence_data["type"]
    assert "quality_score" in data


def test_get_evidence_endpoint(client, sample_evidence_data):
    """Test GET /api/v1/evidence/{evidence_id} endpoint."""
    # Submit evidence first
    create_response = client.post("/api/v1/evidence/", json=sample_evidence_data)
    evidence_id = create_response.json()["id"]

    # Retrieve the evidence
    response = client.get(f"/api/v1/evidence/{evidence_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == evidence_id


def test_list_evidence_endpoint(client, sample_evidence_data):
    """Test GET /api/v1/evidence/ endpoint."""
    # Submit multiple evidence items
    for i in range(3):
        data = sample_evidence_data.copy()
        data["source_identifier"] = f"doi:10.1234/test_{i}"
        client.post("/api/v1/evidence/", json=data)

    response = client.get("/api/v1/evidence/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_create_link_endpoint(client, signer, sample_claim_data, sample_evidence_data):
    """Test POST /api/v1/evidence/links endpoint."""
    # Create a claim
    claim_response = client.post("/api/v1/claims/", json=sample_claim_data)
    claim_id = claim_response.json()["id"]

    # Submit evidence
    evidence_response = client.post("/api/v1/evidence/", json=sample_evidence_data)
    evidence_id = evidence_response.json()["id"]

    # Create link
    link_data = {
        "claim_id": claim_id,
        "evidence_id": evidence_id,
        "relation_type": "supports",
        "strength": 0.9,
    }
    response = client.post("/api/v1/evidence/links", json=signer.sign(link_data))

    assert response.status_code == 201
    data = response.json()
    assert data["claim_id"] == claim_id
    assert data["evidence_id"] == evidence_id
    assert data["relation_type"] == "supports"


def test_get_links_for_claim_endpoint(client, signer, sample_claim_data, sample_evidence_data):
    """Test GET /api/v1/evidence/links/claim/{claim_id} endpoint."""
    # Create a claim
    claim_response = client.post("/api/v1/claims/", json=sample_claim_data)
    claim_id = claim_response.json()["id"]

    # Submit evidence and create link
    evidence_response = client.post("/api/v1/evidence/", json=sample_evidence_data)
    evidence_id = evidence_response.json()["id"]

    link_data = {
        "claim_id": claim_id,
        "evidence_id": evidence_id,
        "relation_type": "supports",
        "strength": 0.9,
    }
    client.post("/api/v1/evidence/links", json=signer.sign(link_data))

    # Get links for claim
    response = client.get(f"/api/v1/evidence/links/claim/{claim_id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["claim_id"] == claim_id


def test_get_epistemic_status_endpoint(client, signer, sample_claim_data, sample_evidence_data):
    """Test GET /api/v1/evidence/epistemic-status/{claim_id} endpoint."""
    # Create a claim
    claim_response = client.post("/api/v1/claims/", json=sample_claim_data)
    claim_id = claim_response.json()["id"]

    # Submit multiple supporting evidence
    for i in range(4):
        data = sample_evidence_data.copy()
        data["source_identifier"] = f"doi:10.1234/test_{i}"
        evidence_response = client.post("/api/v1/evidence/", json=data)
        evidence_id = evidence_response.json()["id"]

        link_data = {
            "claim_id": claim_id,
            "evidence_id": evidence_id,
            "relation_type": "supports",
            "strength": 0.9,
        }
        client.post(
            "/api/v1/evidence/links", json=signer.sign(link_data, attestation_id=f"att-{i}")
        )

    # Get epistemic status
    response = client.get(f"/api/v1/evidence/epistemic-status/{claim_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == claim_id
    assert data["status"] == "supported"
    assert data["supporting_weight"] > 0
    assert "independence_score" in data
    assert "robustness_score" in data
