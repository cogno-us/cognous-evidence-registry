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

The checkout's own object database is never asked what the pinned commit or tree *is*, and (R1-B3) git is never asked
to read it at all: ``TrustedObjects`` (committed in ``bitrep_trusted_objects.py``) carry the expected commit id, root tree
id and per-path blob ids, and a bounded in-process reader (loose zlib objects and pack/idx v2, see "Trusted object
reader" below) re-hashes every object against an id that comes from those anchors or from an already verified parent
object. No git process, git configuration (partial clone, promisor, remote or protocol settings), alternate, refs,
tags, HEAD, replace objects, grafts or shallow files ever takes part. The anchors are source-authentication anchors,
not operational authority.

Verifying a checkout is not enough to import from it (the working tree can change between check and import, and lazy
imports read the live directory), so ``materialize_pinned`` copies the authenticated blobs out of the Git object database
into a private directory and the adapter imports only that copy. The mutable checkout is never put on ``sys.path``.

``checkout_problems`` (the optional ``git status``-style audit of a working tree) still uses git, with a scrubbed
environment and repository-controlled configuration neutralised, and only with plumbing that applies no filter. It is
NOT on the import path: ``materialize_pinned`` and the adapter's ``load_bitrep`` never call it or start any git process.

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
import struct
import subprocess
import tempfile
import zlib
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


# ---------------------------------------------------------------------------------------------------------------------
# Trusted object reader (R1-B3, csf_518b8599e95b7919b55fe371 / csf_d7e271587bb3dc0dec7ac96f)
#
# No git process is started anywhere below. ``<root>/.git/objects`` is treated as untrusted bytes: loose objects
# (zlib) and pack/idx v2 files are parsed in this process by a deliberately minimal reader that only looks up the
# specific object ids it is asked for. Every candidate is re-hashed (``sha1("<type> <size>\0" + raw)``) against the id
# that came from the trusted anchors or from an already authenticated parent object; nothing else decides acceptance.
# Never consulted: configuration (local, global, system, ``extensions.*``, ``remote.*``, ``protocol.*``), promisor or
# partial-clone settings, ``objects/info/alternates``, ``GIT_*`` variables, refs, HEAD, tags, packed-refs,
# ``refs/replace``, grafts, shallow files, ``.git`` files (gitdir indirection), hooks or attributes. A missing object is
# simply an error: there is nothing to fetch lazily.
#
# Bounds are sized from the known use case (the pinned BitRep tree: 71 files, largest blob ~34 KiB, ~440 KiB of blobs,
# 85 distinct objects, delta depth <= 1 in the reference clone) with headroom, not from Git's own limits.
# Unsupported on purpose: sha256 repositories, pack index v1, multi-pack-index, commit-graph, reverse indexes, cruft
# packs, promisor (``.promisor``) packs, tag objects, objects larger than ``MAX_OBJECT_SIZE``, delta chains deeper than
# ``MAX_DELTA_DEPTH``, REF_DELTA bases that are not in the same pack (thin packs are never stored by git), ``.git``
# gitfiles, bare layouts.
# ---------------------------------------------------------------------------------------------------------------------

MAX_OBJECT_SIZE = 256 * 1024           # declared size of any one object (and of any delta stream or delta result)
MAX_COMPRESSED = 320 * 1024            # compressed bytes read for any one object stream
MAX_TOTAL_BYTES = 4 * 1024 * 1024      # sum of the sizes of all authenticated objects (known use case: ~0.45 MiB)
MAX_WORK_BYTES = 16 * 1024 * 1024      # all inflated bytes incl. delta streams and intermediate bases
MAX_OBJECTS = 512                      # distinct authenticated objects (known use case: 85)
MAX_TREE_ENTRIES = 512                 # entries in one tree object
MAX_TOTAL_TREE_ENTRIES = 2048          # entries over all trees (known use case: 71 files + directories)
MAX_TREES = 128                        # tree objects (known use case: 15)
MAX_DELTA_DEPTH = 50                   # git's own default pack.depth
MAX_PACKS = 32
MAX_PACK_OBJECTS = 200_000             # objects per pack index
_CHUNK = 8192

_SHA1_ID = re.compile(r"^[0-9a-f]{40}$")
_TYPES = {1: "commit", 2: "tree", 3: "blob"}
_OPEN_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)


