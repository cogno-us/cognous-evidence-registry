"""Source-key folding for generic URLs, arXiv hosts, handle URLs and lookalike letters (scan5 C-T2-5).

Weights and status thresholds are untouched; these tests only pin which spellings count as one source.
"""
from __future__ import annotations

import pytest

from app.core.models import EvidenceCreate, LinkCreate, RelationType
from app.evidence.service import EvidenceService

key = EvidenceService._source_key

_URL_SAME = [
    "https://example.org/paper", "http://example.org/paper", "https://www.example.org/paper/",
    "HTTPS://Example.ORG/paper", "https://example.org:443/paper", "http://example.org:80/paper",
    "https://example.org/paper#section-2", "https://example.org./paper", "https://WWW.EXAMPLE.ORG/paper/#x",
]
_URL_DIFF = [
    "https://example.org/paper2", "https://example.org/Paper/x", "https://example.org/paper?id=2",
    "https://example.org:8443/paper", "https://sub.example.org/paper", "https://example.com/paper",
    "https://user@example.org/paper",
]


@pytest.mark.parametrize("spelling", _URL_SAME)
def test_generic_url_spellings_unify(spelling):
    assert key(spelling) == key("https://example.org/paper")


@pytest.mark.parametrize("other", _URL_DIFF)
def test_different_urls_stay_distinct(other):
    assert key(other) != key("https://example.org/paper")


def test_url_query_is_kept_and_compared():
    assert key("https://example.org/p?id=1") == key("http://www.example.org/p/?id=1#f")
    assert key("https://example.org/p?id=1") != key("https://example.org/p?id=2")


def test_malformed_urls_do_not_raise():
    for text in ("https://", "http://[::1", "https://example.org:notaport/x", "https://exa mple.org"):
        assert isinstance(key(text), str)


@pytest.mark.parametrize("spelling", [
    "https://export.arxiv.org/abs/2101.00001", "https://arxiv.org/html/2101.00001v2", "http://export.arxiv.org/pdf/2101.00001v1.pdf",
    "https://www.alphaxiv.org/abs/2101.00001", "https://alphaxiv.org/overview/2101.00001v3", "https://alphaxiv.org/pdf/2101.00001",
])
def test_additional_arxiv_hosts_fold_to_arxiv_key(spelling):
    assert key(spelling) == "arxiv:2101.00001"


@pytest.mark.parametrize("other", [
    "https://export.arxiv.org.evil.example/abs/2101.00001", "https://notalphaxiv.org/abs/2101.00001",
    "https://alphaxiv.org/abs/2101.00002", "https://arxiv.org/list/2101.00001",
])
def test_lookalike_arxiv_hosts_and_ids_stay_distinct(other):
    assert key(other) != "arxiv:2101.00001"


@pytest.mark.parametrize("spelling", ["https://hdl.handle.net/10.1234/abc", "http://hdl.handle.net/10.1234/ABC/"])
def test_handle_resolver_for_a_doi_folds_to_doi_key(spelling):
    assert key(spelling) == "doi:10.1234/abc"


def test_handle_resolver_for_other_handles_is_not_a_doi():
    assert key("https://hdl.handle.net/2027/abc") != key("doi:2027/abc")
    assert key("https://hdl.handle.net/2027/abc") != key("https://hdl.handle.net/2027/abd")


@pytest.mark.parametrize("variant", [
    "N\u0430ture", "Natur\u0435", "N\u0430tu\u0433\u0435", "Nat\u03c5re", "N\u03b1ture", "N\u0410TUR\u0415",
])
def test_cross_script_lookalikes_fold_to_latin(variant):
    assert key(variant) == key("Nature") == "nature"


def test_cyrillic_a_and_greek_omicron_in_free_text():
    assert key("Nаture") == key("Nature") == "nature"
    assert key("Natυre") == "nature"
    assert key("Тhe Вook") != key("The Book")  # letters outside the small map are not folded


def test_lookalike_in_url_host_folds():
    assert key("https://exаmple.org/paper") == key("https://example.org/paper")


def test_distinct_free_text_sources_stay_distinct():
    assert key("Nature") != key("Science")
    assert key("Nature") != key("Nature Medicine")


# DOI and arXiv behaviour of registry #33/#34 is covered by tests/test_link_attestation.py and must not change.
def test_doi_and_arxiv_keys_unchanged():
    assert key("https://doi.org/10.1234/abc/") == "doi:10.1234/abc"
    assert key("arXiv:2101.00001v2") == "arxiv:2101.00001"


# ---- end to end: spellings of one source must not inflate weight or independence ----

def _status(evidence_service, sources):
    for i, src in enumerate(sources):
        ev = evidence_service.submit_evidence(EvidenceCreate(
            type="experiment", source_identifier=src, submitted_by="u",
            metadata={"methodology": "double-blind RCT", "sample_size": 1000, "uncertainty": 0.05,
                      "replication_history": [str(i)]}))
        evidence_service.create_link(LinkCreate(
            claim_id="c", evidence_id=ev.id, relation_type=RelationType.SUPPORTS, strength=1.0, attested_by="u"))
    return evidence_service.compute_epistemic_status("c")


@pytest.mark.parametrize("sources", [
    ["https://example.org/paper", "http://example.org/paper", "https://www.example.org/paper/"],
    ["Nature", "Nаture", "Naturе"],
    ["https://arxiv.org/abs/2101.00001", "https://export.arxiv.org/abs/2101.00001", "https://alphaxiv.org/abs/2101.00001v2"],
])
def test_one_source_in_three_spellings_is_not_supported(evidence_service, sources):
    status = _status(evidence_service, sources)
    assert status.supporting_weight == pytest.approx(1.0)
    assert status.independence_score == pytest.approx(0.2)
    assert status.status.value == "proposed"


def test_three_genuinely_different_sources_are_still_supported(evidence_service):
    status = _status(evidence_service, ["https://a.example.org/p", "https://b.example.org/p", "Nature"])
    assert status.supporting_weight == pytest.approx(3.0)
    assert status.status.value == "supported"
