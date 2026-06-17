"""Tests for the ``script_cluster`` math source adapter.

The docx input layer linearises a Word super/subscript "formatted text"
formula (``x²`` / ``H₂O`` typed as runs) to a ``base ^{..} _{..}`` source
string; this adapter rebuilds the MathML and — for the ``script_cluster_chem``
variant — judges whether the cluster is chemistry. The conversion and the
judgment both live here in the frontend, not in the input layer.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from brailix.core.context import MathContext
from brailix.frontend.math import parse_math_tree
from brailix.frontend.math.adapters.script_cluster import _parse_atoms
from brailix.frontend.math.registry import math_source_registry


class TestParseAtoms:
    @pytest.mark.parametrize(
        "source, atoms",
        [
            ("x^{2}", [("x", None), ("2", "super")]),
            ("H_{2}O", [("H", None), ("2", "sub"), ("O", None)]),
            (
                "x_{1}^{2}",
                [("x", None), ("1", "sub"), ("2", "super")],
            ),
            (
                "Ca^{2+}",  # baseline is parsed char-by-char
                [("C", None), ("a", None), ("2", "super"), ("+", "super")],
            ),
        ],
    )
    def test_round_trip(self, source, atoms) -> None:
        assert _parse_atoms(source) == atoms

    def test_malformed_tag_degrades_to_literal(self) -> None:
        # A stray ``^`` with no closing brace can only come from a corrupt
        # payload; it must not raise — it falls back to a baseline char.
        assert _parse_atoms("x^{2") == [
            ("x", None),
            ("^", None),
            ("{", None),
            ("2", None),
        ]


def _mathml(source: str, payload: str) -> str:
    return math_source_registry.get(source).to_mathml(
        payload, MathContext(profile="cn_current", source=source)
    )


class TestGenericMath:
    def test_superscript(self) -> None:
        out = _mathml("script_cluster", "x^{2}")
        assert "<msup>" in out and "<mi>x</mi>" in out and "<mn>2</mn>" in out

    def test_subscript(self) -> None:
        out = _mathml("script_cluster", "H_{2}O")
        assert "<msub>" in out and "<mi>O</mi>" in out

    def test_subsup(self) -> None:
        assert "<msubsup>" in _mathml("script_cluster", "x_{1}^{2}")

    def test_digit_run_base_is_one_mn(self) -> None:
        assert "<mn>10</mn>" in _mathml("script_cluster", "10^{3}")

    def test_minus_is_canonicalised(self) -> None:
        # Hyphen-minus in a script run becomes U+2212 so the backend's symbol
        # table matches.
        assert "−" in _mathml("script_cluster", "10^{-3}")

    def test_plain_variant_never_tags_chem(self) -> None:
        # Even a chemical-looking cluster stays plain math under the
        # non-chem source name.
        assert "data-bk-chem" not in _mathml("script_cluster", "H_{2}O")


class TestChemJudgment:
    def test_water_is_chem(self) -> None:
        assert 'data-bk-chem="1"' in _mathml("script_cluster_chem", "H_{2}O")

    def test_charge_is_chem(self) -> None:
        assert 'data-bk-chem="1"' in _mathml("script_cluster_chem", "Ca^{2+}")

    def test_single_letter_variable_stays_math(self) -> None:
        # V is vanadium, but a lone single-letter subscript is almost always
        # a variable — no chemical signature, so it stays math.
        out = _mathml("script_cluster_chem", "V_{1}")
        assert "data-bk-chem" not in out and "<msub>" in out

    def test_lowercase_exponent_stays_math(self) -> None:
        # x² — a bare exponent (not a charge) can't be chemistry.
        out = _mathml("script_cluster_chem", "x^{2}")
        assert "data-bk-chem" not in out and "<msup>" in out


class TestThroughParseMathTree:
    def test_normalised_tree_via_registry(self) -> None:
        # The public path the pipeline uses: source name → adapter → normalize.
        tree = parse_math_tree("x^{2}", MathContext(profile="cn_current", source="script_cluster"))
        assert tree is not None
        assert tree.find(".//msup") is not None

    def test_chem_tree_carries_attribute(self) -> None:
        tree = parse_math_tree("H_{2}O", MathContext(profile="cn_current", source="script_cluster_chem"))
        assert tree is not None
        assert tree.get("data-bk-chem") == "1"
        # Sanity: it really is the normalised math root.
        assert tree.tag == "math"
        ET.tostring(tree, encoding="unicode")  # round-trips without error