def _open_regular(path: str) -> tuple[int, int]:
    """Open an existing regular file without following a final symlink or blocking on a FIFO; return (fd, size)."""
    fd = os.open(path, _OPEN_FLAGS)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"not a regular file: {path}")
        return fd, info.st_size
    except BaseException:
        os.close(fd)
        raise


def _pread_exact(fd: int, size: int, offset: int, length: int) -> bytes:
    if offset < 0 or length < 0 or offset + length > size:
        raise ValueError("read outside the file")
    data = os.pread(fd, length, offset)
    if len(data) != length:
        raise ValueError("short read")
    return data


class _Inflater:
    """Inflate one zlib stream from ``read(n)`` chunks with hard caps on input and output (a bomb is refused early)."""

    def __init__(self, read, expected: int, max_input: int):
        self.read, self.expected, self.max_input = read, expected, max_input

    def run(self) -> bytes:
        engine, out, fed, pending = zlib.decompressobj(), bytearray(), 0, b""
        try:
            while not engine.eof:
                if not pending:
                    pending = self.read(_CHUNK)
                    fed += len(pending)
                    if not pending:
                        raise ValueError("truncated zlib stream")
                    if fed > self.max_input:
                        raise ValueError("compressed object exceeds the input bound")
                before = len(pending)
                out += engine.decompress(pending, self.expected - len(out) + 1)
                if len(out) > self.expected:
                    raise ValueError("object inflates beyond its declared size")
                pending = engine.unconsumed_tail
                if len(pending) == before and not engine.eof:
                    raise ValueError("zlib stream makes no progress")
        except zlib.error as exc:
            raise ValueError(f"corrupt zlib stream: {exc}") from exc
        if len(out) != self.expected:
            raise ValueError("object size does not match its declared size")
        return bytes(out)


def _apply_delta(base: bytes, delta: bytes) -> bytes:
    """Apply a git delta to ``base`` with every offset, length and the result size checked."""
    pos = 0

    def varint() -> int:
        nonlocal pos
        value = shift = 0
        while True:
            if pos >= len(delta) or shift > 28:
                raise ValueError("malformed delta header")
            byte = delta[pos]
            pos += 1
            value |= (byte & 0x7F) << shift
            shift += 7
            if not byte & 0x80:
                return value

    if varint() != len(base):
        raise ValueError("delta base size mismatch")
    want = varint()
    if want > MAX_OBJECT_SIZE:
        raise ValueError("delta result exceeds the object size bound")
    out = bytearray()
    while pos < len(delta):
        op = delta[pos]
        pos += 1
        if op & 0x80:
            offset = length = 0
            for bit in range(4):
                if op & (1 << bit):
                    if pos >= len(delta):
                        raise ValueError("truncated delta copy")
                    offset |= delta[pos] << (8 * bit)
                    pos += 1
            for bit in range(3):
                if op & (0x10 << bit):
                    if pos >= len(delta):
                        raise ValueError("truncated delta copy")
                    length |= delta[pos] << (8 * bit)
                    pos += 1
            length = length or 0x10000
            if offset + length > len(base):
                raise ValueError("delta copy outside its base")
            out += base[offset:offset + length]
        elif op:
            if pos + op > len(delta):
                raise ValueError("truncated delta insert")
            out += delta[pos:pos + op]
            pos += op
        else:
            raise ValueError("reserved delta opcode")
        if len(out) > want:
            raise ValueError("delta produces more than its declared result")
    if len(out) != want:
        raise ValueError("delta result size mismatch")
    return bytes(out)


