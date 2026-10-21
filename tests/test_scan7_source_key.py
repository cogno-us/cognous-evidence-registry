"""Source-key host normalisation before DOI/arXiv matching, reserved percent-encodings and opaque DOI suffixes (wave 7, T2-D/T2-E)."""
from __future__ import annotations

import sys
import unicodedata

import pytest

from app.evidence.service import EvidenceService

key = EvidenceService._source_key

DOI = "doi:10.1000/abc"
ARXIV = "arxiv:2101.00001"


@pytest.mark.parametrize("spelling", [
    "https://doi.org./10.1000/abc", "https://doi.org../10.1000/abc", "https://doi.org:443/10.1000/abc",
    "http://doi.org:80/10.1000/abc", "https://doi.org:/10.1000/abc", "https://user@doi.org/10.1000/abc",
    "https://user:pw@www.doi.org./10.1000/abc", "https://doi。org/10.1000/abc", "https://doi．org/10.1000/abc",
    "https://doi｡org/10.1000/abc", "https://%64oi.org/10.1000/abc", "https://DOI.ORG%2e/10.1000/abc",
    "https://dx.doi.org.:443/10.1000/abc?x=1", "doi.org./10.1000/abc", "doi.org:443/10.1000/abc",
    "https://doi.org/10.1000/abc", "https://doi.org/10.1000/\tabc", "https://doi.org/10.1000/ab\nc", "htt\nps://doi.org/10.1000/a\rbc",
    "https://hdl.handle.net./10.1000/abc",
])
def test_doi_host_spellings_fold_to_the_doi(spelling):
    assert key(spelling) == DOI


@pytest.mark.parametrize("spelling", [
    "https://arxiv.org./abs/2101.00001", "https://arxiv.org:443/abs/2101.00001", "https://user@arxiv.org/abs/2101.00001",
    "https://arxiv。org/abs/2101.00001", "https://%61rxiv.org/pdf/2101.00001v2", "arxiv.org./abs/2101.00001",
    "arxiv.org:443/abs/2101.00001", "https://export.arxiv.org.:443/abs/2101.00001v3", "https://alphaxiv.org./abs/2101.00001",
    "https://arxiv.org/abs/2101.\t00001",
])
def test_arxiv_host_spellings_fold_to_the_id(spelling):
    assert key(spelling) == ARXIV


@pytest.mark.parametrize("other", [
    "https://doi.org:8443/10.1000/abc", "https://doi.org.evil.example/10.1000/abc", "https://evil.example/doi.org/10.1000/abc",
    "https://doi.org%2f.evil.example/10.1000/abc", "https://doi.org@evil.example/10.1000/abc",
    "https://arxiv.org:8080/abs/2101.00001", "https://arxiv.org.evil.example/abs/2101.00001",
    "https://evil.example/arxiv.org/abs/2101.00001",
])
def test_host_normalisation_does_not_merge_other_hosts(other):
    assert key(other) not in (DOI, ARXIV)


@pytest.mark.parametrize("spelling", [
    "https://example。org/p", "https://example．org/p", "https://%65xample.org/p", "https://%45XAMPLE.org%2e/p",
    "https://example.org:443/p", "https://example.org./p", "https://exa\tmple.org/p", "https://example.org/\np",
    "https://example.org/p#frag",
])
def test_generic_host_spellings_fold(spelling):
    assert key(spelling) == key("https://example.org/p") == "example.org/p"


def test_generic_url_keeps_userinfo_port_and_distinct_hosts():
    assert key("https://user@example.org/p") != key("https://example.org/p")
    assert key("https://example.org:8443/p") != key("https://example.org/p")
    assert key("https://example.org%2f.evil.example/p") != key("https://example.org/p")
    assert key("https://exampleXorg/p") != key("https://example.org/p")


def test_percent_encoded_non_ascii_path_equals_literal():
    assert key("https://example.org/%C3%A4") == key("https://example.org/ä") == key("https://example.org/%c3%a4")
    assert key("https://example.org/a%E2%82%ACb") == key("https://example.org/a€b")
    assert key("doi:10.1000/%C3%A4") == key("doi:10.1000/ä") == key("https://doi.org/10.1000/%C3%A4")
    assert key("https://example.org/%C3") != key("https://example.org/a")  # invalid UTF-8 is left alone


