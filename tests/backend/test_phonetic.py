"""Phonetic (IPA) braille backend tests: PhoneticInline -> braille cells.

Pins the English phonetic-symbol table and the greedy longest-match walk:

* every cell comes from the profile's phonetic table (the backend owns no
  phoneme spelling of its own);
* a multi-character phoneme (long vowel ``iː``, diphthong ``eɪ``,
  affricate ``tʃ``) resolves as a single phoneme ahead of its
  one-character prefix (``t`` / ``e``);
* an unmapped symbol (a stress mark ``ˈ``) is flagged with
  ``PHONETIC_UNKNOWN_SYMBOL`` and a blank cell, never mistranslated.
"""

from __future__ import annotations

import pytest

from brailix.backend.phonetic import translate_phonetic
from brailix.core.config import load_profile
from brailix.core.context import BackendContext
from brailix.core.errors import RunMode, WarningCollector
from brailix.core.span import Span
from brailix.ir.inline import PhoneticInline


@pytest.fixture(scope="module")
def profile():
    return load_profile("cn_current")


def render(surface: str, profile, *, span: Span | None = None):
    """Translate one phoneme run; return ``(cells, warnings)``."""
    wc = WarningCollector(mode=RunMode.NORMAL)
    ctx = BackendContext(profile="cn_current", warnings=wc)
    node = PhoneticInline(surface=surface, span=span)
    return translate_phonetic(node, ctx, profile), wc


def dots(cells):
    return [c.dots for c in cells]


# ---------------------------------------------------------------------------
# Single phonemes from each class
# ---------------------------------------------------------------------------


class TestSinglePhoneme:
    def test_consonants_use_letter_braille(self, profile):
        # The plosive / nasal consonants coincide with English-braille
        # letter cells: p = ⠏ (1234), b = ⠃ (12), t = ⠞ (2345), m = ⠍ (134).
        assert dots(render("p", profile)[0]) == [(1, 2, 3, 4)]
        assert dots(render("b", profile)[0]) == [(1, 2)]
        assert dots(render("t", profile)[0]) == [(2, 3, 4, 5)]
        assert dots(render("m", profile)[0]) == [(1, 3, 4)]

    def test_digraph_consonants(self, profile):
        # θ = ⠹ "th" (1456), ʃ = ⠩ "sh" (156), ŋ = ⠫ "ng" (1246).
        assert dots(render("θ", profile)[0]) == [(1, 4, 5, 6)]
        assert dots(render("ʃ", profile)[0]) == [(1, 5, 6)]
        assert dots(render("ŋ", profile)[0]) == [(1, 2, 4, 6)]

    def test_short_vowel(self, profile):
        assert dots(render("æ", profile)[0]) == [(1, 4, 6)]
        assert dots(render("ə", profile)[0]) == [(1, 2, 6)]
        assert dots(render("ɪ", profile)[0]) == [(2, 4)]

    def test_role_is_phonetic(self, profile):
        cells, _ = render("p", profile)
        assert all(c.role == "phonetic" for c in cells)
        assert cells[0].source_text == "p"


# ---------------------------------------------------------------------------
# Multi-cell phonemes (long vowels / diphthongs) matched whole
# ---------------------------------------------------------------------------


class TestMultiCellPhoneme:
    def test_long_vowel_is_two_cells(self, profile):
        # iː = ⠊⠒ : short-vowel cell (24) + length mark (25), matched as ONE
        # phoneme so both cells carry source_text "iː".
        cells, wc = render("iː", profile)
        assert dots(cells) == [(2, 4), (2, 5)]
        assert [c.source_text for c in cells] == ["iː", "iː"]
        assert not wc.warnings

    def test_diphthong(self, profile):
        assert dots(render("eɪ", profile)[0]) == [(1, 5), (2, 4)]
        assert dots(render("əʊ", profile)[0]) == [(1, 2, 6), (1, 3, 6)]

    def test_affricate_is_one_phoneme(self, profile):
        cells, _ = render("tʃ", profile)
        assert dots(cells) == [(2, 3, 4, 5), (1, 5, 6)]
        assert [c.source_text for c in cells] == ["tʃ", "tʃ"]


# ---------------------------------------------------------------------------
# Greedy longest-match
# ---------------------------------------------------------------------------