class _Pack:
    """One ``pack-<sha1>.idx`` / ``.pack`` pair, read lazily and only for explicit object-id lookups."""

    def __init__(self, store: "_ObjectStore", idx_path: str, pack_path: str):
        self.store = store
        self.idx_fd = self.pack_fd = -1
        try:
            self.idx_fd, self.idx_size = _open_regular(idx_path)
            self.pack_fd, self.pack_size = _open_regular(pack_path)
            head = _pread_exact(self.idx_fd, self.idx_size, 0, 8) if self.idx_size >= 8 + 1024 + 40 else b""
            if head != b"\xfftOc\0\0\0\2":
                raise ValueError("unsupported or malformed pack index (version 2 required)")
            fanout = struct.unpack(">256I", _pread_exact(self.idx_fd, self.idx_size, 8, 1024))
            if any(b < a for a, b in zip(fanout, fanout[1:])):
                raise ValueError("pack index fanout is not monotonic")
            self.count = fanout[255]
            if self.count > MAX_PACK_OBJECTS:
                raise ValueError("pack index declares too many objects")
            self.fanout = fanout
            self.names = 8 + 1024
            self.crcs = self.names + 20 * self.count
            self.offsets = self.crcs + 4 * self.count
            self.large = self.offsets + 4 * self.count
            spare = self.idx_size - self.large - 40
            if spare < 0 or spare % 8 or spare > 8 * self.count:
                raise ValueError("pack index size is inconsistent with its object count")
            self.large_count = spare // 8
            if self.pack_size < 12 + 20:
                raise ValueError("pack file too small")
            magic, version, count = struct.unpack(">4sII", _pread_exact(self.pack_fd, self.pack_size, 0, 12))
            if magic != b"PACK" or version not in (2, 3) or count != self.count:
                raise ValueError("pack header does not match its index")
            self.end = self.pack_size - 20
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        for fd in (self.idx_fd, self.pack_fd):
            if fd >= 0:
                os.close(fd)
        self.idx_fd = self.pack_fd = -1

    def find(self, oid: str) -> int | None:
        """Pack offset of ``oid`` or None (binary search over the sorted names; every probe is a bounded pread)."""
        want = bytes.fromhex(oid)
        first = want[0]
        lo, hi = (self.fanout[first - 1] if first else 0), self.fanout[first]
        while lo < hi:
            mid = (lo + hi) // 2
            name = _pread_exact(self.idx_fd, self.idx_size, self.names + 20 * mid, 20)
            if name[0] != first:
                raise ValueError("pack index names are outside their fanout bucket")
            if name == want:
                return self._offset(mid)
            if name < want:
                lo = mid + 1
            else:
                hi = mid
        return None

    def _offset(self, index: int) -> int:
        (value,) = struct.unpack(">I", _pread_exact(self.idx_fd, self.idx_size, self.offsets + 4 * index, 4))
        if value & 0x80000000:
            slot = value & 0x7FFFFFFF
            if slot >= self.large_count:
                raise ValueError("pack index large offset is outside its table")
            (value,) = struct.unpack(">Q", _pread_exact(self.idx_fd, self.idx_size, self.large + 8 * slot, 8))
        if not 12 <= value < self.end:
            raise ValueError("pack index offset is outside the pack")
        return value

    def _stream(self, pos: int, expected: int) -> bytes:
        if expected > MAX_OBJECT_SIZE:
            raise ValueError("object exceeds the size bound")
        self.store.charge_work(expected)
        cursor = [pos]

        def read(n: int) -> bytes:
            n = min(n, self.end - cursor[0])
            if n <= 0:
                return b""
            data = _pread_exact(self.pack_fd, self.pack_size, cursor[0], n)
            cursor[0] += n
            return data

        return _Inflater(read, expected, MAX_COMPRESSED).run()

    def read(self, offset: int) -> tuple[str, bytes]:
        """Resolve the object at ``offset`` (OFS_DELTA and REF_DELTA inside this pack) to ``(type, raw bytes)``."""
        deltas: list[bytes] = []
        seen: set[int] = set()
        while True:
            if offset in seen or len(deltas) > MAX_DELTA_DEPTH:
                raise ValueError("delta chain is cyclic or too deep")
            seen.add(offset)
            head = _pread_exact(self.pack_fd, self.pack_size, offset, min(32, self.end - offset))
            byte, kind, size, shift, used = head[0], (head[0] >> 4) & 7, head[0] & 15, 4, 1
            while byte & 0x80:
                if used >= len(head) or shift > 28:
                    raise ValueError("malformed pack object header")
                byte = head[used]
                used += 1
                size |= (byte & 0x7F) << shift
                shift += 7
            if size > MAX_OBJECT_SIZE:
                raise ValueError("pack object declares a size above the bound")
            if kind in _TYPES:
                data = self._stream(offset + used, size)
                break
            if kind == 6:
                if used >= len(head):
                    raise ValueError("malformed OFS_DELTA header")
                byte = head[used]
                used += 1
                rel = byte & 0x7F
                while byte & 0x80:
                    if used >= len(head) or used > 12:
                        raise ValueError("malformed OFS_DELTA offset")
                    byte = head[used]
                    used += 1
                    rel = ((rel + 1) << 7) | (byte & 0x7F)
                base = offset - rel
                if rel <= 0 or base < 12:
                    raise ValueError("OFS_DELTA base is outside the pack")
            elif kind == 7:
                if used + 20 > len(head):
                    raise ValueError("malformed REF_DELTA header")
                found = self.find(head[used:used + 20].hex())
                used += 20
                if found is None:
                    raise ValueError("REF_DELTA base is not in the same pack")
                base = found
            else:
                raise ValueError(f"unsupported pack object type {kind}")
            deltas.append(self._stream(offset + used, size))
            offset = base
        kind_name = _TYPES[kind]
        for delta in reversed(deltas):
            data = _apply_delta(data, delta)
            self.store.charge_work(len(data))
        return kind_name, data


