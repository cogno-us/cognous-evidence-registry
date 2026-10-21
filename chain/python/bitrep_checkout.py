"""Verification that a BitRep checkout is exactly the pinned commit, whatever ``git status`` says.

``git status`` trusts the index: a tracked file flagged skip-worktree or assume-unchanged can be edited and still look
clean, and ignored files are never listed. Because the adapter executes BitRep's verifier in process, the checkout is
therefore checked directly:

1. HEAD equals the pin (git replace refs are disabled so they cannot redirect the tree read).
2. No tracked file carries an assume-unchanged or skip-worktree flag (``git ls-files -v``: lowercase or ``S``).
3. Every tracked file exists and its bytes hash to the blob recorded at HEAD (``git ls-tree -r`` against
   ``git hash-object``); line-ending normalisation is accepted only where git's own filters for that path yield the blob.
4. No untracked or ignored importable file, untracked symlink or nested git repository exists anywhere in the tree.
   The tree is walked directly (symlinks not followed, nested ``.git`` directories included), because
   ``git ls-files --others`` lists an untracked directory holding its own ``.git`` as one opaque entry. Only ``*.pyc``
   files under ``__pycache__`` are tolerated: the adapter points ``sys.pycache_prefix`` at an empty private directory
   before importing, so bytecode inside the checkout is never read. Any other importable suffix there is refused.

This module has no import-time side effects and does not import BitRep.
"""

from __future__ import annotations

import importlib.machinery
import os
import subprocess
from pathlib import Path

_IMPORTABLE_SUFFIXES = (*importlib.machinery.all_suffixes(), ".pyw", ".pyd")


def _git(root: Path, *args: str, **kwargs) -> str:
    return subprocess.run(
        ["git", "--no-replace-objects", "-C", str(root), *args],
        check=True, text=True, capture_output=True, timeout=120, **kwargs,
    ).stdout


def checkout_problems(root: Path, pin: str) -> list[str]:
    """Return every reason the checkout is not exactly ``pin``; an empty list means it is."""
    root = Path(root).resolve()
    problems: list[str] = []
    head = _git(root, "rev-parse", "HEAD").strip()
    if head != pin:
        problems.append(f"HEAD {head} is not the pin")
    for line in _git(root, "ls-files", "-v", "-z").split("\0"):
        if line and (line[0].islower() or line[0] == "S"):
            problems.append(f"index flag hides modifications: {line[2:]}")
    tree: dict[str, tuple[str, str, str]] = {}
    for entry in _git(root, "ls-tree", "-r", "-z", head).split("\0"):
        if entry:
            meta, rel = entry.split("\t", 1)
            mode, kind, blob = meta.split()
            tree[rel] = (mode, kind, blob)
    on_disk: list[str] = []
    for rel, (mode, kind, blob) in sorted(tree.items()):
        path = root / rel
        if kind != "blob" or "\n" in rel:
            problems.append(f"cannot be compared with the revision: {rel}")
        elif mode == "120000":
            if not path.is_symlink() or _git(root, "hash-object", "--stdin", input=os.readlink(path)).strip() != blob:
                problems.append(f"content differs from the revision: {rel}")
        elif path.is_symlink() or not path.is_file():
            problems.append(f"content differs from the revision: {rel}")
        else:
            on_disk.append(rel)

    def hashes(paths: list[str], *flags: str) -> list[str]:
        if not paths:
            return []
        out = _git(root, "hash-object", *flags, "--stdin-paths", input="\n".join(paths) + "\n").split()
        if len(out) != len(paths):
            raise ValueError("hash count mismatch")
        return out

    raw = hashes(on_disk, "--no-filters")
    differing = [rel for rel, digest in zip(on_disk, raw) if tree[rel][2] != digest]
    for rel, digest in zip(differing, hashes(differing)):
        if tree[rel][2] != digest:
            problems.append(f"content differs from the revision: {rel}")
    problems.extend(_untracked_problems(root))
    return problems


def _untracked_problems(root: Path) -> list[str]:
    """Walk the whole tree (symlinks not followed, nested ``.git`` directories included) for untracked importables.

    ``git ls-files --others`` reports an untracked directory that holds its own ``.git`` as one opaque entry, so a
    nested repository named like a dependency would hide everything inside it. The walk is the authority instead.
    """
    tracked = {rel for rel in _git(root, "ls-files", "-z").split("\0") if rel}
    found: list[str] = []

    def fail(error: OSError) -> None:
        raise error

    for here, dirnames, filenames in os.walk(root, followlinks=False, onerror=fail):
        base = Path(here)
        relbase = base.relative_to(root)
        if relbase == Path("."):
            dirnames[:] = [d for d in dirnames if d != ".git"]
            filenames[:] = [f for f in filenames if f != ".git"]
        for name in sorted(dirnames + filenames):
            rel = (relbase / name).as_posix()
            if rel in tracked:
                continue
            path = base / name
            if path.is_symlink():
                found.append(f"untracked or ignored symlink: {rel}")
            elif name == ".git":
                found.append(f"untracked or ignored nested git repository: {relbase.as_posix()}")
            elif name in filenames and name.endswith(_IMPORTABLE_SUFFIXES):
                # Compiled bytecode in __pycache__ is never read (the adapter sets sys.pycache_prefix), so only
                # *.pyc is allowed there; any other importable suffix is refused even under __pycache__.
                if "__pycache__" in relbase.parts and name.endswith(".pyc"):
                    continue
                found.append(f"untracked or ignored importable file: {rel}")
    return found
