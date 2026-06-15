"""Sync guard for the three MusicXML ``<type>`` → BANA lookup tables.

``_TYPE_TO_FAMILY`` (note shapes, utils), ``_REST_FAMILY`` (rest shapes),
and ``_VALUE_CATEGORY`` (Par. 2.4 value-sign category) are three separate
projections of the *same* MusicXML duration-type key set. They can't be
merged into one table (different value spaces), but they must stay in sync
on their keys: a ``<type>`` present in one but missing from another
silently degrades to the quarter / large default at translation time —
exactly the breve regression both ``_TYPE_TO_FAMILY`` and ``_REST_FAMILY``
record in their comments. This guard fails if the three ever drift apart,
so adding a new duration type forces updating all three at once.
"""

from __future__ import annotations

from brailix.backend.music.handlers.notes import _REST_FAMILY, _VALUE_CATEGORY
from brailix.backend.music.utils import _TYPE_TO_FAMILY


def test_type_tables_cover_identical_key_sets():
    family_keys = set(_TYPE_TO_FAMILY)
    assert set(_REST_FAMILY) == family_keys, (
        "rest-family table drifted from note-family table: "
        f"{set(_REST_FAMILY) ^ family_keys}"
    )
    assert set(_VALUE_CATEGORY) == family_keys, (
        "value-category table drifted from note-family table: "
        f"{set(_VALUE_CATEGORY) ^ family_keys}"
    )