class _ObjectStore:
    """Bounded, git-free reader over ``<root>/.git/objects`` that returns only bytes hashing to the requested id."""

    def __init__(self, root: Path):
        self.objects = os.path.join(os.fspath(root), ".git", "objects")
        self.work = self.total = 0
        self.cache: dict[tuple[str, str], bytes] = {}
        self._packs: list[_Pack] | None = None

    def __enter__(self) -> "_ObjectStore":
        return self

    def __exit__(self, *exc) -> None:
        for pack in self._packs or []:
            pack.close()
        self._packs = None

    def charge_work(self, n: int) -> None:
        self.work += n
        if self.work > MAX_WORK_BYTES:
            raise ValueError("trusted object reads exceed the work bound")

    def packs(self) -> list[_Pack]:
        if self._packs is None:
            self._packs = []
            directory = os.path.join(self.objects, "pack")
            try:
                names = sorted(e.name for e in os.scandir(directory) if re.fullmatch(r"pack-[0-9a-f]{40}\.idx", e.name))
            except OSError:
                names = []
            if len(names) > MAX_PACKS:
                raise ValueError("too many pack files")
            for name in names:
                try:
                    self._packs.append(_Pack(self, os.path.join(directory, name), os.path.join(directory, name[:-4] + ".pack")))
                except (ValueError, OSError):
                    continue  # an unusable pack is skipped; the object is then missing unless another source authenticates it
        return self._packs

    def _loose(self, oid: str) -> tuple[str, bytes] | None:
        try:
            fd, size = _open_regular(os.path.join(self.objects, oid[:2], oid[2:]))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            raise ValueError("loose object is unreadable")
        try:
            if size > MAX_COMPRESSED:
                raise ValueError("loose object exceeds the compressed input bound")
            raw = os.pread(fd, MAX_COMPRESSED + 1, 0)
        finally:
            os.close(fd)
        # Inflate with a hard output cap, then read the header; a bomb never buffers more than the cap.
        limit = MAX_OBJECT_SIZE + 32
        engine = zlib.decompressobj()
        try:
            data = engine.decompress(raw, limit + 1)
        except zlib.error as exc:
            raise ValueError(f"corrupt loose object: {exc}") from exc
        if len(data) > limit or not engine.eof or engine.unused_data:
            raise ValueError("loose object is truncated, oversized or has trailing data")
        nul = data.find(b"\0", 0, 32)
        head = data[:nul].split(b" ") if nul > 0 else []
        if len(head) != 2 or not head[1].isdigit() or len(head[1]) > 7 or head[1] != b"%d" % int(head[1]):
            raise ValueError("malformed loose object header")
        if int(head[1]) > MAX_OBJECT_SIZE or int(head[1]) != len(data) - nul - 1:
            raise ValueError("loose object size is out of bounds or does not match its header")
        self.charge_work(len(data))
        return head[0].decode("ascii", "replace"), data[nul + 1:]

    def read(self, oid: str, kind: str) -> bytes:
        """Raw bytes of the ``kind`` object ``oid``; accepted only if ``sha1("<kind> <len>\\0" + bytes) == oid``."""
        if not _SHA1_ID.match(oid):
            raise ValueError(f"not a full lowercase sha1 object id: {oid!r}")
        if kind not in ("commit", "tree", "blob"):
            raise ValueError(f"object type not allowed: {kind}")
        if (kind, oid) in self.cache:
            return self.cache[(kind, oid)]
        if len(self.cache) >= MAX_OBJECTS:
            raise ValueError("too many objects")
        failures: list[str] = []

        def candidates():
            try:
                found = self._loose(oid)
            except ValueError as exc:
                failures.append(str(exc))
                found = None
            if found:
                yield found
            for pack in self.packs():
                try:
                    offset = pack.find(oid)
                    if offset is not None:
                        yield pack.read(offset)
                except ValueError as exc:
                    failures.append(str(exc))

        for actual, payload in candidates():
            if actual == kind and hashlib.sha1(actual.encode() + b" %d\0" % len(payload) + payload).hexdigest() == oid:
                if self.total + len(payload) > MAX_TOTAL_BYTES:
                    raise ValueError("authenticated objects exceed the total byte bound")
                self.total += len(payload)
                self.cache[(kind, oid)] = payload
                return payload
            failures.append(f"candidate is not the {kind} {oid}")
        raise ValueError(f"object missing or not authentic as a {kind}: {oid}" + (f" ({failures[0]})" if failures else ""))


