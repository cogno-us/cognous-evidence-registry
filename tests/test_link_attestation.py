"""Regression tests for issue #23 (link attestation) and #24 (source independence)."""

import json
import time

import pytest

from app.bitrep_verify.models import AttestationEnvelope
from app.bitrep_verify.trust import TrustRegistry
from app.bitrep_verify.verification import statement_digest, verify_attestation
from tests.attest_helpers import make_registry, new_key

CLAIM = {
    "canonical_text": "Regression claim",
    "semantic_representation": {"subject": "a", "predicate": "b"},
    "domains": ["t"],
    "created_by": "u",
}


def evidence(source="doi:10.1234/same", i=0):
    return {
        "type": "experiment",
        "source_identifier": source,
        "metadata": {"methodology": "double-blind RCT", "sample_size": 1000, "uncertainty": 0.05,
                     "replication_history": [str(i)]},
        "submitted_by": "u",
    }


@pytest.fixture
def ids(client):
    c = client.post("/api/v1/claims/", json=CLAIM).json()["id"]
    e = client.post("/api/v1/evidence/", json=evidence()).json()["id"]
    return c, e


def fields(c, e, **kw):
    f = {"claim_id": c, "evidence_id": e, "relation_type": "supports", "strength": 0.9}
    f.update(kw)
    return f


def post(client, body):
    return client.post("/api/v1/evidence/links", json=body)


def reason(r):
    return r.json()["detail"]["reason"]


# ---- vendored verifier conformance against the BitRep pinned vector ----

def test_vendored_verifier_matches_bitrep_vector():
    vec = json.load(open("tests/fixtures/bitrep-verification-v1.json"))
    att = AttestationEnvelope.model_validate(vec["attestation"])
    reg = TrustRegistry.model_validate(vec["trust"])
    res = verify_attestation(att, reg, vec["evaluated_at"])
    assert res.model_dump() == vec["verification"]
    assert statement_digest(att.statement) == vec["verification"]["statement_digest"]


# ---- #23: accepted ----

def test_valid_attestation_accepted(client, signer, ids):
    r = post(client, signer.sign(fields(*ids)))
    assert r.status_code == 201
    body = r.json()
    assert body["attested_by"] == "issuer:alice"
    assert body["attestation_id"] == "att-1"
    assert body["attestation_statement_digest"].startswith("sha256:")


def test_idempotent_resubmission_returns_same_link(client, signer, ids):
    body = signer.sign(fields(*ids))
    first = post(client, body)
    second = post(client, body)
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"]
    assert len(client.get(f"/api/v1/evidence/links/claim/{ids[0]}").json()) == 1


def test_attestation_id_reuse_for_different_link_conflicts(client, signer, ids):
    assert post(client, signer.sign(fields(*ids))).status_code == 201
    r = post(client, signer.sign(fields(*ids, strength=0.5)))  # same id, different statement
    assert r.status_code == 409 and reason(r) == "attestation_id_conflict"


# ---- #23: rejected ----

def test_unsigned_link_with_arbitrary_attested_by_rejected(client, signer, ids):
    r = post(client, {**fields(*ids), "attested_by": "forged-attestor"})
    assert r.status_code == 401 and reason(r) == "attestation_required"
    assert client.get(f"/api/v1/evidence/links/claim/{ids[0]}").json() == []


def test_no_trust_registry_fails_closed(client, ids, monkeypatch, signer):
    body = signer.sign(fields(*ids))
    monkeypatch.delenv("BITREP_TRUST_REGISTRY")
    r = post(client, body)
    assert r.status_code == 503 and reason(r) == "trust_unavailable"


def test_forged_signature_rejected(client, signer, ids):
    body = signer.sign(fields(*ids))
    sig = body["attestation"]["signature"]
    body["attestation"]["signature"] = ("A" if sig[0] != "A" else "B") + sig[1:]
    r = post(client, body)
    assert r.status_code == 422 and reason(r) == "invalid_signature"


def test_signed_by_untrusted_key_rejected(client, signer, ids):
    from tests.attest_helpers import sign_link

    r = post(client, sign_link(new_key(), fields(*ids)))  # right issuer/key id, wrong key
    assert r.status_code == 422 and reason(r) == "invalid_signature"


