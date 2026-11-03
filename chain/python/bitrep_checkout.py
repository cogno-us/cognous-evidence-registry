"""Verification that a BitRep checkout is exactly the pinned commit, whatever ``git status`` says.

``git status`` trusts the index: a tracked file flagged skip-worktree or assume-unchanged can be edited and still look
clean, and ignored files are never listed. Because the adapter executes BitRep's verifier in process, the checkout is
therefore checked directly:

1. HEAD equals the pin (git replace refs are disabled so they cannot redirect the tree read).
2. No tracked file carries an assume-unchanged or skip-worktree flag (``git ls-files -v``: lowercase or ``S``).
3. Every tracked file exists and its raw on-disk bytes hash to the blob recorded at HEAD (``git ls-tree -r`` against a
   git blob hash computed in this process). No git filter is ever run and no normalisation is accepted: a CRLF-mutated
   checkout is refused, never "cleaned".
4. The index equals HEAD (``git diff --cached``), and "tracked" means present in the pinned tree, not in the index:
   a file added with ``git add`` but not committed is still refused.
5. No untracked or ignored importable file, untracked symlink or nested git repository exists anywhere in the tree.
   The tree is walked directly (symlinks not followed, nested ``.git`` directories included), because
   ``git ls-files --others`` lists an untracked directory holding its own ``.git`` as one opaque entry. Only ``*.pyc``
   files under ``__pycache__`` are tolerated: the adapter points ``sys.pycache_prefix`` at an empty private directory
   before importing, so bytecode inside the checkout is never read. Any other importable suffix there is refused.

Verifying a checkout is not enough to import from it (the working tree can change between check and import, and lazy
imports read the live directory), so ``materialize_pinned`` copies the authenticated blobs out of the Git object database
into a private directory and the adapter imports only that copy. The mutable checkout is never put on ``sys.path``.

Every git subprocess runs with a scrubbed environment and with repository-controlled configuration neutralised
(``GIT_CONFIG_NOSYSTEM``, ``GIT_CONFIG_GLOBAL``/``SYSTEM`` -> null device, no replace objects, no fsmonitor, no hooks, no
attributes file) and only with plumbing that applies no clean/smudge filter: ``rev-parse``, ``ls-files -v``, ``ls-tree``,
``cat-file`` and ``diff --cached --name-only``.

This module has no import-time side effects and does not import BitRep.
"""

from __future__ import annotations

import atexit
import hashlib
import importlib.machinery
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

_IMPORTABLE_SUFFIXES = (*importlib.machinery.all_suffixes(), ".pyw", ".pyd")