def verify_commit(root: Path, commit: str, *, _store: "_ObjectStore | None" = None) -> str:
    """Hash the raw commit object against ``commit`` and return the root tree id it names (verified, not resolved)."""
    if _store is None:
        with _ObjectStore(Path(root)) as store:
            return verify_commit(root, commit, _store=store)
    payload = _store.read(commit, "commit")
    first = payload.split(b"\n", 1)[0].decode("ascii", "replace")
    parts = first.split(" ")
    if len(parts) != 2 or parts[0] != "tree" or not _SHA1_ID.match(parts[1]):
        raise ValueError("commit object does not start with a tree line")
    return parts[1]


def verified_tree_entries(root: Path, tree: str, *, _store: "_ObjectStore | None" = None) -> list[tuple[str, str, str]]:
    """Recompute every tree object hash in-process from ``tree`` down and return flat ``(mode, path, blob)`` entries."""
    if _store is None:
        with _ObjectStore(Path(root)) as store:
            return verified_tree_entries(root, tree, _store=store)
    flat: list[tuple[str, str, str]] = []
    pending: list[tuple[str, str]] = [("", tree)]
    seen: set[str] = set()
    total_entries = 0
    while pending:
        prefix, oid = pending.pop()
        if oid in seen:
            raise ValueError("tree object referenced twice")
        seen.add(oid)
        if len(seen) > MAX_TREES:
            raise ValueError("tree is too large")
        data, pos, entries = _store.read(oid, "tree"), 0, 0
        while pos < len(data):
            entries += 1
            total_entries += 1
            if entries > MAX_TREE_ENTRIES or total_entries > MAX_TOTAL_TREE_ENTRIES:
                raise ValueError("tree has too many entries")
            sp = data.index(b" ", pos)
            nul = data.index(b"\0", sp)
            mode, name = data[pos:sp].decode("ascii"), os.fsdecode(data[sp + 1:nul])
            child = data[nul + 1:nul + 21].hex()
            if len(child) != 40:
                raise ValueError("truncated tree entry")
            pos = nul + 21
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
    manifest id. No git process is started; refs, tags, HEAD, replace objects, alternates, grafts, shallow files and
    configuration never take part (see the reader notes above).
    """
    root = Path(root).resolve()
    for oid in (anchors.commit, anchors.tree):
        if not _SHA1_ID.match(oid):
            raise ValueError("trusted anchors must be full lowercase sha1 object ids")
    with _ObjectStore(root) as store:
        if verify_commit(root, anchors.commit, _store=store) != anchors.tree:
            raise ValueError("commit does not name the trusted tree")
        entries = verified_tree_entries(root, anchors.tree, _store=store)
        if entries != sorted(anchors.files, key=lambda e: e[1]) or len(set(e[1] for e in entries)) != len(entries):
            raise ValueError("tree contents differ from the trusted manifest")
        blobs = {blob: store.read(blob, "blob") for _, _, blob in entries}
    return entries, blobs


def materialize_pinned(root: Path, pin: str, dest: Path | None = None, *, anchors: TrustedObjects) -> Path:
    """Copy the files of the anchored commit out of ``root``'s object database into a private directory.

    ``anchors`` (trusted code, not the checkout) define the expected commit, tree and per-path blob ids; ``root`` only
    supplies bytes, each verified by in-process hashing (see ``verify_anchored``). ``pin`` must equal ``anchors.commit``.
    Only Git objects named by those ids are read, in-process (never the working tree, index, refs, configuration or any
    git process). The directory is private (0700), made read-only, and removed at interpreter exit. Raises ``ValueError`` on
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
