"""Filesystem paths for downloadable model assets.

Uses the same frozen-vs-dev dispatch a packaged front-end applies,
but lives in the ``brailix`` package so adapter code can resolve
model directories on its own without importing any front-end layer.

Resolution rules:

* Frozen build (Nuitka standalone): ``<exe parent>/models/``.
  Sits next to the application executable so a copied portable bundle
  carries its downloaded weights along.
* Dev / source mode: ``<cwd>/models/``.  Predictable for
  developers running the application from the repo root;
  ``.gitignore`` already excludes ``models/`` so test weights don't
  get committed.
* Fallback when the chosen root is **not writable**: a per-user data
  directory (``%LOCALAPPDATA%/brailix/models`` on Windows, an
  XDG / home path elsewhere).  This is the case when brailix is
  imported into *another* application's frozen interpreter — e.g. the
  NVDA add-on, where ``sys.executable`` is ``nvda.exe`` under
  ``C:/Program Files`` — or installed read-only.  Without it,
  resolving a model dir would raise ``PermissionError`` mid-compile.

Both :func:`get_models_root` and :func:`get_model_dir` create the
directory on first call — adapters should be able to assume the
path exists, and a missing-but-creatable directory is never the
right error condition (the failure modes that matter are missing
*files inside it*, surfaced by the adapter's own
``_ensure_model_installed`` check raising
:class:`~brailix.core.errors.ModelNotInstalledError`).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_MODELS_DIRNAME = "models"


def _is_frozen() -> bool:
    """``True`` when running from a PyInstaller / Nuitka standalone build.

    Nuitka doesn't set ``sys.frozen`` (only PyInstaller does); it sets a
    module-level ``__compiled__``.  Check both.
    """
    return bool(getattr(sys, "frozen", False)) or "__compiled__" in globals()


def _portable_root() -> Path:
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def _user_data_root() -> Path:
    """Per-user, writable base directory for brailix assets.

    Used as the fallback when the portable root isn't writable. Honors
    ``LOCALAPPDATA`` / ``APPDATA`` (Windows) then ``XDG_DATA_HOME``,
    finally ``~/.local/share``.
    """
    win = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if win:
        return Path(win) / "brailix"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "brailix"
    return Path.home() / ".local" / "share" / "brailix"


def _make_writable_dir(path: Path) -> bool:
    """Create ``path`` (with parents) and report whether it's usable.

    Returns ``False`` instead of raising when the directory can't be
    created (read-only parent, a file in the way) so the caller can fall
    back to another location.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(path, os.W_OK)


def get_models_root() -> Path:
    """Return a writable ``models/`` directory, creating it on first call.

    Prefers the portable bundle root (next to the executable when frozen,
    else the cwd) so a copied portable bundle carries its weights. Falls
    back to a per-user data directory when that root is read-only.

    Safe to call from any thread / process — :meth:`Path.mkdir` with
    ``exist_ok=True`` is idempotent.
    """
    portable = _portable_root() / _MODELS_DIRNAME
    if _make_writable_dir(portable):
        return portable
    fallback = _user_data_root() / _MODELS_DIRNAME
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_model_dir(name: str) -> Path:
    """Return ``models/<name>/`` for a registered model, creating it.

    ``name`` is the registry key (e.g. ``"hanlp"``, ``"g2pw"``); the
    caller is responsible for picking a stable, filesystem-safe
    identifier.  Empty or path-component names raise ``ValueError``
    rather than silently writing outside ``models/``.
    """
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"invalid model name: {name!r}")
    target = get_models_root() / name
    target.mkdir(parents=True, exist_ok=True)
    return target


__all__ = ("get_models_root", "get_model_dir")
