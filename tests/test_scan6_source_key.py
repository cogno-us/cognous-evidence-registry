"""Source-key folding of invisible characters, slash lookalikes, trailing dots and URL paths (scan6 F3)."""
from __future__ import annotations

import pytest

from app.evidence.service import EvidenceService

key = EvidenceService._source_key

_BASES = ["doi:10.1234/abc", "https://example.org/paper", "Nature"]
_SPACES = [" ", " ", " ", "　", "\t", "\n"]
_INVISIBLE = [
    "\x00", "\x7f", "\x08", "⠀", "ㅤ", "ᅟ", "ᅠ", "ﾠ", "​", "­", "͏", "️",
    "", "\U000e0001", "͸",
]


@pytest.mark.parametrize("junk", _SPACES)
@pytest.mark.parametrize("base", _BASES)
def test_surrounding_space_like_characters_fold(junk, base):
    assert key(base + junk) == key(base)
    assert key(junk + base) == key(base)


@pytest.mark.parametrize("junk", _INVISIBLE)
@pytest.mark.parametrize("base", _BASES)
def test_invisible_characters_fold_anywhere(junk, base):
    assert key(base + junk) == key(base)
    assert key(junk + base) == key(base)
    assert key(base[:6] + junk + base[6:]) == key(base)


def test_percent_encoded_control_in_doi_folds():
    assert key("doi:10.1234/abc%00") == key("doi:10.1234/abc")
    assert key("https://doi.org/10.1234/abc%E2%A0%80") == "doi:10.1234/abc"


# wave 7 (T2-E): the scan6 tests here folded a trailing dot and a doubled slash inside a DOI suffix. DOI suffixes are
# opaque, so ``10.1234/abc.`` and ``10.1234//abc`` are different DOIs from ``10.1234/abc``; they no longer fold.
@pytest.mark.parametrize("spelling", ["doi:10.1234/abc.", "doi:10.1234/abc..", "10.1234/abc.", "https://doi.org/10.1234/abc."])
def test_trailing_dot_in_doi_suffix_stays_distinct(spelling):
    assert key(spelling) != key("doi:10.1234/abc")
    assert key(spelling).startswith("doi:10.1234/abc.")


@pytest.mark.parametrize("spelling", [
    "doi:10.1234∕abc", "doi:10.1234⁄abc", "doi:10.1234⧸abc", "doi:10.1234/abc//", "https://doi.org/10.1234/abc/",
])
def test_slash_lookalikes_and_trailing_slashes_fold_in_doi(spelling):
    assert key(spelling) == "doi:10.1234/abc"


@pytest.mark.parametrize("spelling", [
    "https://example.org//a", "https://example.org/./a", "https://example.org/b/../a", "https://example.org/%61",
    "https://example.org/%2e/a", "https://example.org/b/%2E%2e/a", "https://example.org∕a", "https://example.org/a/.",
    "https://example.org/a/b/..", "https://example.org/a//", "https://example.org/x/../../a",
])
def test_url_path_normalisation(spelling):
    assert key(spelling) == key("https://example.org/a") == "example.org/a"


def test_reserved_percent_encoding_and_real_path_differences_stay_distinct():
    assert key("https://example.org/a%2fb") != key("https://example.org/a/b")
    assert key("https://example.org/a/b") != key("https://example.org/a")
    assert key("https://example.org/a") != key("https://example.org/b")
    assert key("https://example.org/a?x=./b") != key("https://example.org/a")


def test_distinct_dois_stay_distinct():
    assert key("doi:10.1234/abc") != key("doi:10.1234/abd")
