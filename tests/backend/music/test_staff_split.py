"""Multi-staff part splitting (``_emit_part`` staff loop).

A part whose notes carry distinct ``<staff>`` numbers is emitted staff by
staff, separated by ``music_part_sep``. Per-staff reading state — octave
inference, value-sign baseline, hairpin, AND the Par. 9.2 clef — must
restart at each staff boundary so one staff's context never leaks into the
next. This path had no test coverage; the clef-reset case below is a
regression guard for that leak.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from brailix.backend.music import emit_tree
from brailix.core.config import load_profile
from brailix.core.context import BackendContext


@pytest.fixture(scope="module")
def profile():
    return load_profile("cn_current")


@pytest.fixture
def ctx():
    return BackendContext(profile="cn_current", block_type="score")


def _roles(cells):
    return [c.role for c in cells]


def _quarter_note_dots(profile, step: str, octave: int):
    """Note-cell dots of a lone quarter note — used to identify which pitch
    a chord picked as its written (first-emitted) note. The note cell
    encodes pitch-letter + value only (octave is a separate cell), so C and
    E differ here regardless of register."""
    m = ET.fromstring(
        '<score-partwise><part id="P1"><measure number="1">'
        f"<note><pitch><step>{step}</step><octave>{octave}</octave></pitch>"
        "<duration>1</duration><type>quarter</type></note>"
        "</measure></part></score-partwise>"
    )
    cells = emit_tree(m, BackendContext(profile="cn_current", block_type="score"), profile)
    return next(c.dots for c in cells if c.role == "music_note")


class TestClefResetsAtStaffBoundary:
    def test_unnumbered_clef_does_not_leak_into_staff_two(self, profile, ctx):
        # An unnumbered <clef> belongs to staff 1, so staff 2 declares no
        # clef of its own. The G (treble) clef must NOT leak into staff 2:
        # leaked, staff 2's chord reads treble (uppermost = written, so E3);
        # reset at the staff boundary, staff 2 falls back to the clef-less
        # default (source order, first note written, so C3). The chord is
        # authored low→high (C3 root, E3 chord) precisely so the two
        # behaviours pick different written notes.
        score = ET.fromstring(
            '<score-partwise version="4.0"><part id="P1">'
            '<measure number="1">'
            "<attributes><divisions>1</divisions>"
            "<clef><sign>G</sign><line>2</line></clef>"
            "</attributes>"
            # staff 1: a single treble note
            "<note><pitch><step>C</step><octave>4</octave></pitch>"
            "<duration>1</duration><type>quarter</type><staff>1</staff></note>"
            # staff 2: a chord, source order low (C3) then high (E3)
            "<note><pitch><step>C</step><octave>3</octave></pitch>"
            "<duration>1</duration><type>quarter</type><staff>2</staff></note>"
            "<note><chord/><pitch><step>E</step><octave>3</octave></pitch>"
            "<duration>1</duration><type>quarter</type><staff>2</staff></note>"
            "</measure></part></score-partwise>"
        )
        cells = emit_tree(score, ctx, profile)
        roles = _roles(cells)
        # Staff 1 and staff 2 streams are separated by a part-sep.
        sep_idx = roles.index("music_part_sep")
        staff2_notes = [c for c in cells[sep_idx:] if c.role == "music_note"]
        assert staff2_notes, "staff 2 should emit notes after the separator"
        # The written (first-emitted) note of staff 2's chord must be C3
        # (clef-less default), not E3 (which a leaked treble clef picks).
        assert staff2_notes[0].dots == _quarter_note_dots(profile, "C", 3)
        assert staff2_notes[0].dots != _quarter_note_dots(profile, "E", 3)
