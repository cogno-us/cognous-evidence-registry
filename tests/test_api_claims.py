"""
Integration tests for the Claims API.
"""


def test_create_claim_endpoint(client, sample_claim_data):
    """Test POST /api/v1/claims/ endpoint."""
    response = client.post("/api/v1/claims/", json=sample_claim_data)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["canonical_text"] == sample_claim_data["canonical_text"]
    assert data["status"] == "proposed"


def test_get_claim_endpoint(client, sample_claim_data):
    """Test GET /api/v1/claims/{claim_id} endpoint."""
    # Create a claim first
    create_response = client.post("/api/v1/claims/", json=sample_claim_data)
    claim_id = create_response.json()["id"]

    # Retrieve the claim
    response = client.get(f"/api/v1/claims/{claim_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == claim_id
    assert data["canonical_text"] == sample_claim_data["canonical_text"]


def test_get_nonexistent_claim_endpoint(client):
    """Test GET /api/v1/claims/{claim_id} with nonexistent ID."""
    response = client.get("/api/v1/claims/nonexistent_id")
    assert response.status_code == 404


def test_list_claims_endpoint(client, sample_claim_data):
    """Test GET /api/v1/claims/ endpoint."""
    # Create multiple claims
    for i in range(3):
        data = sample_claim_data.copy()
        data["canonical_text"] = f"Test claim {i}"
        client.post("/api/v1/claims/", json=data)

    response = client.get("/api/v1/claims/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3


def test_list_claims_with_filters(client, sample_claim_data):
    """Test GET /api/v1/claims/ with filters."""
    # Create a claim
    client.post("/api/v1/claims/", json=sample_claim_data)

    # Filter by domain
    response = client.get("/api/v1/claims/?domain=quantum_physics")

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert "quantum_physics" in data[0]["domains"]


def test_update_claim_endpoint(client, sample_claim_data):
    """Test PUT /api/v1/claims/{claim_id} endpoint."""
    # Create a claim
    create_response = client.post("/api/v1/claims/", json=sample_claim_data)
    claim_id = create_response.json()["id"]

    # Update the claim
    update_data = {"canonical_text": "Updated claim text", "status": "supported"}
    response = client.put(f"/api/v1/claims/{claim_id}", json=update_data)

    assert response.status_code == 409
    data = client.get(f"/api/v1/claims/{claim_id}").json()
    assert data["canonical_text"] == sample_claim_data["canonical_text"]
    assert data["status"] == "proposed"


def test_delete_claim_endpoint(client, sample_claim_data):
    """Test DELETE /api/v1/claims/{claim_id} endpoint."""
    # Create a claim
    create_response = client.post("/api/v1/claims/", json=sample_claim_data)
    claim_id = create_response.json()["id"]

    # Delete the claim
    response = client.delete(f"/api/v1/claims/{claim_id}")
    assert response.status_code == 409

    # Verify accepted history is still readable
    get_response = client.get(f"/api/v1/claims/{claim_id}")
    assert get_response.status_code == 200


def test_search_claims_endpoint(client, sample_claim_data):
    """Test GET /api/v1/claims/search/ endpoint."""
    # Create claims with different text
    data1 = sample_claim_data.copy()
    data1["canonical_text"] = "Quantum mechanics is fundamental"
    client.post("/api/v1/claims/", json=data1)

    data2 = sample_claim_data.copy()
    data2["canonical_text"] = "Classical physics explains phenomena"
    client.post("/api/v1/claims/", json=data2)

    # Search for "quantum"
    response = client.get("/api/v1/claims/search/?q=quantum")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert "quantum" in data[0]["canonical_text"].lower()