_HARDENED_CONFIG = (
    "core.fsmonitor=false", "core.hooksPath=" + os.devnull, "core.attributesFile=" + os.devnull,
    "core.untrackedCache=false", "core.sshCommand=false", "protocol.allow=never",
)
_KEEP_ENV = ("PATH", "SYSTEMROOT", "SystemDrive", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL")


def _git_env() -> dict[str, str]:
    """Scrubbed environment: nothing from the caller's GIT_* variables, no user/system configuration."""
    env = {k: os.environ[k] for k in _KEEP_ENV if k in os.environ}
    env.update(
        GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
        GIT_NO_REPLACE_OBJECTS="1", GIT_ATTR_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0",
        GIT_EXTERNAL_DIFF=os.devnull, GIT_PAGER="cat", GIT_ASKPASS=os.devnull,
    )
    return env


def _git_cmd(root: Path, *args: str) -> list[str]:
    flags = [x for key in _HARDENED_CONFIG for x in ("-c", key)]
    return ["git", "--no-replace-objects", "--no-pager", *flags, "-C", str(root), *args]


def _git(root: Path, *args: str, **kwargs) -> str:
    return subprocess.run(
        _git_cmd(root, *args), check=True, text=True, capture_output=True, timeout=120, env=_git_env(), **kwargs,
    ).stdout


def _git_bytes(root: Path, *args: str, input: bytes | None = None) -> bytes:
    return subprocess.run(
        _git_cmd(root, *args), check=True, capture_output=True, timeout=120, env=_git_env(), input=input,
    ).stdout


def _blob_digest(data: bytes, width: int) -> str:
    """Git blob object id of raw ``data`` (sha1 or sha256 object format, chosen by the id width)."""
    algorithm = hashlib.sha256 if width == 64 else hashlib.sha1
    return algorithm(b"blob %d\0" % len(data) + data).hexdigest()


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
            if not path.is_symlink() or _blob_digest(os.fsencode(os.readlink(path)), len(blob)) != blob:
                problems.append(f"content differs from the revision: {rel}")
        elif path.is_symlink() or not path.is_file():
            problems.append(f"content differs from the revision: {rel}")
        else:
            on_disk.append(rel)

    # Raw bytes only: no git filter (clean, smudge, eol, ident) is consulted, so a repository-controlled filter or
    # attribute can neither run nor make a different file look like the blob.
    for rel in on_disk:
        try:
            digest = _blob_digest(Path(root / rel).read_bytes(), len(tree[rel][2]))
        except OSError:
            digest = ""
        if tree[rel][2] != digest:
            problems.append(f"content differs from the revision: {rel}")
    # The tracked set is the pinned tree, not the index: ``git add evil.py`` must not make an uncommitted file look
    # tracked. The index itself must also equal HEAD (nothing staged, added, deleted or retyped).
    staged = [rel for rel in _git(root, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--name-only", "-z", head).split("\0") if rel]
    for rel in staged:
        problems.append(f"index differs from the revision, staged change: {rel}")
    problems.extend(_untracked_problems(root, set(tree)))
    return problems


def _untracked_problems(root: Path, tracked: set[str]) -> list[str]:
    """Walk the whole tree (symlinks not followed, nested ``.git`` directories included) for untracked importables.

    ``git ls-files --others`` reports an untracked directory that holds its own ``.git`` as one opaque entry, so a
    nested repository named like a dependency would hide everything inside it. The walk is the authority instead.
    ``tracked`` is the set of paths in the pinned tree (``git ls-tree -r``), never the index.
    """
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


_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_MATERIALIZED: list[Path] = []


def _cleanup() -> None:
    for path in _MATERIALIZED:
        for here, dirnames, _ in os.walk(path):
            for name in dirnames:
                try:
                    os.chmod(os.path.join(here, name), 0o700)
                except OSError:
                    pass
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
        shutil.rmtree(path, ignore_errors=True)


atexit.register(_cleanup)


def _safe_relative(rel: str) -> bool:
    parts = rel.split("/")
    return bool(rel) and not rel.startswith("/") and "\\" not in rel and "\0" not in rel and all(
        p not in ("", ".", "..") and p.lower() != ".git" and ":" not in p for p in parts
    )


def materialize_pinned(root: Path, pin: str, dest: Path | None = None) -> Path:
    """Copy the files of commit ``pin`` out of ``root``'s object database into a private directory and return it.

    Only Git objects are read (``cat-file --batch``, never the working tree, index or any filter), and every blob is
    re-hashed here against the id recorded in the pinned tree, so the returned directory holds exactly the authenticated
    bytes. The directory is private (0700), made read-only, and removed at interpreter exit. Untracked files, index
    flags, ``.gitattributes`` and the state of the checkout are irrelevant to it. Raises ``ValueError`` on anything that
    cannot be reproduced exactly (non-commit pin, submodule, unsafe path, case-colliding names, escaping symlink).
    """
    root = Path(root).resolve()
    if not _OBJECT_ID.match(pin):
        raise ValueError("pin must be a full lowercase object id")
    if _git(root, "cat-file", "-t", pin).strip() != "commit":
        raise ValueError("pin is not a commit")
    entries: list[tuple[str, str, str, str]] = []
    for entry in _git(root, "ls-tree", "-r", "-z", "--full-tree", pin).split("\0"):
        if entry:
            meta, rel = entry.split("\t", 1)
            mode, kind, blob = meta.split()
            entries.append((mode, kind, blob, rel))
    seen: set[str] = set()
    for mode, kind, blob, rel in entries:
        if kind != "blob" or mode not in ("100644", "100755", "120000") or not _safe_relative(rel):
            raise ValueError(f"cannot materialize pinned entry: {rel!r}")
        folded = rel.casefold()
        if folded in seen:
            raise ValueError(f"case-colliding pinned path: {rel!r}")
        seen.add(folded)
    blobs = sorted({blob for _, _, blob, _ in entries})
    data: dict[str, bytes] = {}
    if blobs:
        stream = _git_bytes(root, "cat-file", "--batch", input=("\n".join(blobs) + "\n").encode())
        pos = 0
        for blob in blobs:
            end = stream.index(b"\n", pos)
            header = stream[pos:end].split()
            if len(header) != 3 or header[0].decode() != blob or header[1] != b"blob":
                raise ValueError(f"object missing or not a blob: {blob}")
            size = int(header[2])
            payload = stream[end + 1:end + 1 + size]
            if len(payload) != size or _blob_digest(payload, len(blob)) != blob:
                raise ValueError(f"object bytes do not match their id: {blob}")
            data[blob] = payload
            pos = end + 1 + size + 1
    out = Path(dest) if dest is not None else Path(tempfile.mkdtemp(prefix="bitrep-pinned-"))
    out.mkdir(mode=0o700, exist_ok=True)
    out = out.resolve()
    if dest is None:
        _MATERIALIZED.append(out)
    for mode, _, blob, rel in entries:
        target = out.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        if mode == "120000":
            link = os.fsdecode(data[blob])
            resolved = os.path.normpath(os.path.join(str(target.parent), link))
            if os.path.isabs(link) or not (resolved == str(out) or resolved.startswith(str(out) + os.sep)):
                raise ValueError(f"symlink escapes the pinned tree: {rel!r}")
            os.symlink(link, target)
        else:
            target.write_bytes(data[blob])
            os.chmod(target, 0o555 if mode == "100755" else 0o444)
    for here, dirnames, _ in os.walk(out, topdown=False):
        for name in dirnames:
            os.chmod(os.path.join(here, name), 0o555)
    os.chmod(out, 0o555)
    return out
