"""Translate a :class:`~brailix.ir.inline.PhoneticInline` node to braille.

A phonetic transcription is a flat run of IPA phonemes (English
pronunciation), recognised in prose as a ``/.../`` or ``[...]`` region
and carried verbatim on the node's ``surface``. Translation is a greedy
longest-match walk over that surface against the profile's phonetic
table: at each position the longest phoneme that matches wins, so the
affricate ``tʃ`` and the diphthong ``eɪ`` resolve as single phonemes
ahead of their one-character prefixes ``t`` / ``e``. Each matched phoneme
emits its cell sequence (one or more cells) from the table.

Every cell comes from ``profile.phonetic`` — the backend owns no phoneme
spelling of its own. A character with no table entry (a stress mark
``ˈ`` / ``ˌ`` the table doesn't define, a stray symbol) is flagged with a
``PHONETIC_UNKNOWN_SYMBOL`` warning and a blank unknown cell, so one
unmapped mark never sinks the rest of the transcription; an internal
space becomes a blank cell.
"""

from __future__ import annotations

from brailix.core.chars import nonstandard_char_hint
from brailix.core.config import BrailleProfile
from brailix.core.context import BackendContext
from brailix.core.span import Span
from brailix.ir.braille import BrailleCell
from brailix.ir.inline import PhoneticInline


def translate_phonetic(
    node: PhoneticInline, ctx: BackendContext, profile: BrailleProfile
) -> list[BrailleCell]:
    """Greedy longest-match a phoneme run into braille cells."""
    text = node.surface
    if not text:
        return []
    base = node.span.start if node.span else 0
    has_span = node.span is not None
    max_len = profile.phonetic_max_symbol_len()
    out: list[BrailleCell] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            out.append(
                BrailleCell(
                    dots=(),
                    role="space",
                    source_span=Span(base + i, base + i + 1) if has_span else None,
                    source_text=" ",
                )
            )
            i += 1
            continue
        match = _longest_match(text, i, max_len, profile)
        if match is None:
            out.append(_emit_unknown(ch, base + i, has_span, ctx))
            i += 1
            continue
        symbol, cells = match
        span = Span(base + i, base + i + len(symbol)) if has_span else None
        for dots in cells:
            out.append(
                BrailleCell(
                    dots=dots,
                    role="phonetic",
                    source_span=span,
                    source_text=symbol,
                )
            )
        i += len(symbol)
    return out


def _longest_match(
    text: str, i: int, max_len: int, profile: BrailleProfile
) -> tuple[str, tuple[tuple[int, ...], ...]] | None:
    """Return the longest phoneme matching at ``text[i:]`` plus its cell
    sequence, or ``None`` when no table entry starts here.

    Tries the table's longest key length down to 1, so the affricate
    ``tʃ`` is matched before the plosive ``t`` and the diphthong ``eɪ``
    before the vowel ``e``. The upper bound comes from the table
    (:meth:`BrailleProfile.phonetic_max_symbol_len`), not a hardcoded 2,
    so a future longer phoneme needs no code change here."""
    n = len(text)
    for length in range(min(max_len, n - i), 0, -1):
        symbol = text[i : i + length]
        cells = profile.phonetic_symbol(symbol)
        if cells is not None:
            return symbol, cells
    return None


def _emit_unknown(
    ch: str, offset: int, has_span: bool, ctx: BackendContext
) -> BrailleCell:
    """Flag one unmapped character and return a blank unknown cell.

    The character is carried verbatim on the cell (not folded): the
    warning names what the author typed, and no original symbol is
    silently rewritten. A stress mark ``ˈ`` / ``ˌ`` lands here because the
    phonetic table intentionally has no cell for it."""
    span = Span(offset, offset + 1) if has_span else None
    hint = nonstandard_char_hint(ch)
    message = f"no braille mapping for phonetic symbol {ch!r}"
    if hint:
        message = f"{message} — {hint}"
    ctx.warnings.warn(
        code="PHONETIC_UNKNOWN_SYMBOL",
        message=message,
        surface=ch,
        span=span,
        source="backend.phonetic",
    )
    return BrailleCell(dots=(), role="unknown", source_span=span, source_text=ch)
