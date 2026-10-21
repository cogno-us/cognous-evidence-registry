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


# ---- source normalisation: spellings of one DOI / arXiv id are one source (scan4 C-1) ----

from app.evidence.service import EvidenceService  # noqa: E402

_DOI_SAME = [
    "doi:10.1234/abc", "10.1234/abc", "https://doi.org/10.1234/abc/", "https://www.doi.org/10.1234/abc",
    "http://dx.doi.org/10.1234/abc", "doi.org/10.1234/abc", "info:doi/10.1234/abc", "urn:doi:10.1234/abc",
    "https://doi.org/10.1234%2Fabc", "https://doi.org/10.1234%2fABC", "DOI: 10.1234/ABC",
    "https://doi.org/10.1234/abc?utm=1", "https://doi.org/10.1234/abc#x", "https://doi.org/doi:10.1234/abc",
]
_DOI_DIFF = [
    "doi:10.1234/abd", "doi:10.1235/abc", "doi:10.1234/abc.", "doi:10.1234/abc?utm=1", "doi:10.1234/abc#x",
    "https://publisher.example/10.1234/abc", "https://example.org/doi.org/10.1234/abc", "arxiv:2101.00001",
]
_ARXIV_SAME = [
    "arXiv:2101.00001", "arxiv:2101.00001v2", "https://arxiv.org/abs/2101.00001", "http://www.arxiv.org/abs/2101.00001v3",
    "https://arxiv.org/pdf/2101.00001.pdf", "https://arxiv.org/pdf/2101.00001v1.pdf", "arxiv.org/abs/2101.00001/",
]
_ARXIV_DIFF = ["arxiv:2101.00002", "arxiv:2102.00001", "2101.00001", "doi:10.1234/2101.00001",
               "https://arxiv.org.evil.example/abs/2101.00001"]


@pytest.mark.parametrize("spelling", _DOI_SAME)
def test_doi_spellings_unify(spelling):
    assert EvidenceService._source_key(spelling) == EvidenceService._source_key("doi:10.1234/abc") == "doi:10.1234/abc"


@pytest.mark.parametrize("other", _DOI_DIFF)
def test_different_dois_stay_distinct(other):
    assert EvidenceService._source_key(other) != "doi:10.1234/abc"


@pytest.mark.parametrize("spelling", _ARXIV_SAME)
def test_arxiv_spellings_unify(spelling):
    assert EvidenceService._source_key(spelling) == "arxiv:2101.00001"


@pytest.mark.parametrize("other", _ARXIV_DIFF)
def test_different_arxiv_ids_stay_distinct(other):
    assert EvidenceService._source_key(other) != "arxiv:2101.00001"


def test_old_style_arxiv_ids():
    key = EvidenceService._source_key
    assert key("arXiv:hep-th/9901001v2") == key("https://arxiv.org/abs/hep-th/9901001") == "arxiv:hep-th/9901001"
    assert key("arxiv:math.GT/0309136") == key("https://arxiv.org/pdf/math.gt/0309136v1.pdf")
    assert key("arxiv:hep-th/9901001") != key("arxiv:hep-ph/9901001")


def test_legacy_prefix_behaviour_kept():
    key = EvidenceService._source_key
    assert key("doi:x") == key("DOI:  x") == key("https://doi.org/x") == "doi:x"


def test_one_doi_in_four_spellings_is_one_source_end_to_end(client, signer):
    c = client.post("/api/v1/claims/", json=CLAIM).json()["id"]
    _link_n(client, signer, c, ["doi:10.1234/abc", "10.1234/abc", "https://doi.org/10.1234/abc/",
                                "https://www.doi.org/10.1234/abc"])
    s = client.get(f"/api/v1/evidence/epistemic-status/{c}").json()
    assert s["independence_score"] == pytest.approx(0.2)
    assert s["supporting_weight"] == pytest.approx(0.9)  # one source at quality 1.0 x strength 0.9, not 4x
    assert s["status"] == "proposed"


# ---- dangling references are refused on the HTTP route (scan4 C-2) ----

def test_link_to_missing_evidence_is_404_and_not_stored(client, signer):
    c = client.post("/api/v1/claims/", json=CLAIM).json()["id"]
    r = post(client, signer.sign(fields(c, "evidence_doesnotexist"), attestation_id="d1"))
    assert r.status_code == 404
    assert r.json()["detail"]["reason"] == "evidence_not_found"
    assert client.get(f"/api/v1/evidence/links/claim/{c}").json() == []


def test_link_to_missing_claim_is_404_and_not_stored(client, signer):
    e = client.post("/api/v1/evidence/", json=evidence()).json()["id"]
    r = post(client, signer.sign(fields("claim_doesnotexist", e), attestation_id="d2"))
    assert r.status_code == 404
    assert r.json()["detail"]["reason"] == "claim_not_found"
    assert client.get("/api/v1/evidence/links/claim/claim_doesnotexist").json() == []


def test_link_between_claims_checks_both_claims(client, signer):
    c = client.post("/api/v1/claims/", json=CLAIM).json()["id"]
    body = signer.sign(
        {"claim_id": c, "claim_id_2": "claim_doesnotexist", "relation_type": "supports", "strength": 0.9},
        attestation_id="d3",
    )
    r = post(client, body)
    assert r.status_code == 404
    assert r.json()["detail"]["reason"] == "claim_not_found"


def test_unsigned_dangling_link_still_401(client):
    r = post(client, {**fields("claim_doesnotexist", "evidence_doesnotexist"), "attested_by": "x"})
    assert r.status_code == 401 and reason(r) == "attestation_required"
