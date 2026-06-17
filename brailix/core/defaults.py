"""Built-in default adapter names — single source of truth.

Whenever the library needs to pick a "first reasonable choice" of
segmenter / normalizer / analyzer / resolver / renderer, it pulls the
name from this module instead of hard-coding a string, so the shipping
default is a one-line edit and references stay in sync.

There is deliberately **no** default profile or language. A profile is
a braille standard the caller must choose explicitly — ``Pipeline``,
the ``parse_*`` helpers, and the CLI ``--profile`` flag all require it —
and a profile's ``language`` is declared in its own JSON. The library
does not privilege any one language or standard as a built-in fallback.

These are **names registered with the corresponding registries**, not
type names. Users who write custom adapters register them under their
own name and pass that name to :class:`Pipeline`.
"""

from __future__ import annotations

# Frontend adapter chain
DEFAULT_SEGMENTER: str = "default"
DEFAULT_NORMALIZER: str = "default"
# Both analyzer and resolver default to "auto" so the heaviest
# installed implementation is picked at runtime — users don't need
# to know the registry to get good behavior out of the box.
# Override with a specific adapter name (``"jieba"``, ``"hanlp"``,
# ``"pypinyin"`` ...) when reproducibility matters.
DEFAULT_ZH_ANALYZER: str = "auto"
DEFAULT_PINYIN_RESOLVER: str = "auto"

# Output
DEFAULT_RENDERER: str = "unicode"
