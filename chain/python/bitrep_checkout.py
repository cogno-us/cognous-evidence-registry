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

The checkout's own object database is never asked what the pinned commit or tree *is*: ``TrustedObjects`` (committed in
``bitrep_trusted_objects.py``) carry the expected commit id, root tree id and per-path blob ids, and every object read
is re-hashed in-process against an id that comes from those anchors or from an already verified parent object. Refs,
tags, HEAD, replace objects, alternates, grafts and shallow files never take part. The anchors are source-authentication
anchors, not operational authority.

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
from typing import NamedTuple

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


class TrustedObjects(NamedTuple):
    """Expected Git object identities, supplied by trusted code (``bitrep_trusted_objects.py``), never by a checkout.

    ``commit`` and ``tree`` are the pinned commit and root tree ids; ``files`` is the complete expected manifest of
    ``(mode, path, blob id)`` entries of that tree. They are source-authentication anchors only.
    """

    commit: str
    tree: str
    files: tuple[tuple[str, str, str], ...]


def _object_hash(kind: bytes, payload: bytes, width: int) -> str:
    algorithm = hashlib.sha256 if width == 64 else hashlib.sha1
    return algorithm(kind + b" %d\0" % len(payload) + payload).hexdigest()


def _read_objects(root: Path, kind: str, ids: list[str]) -> dict[str, bytes]:
    """Read raw objects by full id and verify each in-process against the id that was asked for.

    The object database (or an alternate, replace ref or ``GIT_*`` redirection it may carry) only supplies bytes: an
    object is accepted solely when ``"<kind> <len>\\0" + bytes`` hashes to exactly the id requested here, and the id
    always comes from trusted anchors or from an already verified parent object.
    """
    ids = sorted(set(ids))
    for oid in ids:
        if not _OBJECT_ID.match(oid):
            raise ValueError(f"not a full lowercase object id: {oid!r}")
    out: dict[str, bytes] = {}
    if not ids:
        return out
    stream = _git_bytes(root, "cat-file", "--batch", input=("\n".join(ids) + "\n").encode())
    pos = 0
    for oid in ids:
        end = stream.index(b"\n", pos)
        header = stream[pos:end].split()
        if len(header) != 3 or header[0].decode() != oid or header[1].decode() != kind:
            raise ValueError(f"object missing or not a {kind}: {oid}")
        size = int(header[2])
        payload = stream[end + 1:end + 1 + size]
        if len(payload) != size or _object_hash(kind.encode(), payload, len(oid)) != oid:
            raise ValueError(f"object bytes do not match their id: {oid}")
        out[oid] = payload
        pos = end + 1 + size + 1
    return out


def verify_commit(root: Path, commit: str) -> str:
    """Hash the raw commit object against ``commit`` and return the root tree id it names (verified, not resolved)."""
    payload = _read_objects(root, "commit", [commit])[commit]
    first = payload.split(b"\n", 1)[0].decode("ascii", "replace")
    parts = first.split(" ")
    if len(parts) != 2 or parts[0] != "tree" or not _OBJECT_ID.match(parts[1]) or len(parts[1]) != len(commit):
        raise ValueError("commit object does not start with a tree line")
    return parts[1]


def verified_tree_entries(root: Path, tree: str) -> list[tuple[str, str, str]]:
    """Recompute every tree object hash in-process from ``tree`` down and return flat ``(mode, path, blob)`` entries."""
    width = len(tree)
    flat: list[tuple[str, str, str]] = []
    pending: list[tuple[str, str]] = [("", tree)]
    seen: set[str] = set()
    while pending:
        level = pending
        pending = []
        raw = _read_objects(root, "tree", [oid for _, oid in level])
        for prefix, oid in level:
            seen.add(oid)
            if len(seen) > 10000:
                raise ValueError("tree is too large")
            data, pos = raw[oid], 0
            while pos < len(data):
                sp = data.index(b" ", pos)
                nul = data.index(b"\0", sp)
                mode, name = data[pos:sp].decode("ascii"), os.fsdecode(data[sp + 1:nul])
                child = data[nul + 1:nul + 1 + width // 2].hex()
                if len(child) != width:
                    raise ValueError("truncated tree entry")
                pos = nul + 1 + width // 2
                rel = prefix + name
                if not name or "/" in name:
                    raise ValueError(f"unsafe tree entry name: {rel!r}")
                if mode == "40000":
                    pending.append((rel + "/", child))
                elif mode in ("100644", "100755", "120000"):
                    flat.append((mode, rel, child))
                else:
                    raise ValueError(f"cannot materialize pinned entry: {rel!r} (mode {mode})")
    return sorted(flat, key=lambda e: e[1])


def verify_anchored(root: Path, anchors: TrustedObjects) -> tuple[list[tuple[str, str, str]], dict[str, bytes]]:
    """Authenticate commit, tree, manifest and every blob against ``anchors``; return entries and blob bytes.

    Order: raw commit hash == anchors.commit; the commit's tree line == anchors.tree; every tree object re-hashed from
    anchors.tree down; the resulting (mode, path, blob) set == anchors.files exactly; each blob re-hashed against its
    manifest id. Refs, tags, HEAD, replace objects, alternates, grafts and shallow files never take part.
    """
    root = Path(root).resolve()
    for oid in (anchors.commit, anchors.tree):
        if not _OBJECT_ID.match(oid):
            raise ValueError("trusted anchors must be full lowercase object ids")
    if verify_commit(root, anchors.commit) != anchors.tree:
        raise ValueError("commit does not name the trusted tree")
    entries = verified_tree_entries(root, anchors.tree)
    if entries != sorted(anchors.files, key=lambda e: e[1]) or len(set(e[1] for e in entries)) != len(entries):
        raise ValueError("tree contents differ from the trusted manifest")
    blobs = _read_objects(root, "blob", [blob for _, _, blob in entries])
    return entries, blobs


def materialize_pinned(root: Path, pin: str, dest: Path | None = None, *, anchors: TrustedObjects) -> Path:
    """Copy the files of the anchored commit out of ``root``'s object database into a private directory.

    ``anchors`` (trusted code, not the checkout) define the expected commit, tree and per-path blob ids; ``root`` only
    supplies bytes, each verified by in-process hashing (see ``verify_anchored``). ``pin`` must equal ``anchors.commit``.
    Only Git objects named by those ids are read (``cat-file --batch``, never the working tree, index, refs or any
    filter). The directory is private (0700), made read-only, and removed at interpreter exit. Raises ``ValueError`` on
    anything that cannot be reproduced exactly (identity mismatch, submodule, unsafe path, case-colliding names,
    escaping symlink).
    """
    root = Path(root).resolve()
    if pin != anchors.commit:
        raise ValueError("pin is not the trusted anchor commit")
    verified, data_by_blob = verify_anchored(root, anchors)
    entries = [(mode, "blob", blob, rel) for mode, rel, blob in verified]
    seen: set[str] = set()
    for mode, kind, blob, rel in entries:
        if not _safe_relative(rel):
            raise ValueError(f"cannot materialize pinned entry: {rel!r}")
        folded = rel.casefold()
        if folded in seen:
            raise ValueError(f"case-colliding pinned path: {rel!r}")
        seen.add(folded)
    data = data_by_blob
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