def test_tab_newline_cr_inside_url_are_removed_but_not_in_free_text():
    assert key("https://exa\tmple.org/p\nq\r") == key("https://example.org/pq")
    assert key("Nature\tPhysics") == key("Nature Physics") != key("NaturePhysics")


@pytest.mark.parametrize("suffix", ["a?b", "a#b"])
def test_reserved_percent_encodings_in_doi_do_not_become_delimiters(suffix):
    enc = suffix.replace("?", "%3F").replace("#", "%23")
    for prefix in ("https://doi.org/10.1000/", "https://dx.doi.org/10.1000/", "https://hdl.handle.net/10.1000/"):
        assert key(prefix + enc) != "doi:10.1000/a"
        assert key(prefix + enc) != key(prefix + "a")
        assert key(prefix + enc) == key(prefix + enc.lower())
    assert key("https://doi.org/10.1000/a%3Fb") != key("https://doi.org/10.1000/a%23b")
    assert key("https://doi.org/10.1000/a%253Fb") != key("https://doi.org/10.1000/a%3Fb")
    assert key("https://doi.org/10.1000/a%3Fb") != key("doi:10.1000/a")
    # a real query or fragment on the resolver URL is still dropped
    assert key("https://doi.org/10.1000/a?utm=1") == key("https://doi.org/10.1000/a#x") == "doi:10.1000/a"
    # %2F is the same DOI as a literal slash
    assert key("https://doi.org/10.1000%2Fa") == key("https://doi.org/10.1000/a")


def test_doi_suffix_is_opaque_inside_but_case_insensitive():
    assert key("doi:10.1000/a//b") != key("doi:10.1000/a/b")
    assert key("doi:10.1000/a//b") == "doi:10.1000/a//b"
    assert key("doi:10.1000/a.") == "doi:10.1000/a." != key("doi:10.1000/a")
    assert key("https://doi.org/10.1000/a.") != key("https://doi.org/10.1000/a")
    assert key("doi:10.1000/ABC") == key("DOI:10.1000/abc") == key("https://doi.org/10.1000/%41bc") == DOI


def test_url_path_trailing_dot_is_kept():
    assert key("https://example.org/a.") != key("https://example.org/a")
    assert key("https://example.org/a.") == "example.org/a."
    assert key("https://example.org/a/..") == key("https://example.org")  # dot segments are still resolved


_SAMPLES = [
    "https://doi.org./10.1000/abc", "https://user@arxiv.org:443/abs/2101.00001v2", "https://example。org/%C3%A4/x.",
    "https://doi.org/10.1000/a%3Fb", "doi:10.1000/a//b", "https://example.org/%41%2f%25%5F", "https://%65xample.org/p?q=%C3%A4",
    "https://exa\tmple.org/a", "https://doi.org/10.1000/%25%34%31", "https://doi.org/10.1000/%EF%BC%85%EF%BC%93f",
    "https://example.org/%EF%BC%85c3%EF%BC%85a4", "DOI:  10.1000/ABC///", "10.1000/a%2541",
]


@pytest.mark.parametrize("sample", _SAMPLES)
def test_idempotent_on_samples(sample):
    once = key(sample)
    assert key(once) == once


def _interesting(ch: str) -> bool:
    """Every character a fold could touch: ASCII, anything NFKD/casefold changes, and any C*, Z*, M* or P* character."""
    cat = unicodedata.category(ch)
    if cat in ("Cn", "Co") and ord(ch) % 997:  # unassigned and private use are all deleted alike; sample them
        return False
    return (
        ch.isascii() or cat[0] in "CZMPS" or unicodedata.normalize("NFKD", ch) != ch or ch.casefold() != ch
        or ch.translate(EvidenceService._CONFUSABLES) != ch
    )


def test_idempotent_over_unicode_in_url_positions():
    """key(key(x)) == key(x) for every character a fold can touch, in host, path, DOI suffix and arXiv positions. (The
    owner-side full sweep over all code points and more templates was run once by hand; this keeps CI fast.)"""
    templates = ["https://doi{}org/10.1000/a{}b", "https://example{}org/p{}", "doi:10.1000/{}", "https://example.org/%{}"]
    bad = []
    for cp in range(sys.maxunicode + 1):
        if 0xD800 <= cp < 0xE000:
            continue
        ch = chr(cp)
        if not _interesting(ch):
            continue
        for t in templates:
            s = t.format(*([ch] * t.count("{}")))
            once = key(s)
            if key(once) != once:
                bad.append((s, once))
    assert not bad[:5], bad[:5]