def test_unknown_issuer_rejected(client, signer, ids):
    from tests.attest_helpers import sign_link

    r = post(client, sign_link(new_key(), fields(*ids), issuer="issuer:mallory"))
    assert r.status_code == 422 and reason(r) == "unknown_key"


def test_expired_attestation_rejected(client, signer, ids):
    r = post(client, signer.sign(fields(*ids), now=int(time.time()) - 7200, ttl=60,
                                  issued_offset=-60))
    assert r.status_code == 422 and reason(r) == "attestation_expired"


def test_revoked_key_rejected(client, signer, ids):
    signer.set_registry(make_registry(signer.key, revoked_at=int(time.time()) - 5))
    r = post(client, signer.sign(fields(*ids)))
    assert r.status_code == 422 and reason(r) == "key_revoked"


def test_wrong_audience_rejected(client, signer, ids):
    r = post(client, signer.sign(fields(*ids), audience="index:other"))
    assert r.status_code == 422 and reason(r) == "audience_mismatch"


def test_malformed_attestation_rejected(client, signer, ids):
    body = signer.sign(fields(*ids))
    body["attestation"]["statement"]["extra"] = "x"
    r = post(client, body)
    assert r.status_code == 422 and reason(r) == "malformed_attestation"


def test_attested_by_must_equal_signed_issuer(client, signer, ids):
    body = signer.sign(fields(*ids))
    body["attested_by"] = "issuer:bob"
    r = post(client, body)
    assert r.status_code == 422 and reason(r) == "attestation_binding_mismatch"


@pytest.mark.parametrize("tamper", [
    {"strength": 0.1}, {"relation_type": "contradicts"}, {"claim_id": "other_claim"},
])
def test_attestation_cannot_be_reused_for_a_different_link(client, signer, ids, tamper):
    body = signer.sign(fields(*ids))
    body.update(tamper)
    r = post(client, body)
    assert r.status_code == 422 and reason(r) == "attestation_binding_mismatch"


def test_wrong_statement_type_rejected(client, signer, ids):
    r = post(client, signer.sign(fields(*ids), statement_type="asserts"))
    assert r.status_code == 422 and reason(r) == "attestation_binding_mismatch"


def test_rejected_links_never_affect_status(client, signer, ids):
    post(client, {**fields(*ids), "attested_by": "forged"})
    s = client.get(f"/api/v1/evidence/epistemic-status/{ids[0]}").json()
    assert s["supporting_weight"] == 0 and s["independence_score"] == 0


# ---- #24: independence counts distinct sources ----

def _link_n(client, signer, c, sources):
    for i, src in enumerate(sources):
        e = client.post("/api/v1/evidence/", json=evidence(src, i)).json()["id"]
        r = post(client, signer.sign(fields(c, e), attestation_id=f"a{i}"))
        assert r.status_code == 201


def test_five_records_one_source_independence_at_most_point_two(client, signer):
    c = client.post("/api/v1/claims/", json=CLAIM).json()["id"]
    _link_n(client, signer, c, ["doi:10.1234/same"] * 5)
    s = client.get(f"/api/v1/evidence/epistemic-status/{c}").json()
    assert s["independence_score"] == pytest.approx(0.2)


def test_five_distinct_sources_independence_one(client, signer):
    c = client.post("/api/v1/claims/", json=CLAIM).json()["id"]
    _link_n(client, signer, c, [f"doi:10.1234/s{i}" for i in range(5)])
    s = client.get(f"/api/v1/evidence/epistemic-status/{c}").json()
    assert s["independence_score"] == 1.0


def test_source_spelling_variants_are_one_source(client, signer):
    c = client.post("/api/v1/claims/", json=CLAIM).json()["id"]
    _link_n(client, signer, c, ["DOI:10.1234/Same", " doi:10.1234/same ", "doi:10.1234/same"])
    s = client.get(f"/api/v1/evidence/epistemic-status/{c}").json()
    assert s["independence_score"] == pytest.approx(0.2)


def test_service_level_independence_distinct_sources(evidence_service):
    from app.core.models import EvidenceCreate, LinkCreate, RelationType

    for i in range(5):
        ev = evidence_service.submit_evidence(EvidenceCreate(**evidence("doi:x", i)))
        evidence_service.create_link(LinkCreate(
            claim_id="c", evidence_id=ev.id, relation_type=RelationType.SUPPORTS,
            strength=1.0, attested_by="u"))
    assert evidence_service.compute_epistemic_status("c").independence_score <= 0.2
