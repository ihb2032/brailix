"""Classification of non-standard input characters, for diagnostics.

A core character utility, depended on by every layer: the frontend segmenter
classifies input, the prose / math / chemistry backends report a stray
full-width symbol or invisible zero-width char the same actionable way, and an
editing tool offers the fix — all naming the *writing* problem instead of a
bare "unknown".  It lives in ``core`` (not ``backend``) precisely so frontend
and backend can both depend on it without a reverse import.

Nothing here rewrites input: a full-width ``＝`` (U+FF1D) and a half-width
``=`` (U+003D) are different code points, and the translator never silently
folds one into the other. It only classifies the character so the warning
can tell the writer what to fix.

:data:`INVISIBLE_CPS` and :func:`fold_fullwidth` expose that knowledge — the
set of invisible code points and the canonical half-width form — as the
single source of truth, so an editing tool can offer the fix (rewrite the
source) without re-deriving "what counts as non-standard". Folding is never
done here; that is an editor's job.
"""

from __future__ import annotations

# Invisible / zero-width formatting characters that almost always arrive as
# paste artefacts from the web, a PDF, or Word: ZWSP / ZWNJ / ZWJ (U+200B–
# U+200D), the word joiner (U+2060), the soft hyphen (U+00AD), and the
# BOM / ZWNBSP (U+FEFF). The single authority for "this code point is
# invisible debris": diagnostics warn on it and an editor strips it, both
# reading this one set so the two can't drift apart.
INVISIBLE_CPS: frozenset[int] = frozenset(
    {0x200B, 0x200C, 0x200D, 0x2060, 0x00AD, 0xFEFF}
)


def fold_fullwidth(ch: str) -> str | None:
    """The half-width form of a single full-width character, or ``None``.

    A full-width ASCII variant (U+FF01–U+FF5E) folds to its half-width ASCII
    form — each sits exactly ``0xFEE0`` above its half-width twin — and the
    ideographic space (U+3000) folds to a normal space. Returns ``None`` for
    anything else, including an ordinary half-width char, so a caller folds
    only when there is a mapping.

    This is *only* the Unicode fact "what is the half-width form". Whether a
    character should actually be folded in a given context is the caller's
    policy, deliberately not encoded here: the prose backend folds full-width
    digits but warns on them inside math, and an editor may fold digits,
    letters and operators while leaving full-width Chinese punctuation (which
    prose genuinely wants) alone.
    """
    if len(ch) != 1:
        return None
    cp = ord(ch)
    if 0xFF01 <= cp <= 0xFF5E:
        return chr(cp - 0xFEE0)
    if cp == 0x3000:
        return " "
    return None


def nonstandard_char_hint(text: str) -> str | None:
    """An actionable hint when ``text`` is a single non-standard character:
    a full-width ASCII variant (naming its half-width form), a full-width
    space, or an invisible zero-width char. Returns ``None`` for an ordinary
    character, so callers append the hint only when there is one to give."""
    if len(text) != 1:
        return None
    cp = ord(text)
    half = fold_fullwidth(text)
    if half is not None:
        if cp == 0x3000:
            return "full-width space (U+3000); use a normal space"
        return f"full-width '{text}' (U+{cp:04X}); use the half-width '{half}'"
    if cp in INVISIBLE_CPS:
        return f"zero-width / invisible character (U+{cp:04X})"
    return None


__all__ = ("INVISIBLE_CPS", "fold_fullwidth", "nonstandard_char_hint")