class TestGreedyMatch:
    def test_affricate_beats_prefix(self, profile):
        # "tʃ" must match the affricate, not "t" then unknown "ʃ"... ʃ is
        # known too, but the point is one 2-char phoneme, not two 1-char.
        cells, _ = render("tʃ", profile)
        assert len({c.source_text for c in cells}) == 1  # all "tʃ"

    def test_lone_t_is_plosive(self, profile):
        # A "t" not followed by ʃ/s/r stays the plosive.
        cells, _ = render("t", profile)
        assert dots(cells) == [(2, 3, 4, 5)]
        assert cells[0].source_text == "t"

    def test_ts_affricate(self, profile):
        cells, _ = render("ts", profile)
        assert dots(cells) == [(2, 3, 4, 5), (2, 3, 4)]
        assert [c.source_text for c in cells] == ["ts", "ts"]


# ---------------------------------------------------------------------------
# Word-length transcriptions
# ---------------------------------------------------------------------------


class TestWord:
    def test_cat(self, profile):
        # kæt : k(13) æ(146) t(2345)
        cells, wc = render("kæt", profile)
        assert dots(cells) == [(1, 3), (1, 4, 6), (2, 3, 4, 5)]
        assert not wc.warnings

    def test_cheese(self, profile):
        # tʃiːz : tʃ(2 cells) iː(2 cells) z(1 cell) = 5 cells
        cells, wc = render("tʃiːz", profile)
        assert dots(cells) == [
            (2, 3, 4, 5), (1, 5, 6),  # tʃ
            (2, 4), (2, 5),           # iː
            (1, 3, 5, 6),             # z
        ]
        assert not wc.warnings

    def test_g_alias(self, profile):
        # The IPA script g (ɡ) and the ASCII g share one cell.
        assert dots(render("g", profile)[0]) == [(1, 2, 4, 5)]
        assert dots(render("ɡ", profile)[0]) == [(1, 2, 4, 5)]


# ---------------------------------------------------------------------------
# Unknowns / spaces / edges
# ---------------------------------------------------------------------------


class TestUnknownAndEdges:
    def test_stress_mark_warns(self, profile):
        # The table has no stress mark — flag it, translate the rest.
        cells, wc = render("ˈæpl", profile)
        assert cells[0].role == "unknown"
        assert cells[0].dots == ()
        assert cells[0].source_text == "ˈ"
        assert [c.dots for c in cells[1:]] == [(1, 4, 6), (1, 2, 3, 4), (1, 2, 3)]
        codes = [w.code for w in wc.warnings]
        assert codes == ["PHONETIC_UNKNOWN_SYMBOL"]
        assert wc.warnings[0].surface == "ˈ"

    def test_internal_space_is_blank_cell(self, profile):
        cells, wc = render("k t", profile)
        assert [c.role for c in cells] == ["phonetic", "space", "phonetic"]
        assert cells[1].dots == ()
        assert not wc.warnings

    def test_empty_surface(self, profile):
        assert render("", profile)[0] == []


# ---------------------------------------------------------------------------
# Source spans (proofreading provenance)
# ---------------------------------------------------------------------------


class TestSourceSpan:
    def test_per_phoneme_span(self, profile):
        # "kæt" at offset 10: each cell maps back onto its phoneme char.
        cells, _ = render("kæt", profile, span=Span(10, 13))
        spans = [(c.source_span.start, c.source_span.end) for c in cells]
        assert spans == [(10, 11), (11, 12), (12, 13)]

    def test_multi_cell_phoneme_shares_span(self, profile):
        # iː is two cells but one source phoneme → both share the span.
        cells, _ = render("iː", profile, span=Span(5, 7))
        assert all(c.source_span == Span(5, 7) for c in cells)


# ---------------------------------------------------------------------------
# Table completeness / integrity
# ---------------------------------------------------------------------------


class TestTableIntegrity:
    def test_full_inventory_loaded(self, profile):
        # 48 IPA phonemes + the ASCII-g alias = 49 entries.
        assert len(profile.phonetic) == 49

    def test_every_entry_resolves_to_cells(self, profile):
        for sym, seq in profile.phonetic.items():
            assert seq, f"{sym!r} resolved to an empty cell sequence"
            assert all(isinstance(cell, tuple) for cell in seq)

    def test_max_symbol_len(self, profile):
        # Every multi-character phoneme is exactly two characters.
        assert profile.phonetic_max_symbol_len() == 2
