"""R1-B2: the expected BitRep commit, tree and blob ids are trusted anchors, never read from the checkout (csf_2549122f435d297f245f3c12).

Hermetic: throwaway git repositories play both the genuine source and the attacker's object database. The attacker
controls everything under ``.git`` (loose objects, refs, tags, replace refs, alternates) and the process environment's
``GIT_*`` variables; the anchors come from a separate, trusted derivation of the genuine repository.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
import zlib
from pathlib import Path

import pytest

from test_bitrep_checkout import MODULE, checkout, git
from test_r1b_source_verification import ADAPTER, STUBS, anchors_for, run_adapter

PYDIR = MODULE.parent
KNOWN_GOOD = Path(os.environ.get("BITREP_KNOWN_GOOD", "/home/claude/p0/src/cognous-evidence-attestation"))
PRODUCTION_PIN = "981036c315856c71207984797b0c4e48d3b3921d"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name + "_under_test", PYDIR / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_repo(root: Path, files: dict[str, str]) -> str:
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "c")
    return git(root, "rev-parse", "HEAD").strip()


def write_loose(root: Path, oid: str, kind: str, payload: bytes) -> None:
    """Store ``payload`` under the path of ``oid`` whatever its real hash is (the attacker owns the object database)."""
    path = root / ".git" / "objects" / oid[:2] / oid[2:]
    if path.exists():
        path.chmod(0o644)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zlib.compress(kind.encode() + b" %d\0" % len(payload) + payload))


def forge_pack(root: Path, objects: dict[str, tuple[str, bytes]]) -> None:
    """Add a pack whose index claims ``oid`` for attacker bytes. Git does not re-hash packed objects on ordinary reads, so
    this is how a hostile object database redefines what a genuine id means (loose forgeries are caught by git itself)."""
    import struct
    kinds = {"commit": 1, "tree": 2, "blob": 3}
    body, entries = b"PACK" + struct.pack(">II", 2, len(objects)), []
    for oid, (kind, payload) in sorted(objects.items()):
        offset, size = len(body), len(payload)
        head = bytearray([(kinds[kind] << 4) | (size & 15) | (0x80 if size >> 4 else 0)])
        size >>= 4
        while size:
            head.append((size & 0x7F) | (0x80 if size >> 7 else 0))
            size >>= 7
        packed = bytes(head) + zlib.compress(payload)
        entries.append((bytes.fromhex(oid), zlib.crc32(packed), offset))
        body += packed
        loose = root / ".git" / "objects" / oid[:2] / oid[2:]
        if loose.exists():
            loose.chmod(0o644)
            loose.unlink()
    trailer = hashlib.sha1(body).digest()
    fan, ids = [0] * 256, [e[0] for e in entries]
    for i in ids:
        fan[i[0]] += 1
    total, fanout = 0, b""
    for count in fan:
        total += count
        fanout += struct.pack(">I", total)
    idx = b"\xfftOc" + struct.pack(">I", 2) + fanout + b"".join(ids) + b"".join(struct.pack(">I", e[1]) for e in entries)
    idx += b"".join(struct.pack(">I", e[2]) for e in entries) + trailer
    idx += hashlib.sha1(idx).digest()
    pack_dir = root / ".git" / "objects" / "pack"
    pack_dir.mkdir(exist_ok=True)
    (pack_dir / f"pack-{trailer.hex()}.pack").write_bytes(body + trailer)
    (pack_dir / f"pack-{trailer.hex()}.idx").write_bytes(idx)


def raw(root: Path, oid: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), "cat-file", "-p", oid], check=True, capture_output=True).stdout


def new_object(root: Path, kind: str, data: bytes) -> str:
    return subprocess.run(["git", "-C", str(root), "hash-object", "-w", "-t", kind, "--stdin"], input=data, check=True,
                          capture_output=True).stdout.decode().strip()


@pytest.fixture()
def good(tmp_path):
    """Genuine repository, its pinned commit and the trusted anchors derived from it."""
    root = tmp_path / "good"
    root.mkdir()
    pin = make_repo(root, STUBS)
    return root, pin, anchors_for(root, pin)


def attacker_commit(root: Path, evil_text: str = "VALUE = 'EVIL'\n") -> tuple[str, str, str]:
    """Internally consistent malicious blob/tree/commit inside ``root``'s object database: returns (commit, tree, blob)."""
    files = dict(STUBS, **{"models/lazy_mod.py": evil_text})
    blob = new_object(root, "blob", evil_text.encode())
    tree_lines = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "HEAD"], check=True, capture_output=True, text=True).stdout
    entries = []
    for line in tree_lines.splitlines():
        meta, rel = line.split("\t")
        mode, _, oid = meta.split()
        entries.append(f"{mode} blob {blob if rel == 'models/lazy_mod.py' else oid}\t{rel}")
    assert files  # documentation of intent
    # flat mktree needs per-directory trees: build the index and write a tree from it
    env = {**os.environ, "GIT_INDEX_FILE": str(root / ".git" / "evil-index")}
    subprocess.run(["git", "-C", str(root), "read-tree", "HEAD"], check=True, env=env)
    subprocess.run(["git", "-C", str(root), "update-index", "--cacheinfo", f"100644,{blob},models/lazy_mod.py"], check=True, env=env)
    tree = subprocess.run(["git", "-C", str(root), "write-tree"], check=True, capture_output=True, text=True, env=env).stdout.strip()
    commit = subprocess.run(["git", "-C", str(root), "commit-tree", tree, "-m", "evil"], check=True, capture_output=True, text=True,
                            env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x.invalid",
                                 "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@x.invalid"}).stdout.strip()
    return commit, tree, blob


def materialize(root, pin, anchors, dest):
    return checkout.materialize_pinned(root, pin, dest=dest, anchors=anchors)


def unlock(path: Path) -> None:
    for here, dirs, _ in os.walk(path):
        for d in dirs:
            os.chmod(os.path.join(here, d), 0o700)
    os.chmod(path, 0o700)


# 1: normal pinned repository ------------------------------------------------------------------------------------------

def test_normal_pinned_repository_passes_and_copy_is_exact(good, tmp_path):
    root, pin, anchors = good
    dest = materialize(root, pin, anchors, tmp_path / "copy")
    try:
        for rel, text in STUBS.items():
            assert (dest / rel).read_bytes() == text.encode()
    finally:
        unlock(dest)


# 2: object DB altered so the fixed revision resolves to an attacker tree --------------------------------------------

def forge_consistent_graph(root: Path, pin: str, anchors) -> str:
    """Make the genuine commit, root tree and the lazy_mod blob ids answer with an internally consistent malicious graph."""
    commit, tree, blob = attacker_commit(root)
    genuine_blob = dict((p, b) for _, p, b in anchors.files)["models/lazy_mod.py"]
    models = git(root, "rev-parse", f"{pin}:models").strip()
    evil_models = git(root, "rev-parse", f"{tree}:models").strip()
    cat = lambda oid: subprocess.run(["git", "-C", str(root), "cat-file", "tree" if oid != commit else "commit", oid], check=True, capture_output=True).stdout
    forge_pack(root, {
        pin: ("commit", cat(commit)),
        anchors.tree: ("tree", cat(tree)),
        models: ("tree", cat(evil_models)),
        genuine_blob: ("blob", b"VALUE = 'EVIL'\n"),
    })
    return "VALUE = 'EVIL'\n"


def test_premise_plain_git_really_is_redirected_by_a_forged_object_database(good):
    """Why name resolution is not enough: plain git, asked about the genuine commit id, returns the attacker's content."""
    root, pin, anchors = good
    forge_consistent_graph(root, pin, anchors)
    assert git(root, "show", f"{pin}:models/lazy_mod.py") == "VALUE = 'EVIL'\n"


def test_object_database_redefining_the_pinned_commit_tree_and_blobs_is_refused(good, tmp_path):
    root, pin, anchors = good
    forge_consistent_graph(root, pin, anchors)
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")


@pytest.mark.parametrize("forge", ["commit", "tree", "blob"])
def test_forged_object_under_a_genuine_id_is_refused(good, tmp_path, forge):
    root, pin, anchors = good
    commit, tree, blob = attacker_commit(root)
    if forge == "commit":
        write_loose(root, pin, "commit", raw(root, commit))
    elif forge == "tree":
        # genuine commit, but the root tree id now resolves to the attacker's (consistent) tree
        write_loose(root, anchors.tree, "tree", subprocess.run(["git", "-C", str(root), "cat-file", "tree", tree], check=True, capture_output=True).stdout)
    else:
        genuine = dict((p, b) for _, p, b in anchors.files)["models/lazy_mod.py"]
        write_loose(root, genuine, "blob", b"VALUE = 'EVIL'\n")
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")
    assert not (tmp_path / "copy" / "models").exists()


def test_forged_subtree_adding_a_file_is_refused(good, tmp_path):
    root, pin, anchors = good
    blob = new_object(root, "blob", b"import os\n")
    models = git(root, "rev-parse", f"{pin}:models").strip()
    payload = subprocess.run(["git", "-C", str(root), "cat-file", "tree", models], check=True, capture_output=True).stdout
    write_loose(root, models, "tree", payload + b"100644 evil.py\0" + bytes.fromhex(blob))
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")


# 3: attacker supplies a complete, internally consistent malicious set ------------------------------------------------

def test_internally_consistent_attacker_repository_is_refused_because_ids_differ(good, tmp_path):
    _, pin, anchors = good
    evil_root = tmp_path / "evil"
    evil_root.mkdir()
    evil_pin = make_repo(evil_root, dict(STUBS, **{"models/lazy_mod.py": "VALUE = 'EVIL'\n"}))
    assert evil_pin != pin
    # everything in it is self-consistent, HEAD/branch/tag all say "the fixed revision"
    git(evil_root, "tag", "pinned")
    assert checkout.checkout_problems(evil_root, evil_pin) == []
    with pytest.raises(ValueError):
        materialize(evil_root, pin, anchors, tmp_path / "a")
    with pytest.raises(ValueError):  # trusted anchors do not belong to the attacker's own commit id either
        materialize(evil_root, evil_pin, anchors, tmp_path / "b")
    # anchors that merely trust whatever the attacker's repository says would pass: that is the defect being closed
    own = anchors_for(evil_root, evil_pin)
    unlock(materialize(evil_root, evil_pin, own, tmp_path / "c"))


def test_wrong_tree_or_manifest_in_the_anchors_is_refused(good, tmp_path):
    root, pin, anchors = good
    cases = {
        "tree": anchors._replace(tree="0" * 40),
        "extra path": anchors._replace(files=anchors.files + (("100644", "zzz.py", "1" * 40),)),
        "missing path": anchors._replace(files=anchors.files[1:]),
        "wrong blob": anchors._replace(files=(("100644", anchors.files[0][1], "2" * 40),) + anchors.files[1:]),
        "wrong mode": anchors._replace(files=(("100755", anchors.files[0][1], anchors.files[0][2]),) + anchors.files[1:]),
    }
    for name, bad in cases.items():
        with pytest.raises(ValueError):
            materialize(root, pin, bad, tmp_path / name.replace(" ", "_"))


def test_symbolic_or_foreign_pin_is_refused(good, tmp_path):
    root, pin, anchors = good
    for bad in ("HEAD", "refs/heads/master", pin[:12], "0" * 40, anchors.tree):
        with pytest.raises(ValueError):
            materialize(root, bad, anchors, tmp_path / "x")


# 4: replace objects ---------------------------------------------------------------------------------------------------

def test_replace_refs_are_ignored(good, tmp_path, monkeypatch):
    root, pin, anchors = good
    commit, tree, blob = attacker_commit(root)
    genuine_blob = dict((p, b) for _, p, b in anchors.files)["models/lazy_mod.py"]
    git(root, "replace", pin, commit)
    git(root, "replace", genuine_blob, blob)
    git(root, "replace", anchors.tree, tree)
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/replace/")
    dest = materialize(root, pin, anchors, tmp_path / "copy")
    try:
        assert (dest / "models" / "lazy_mod.py").read_text() == STUBS["models/lazy_mod.py"]
    finally:
        unlock(dest)


def test_replace_refs_for_a_forged_graph_in_an_alternate_are_refused_not_followed(good, tmp_path):
    root, pin, anchors = good
    commit, _, _ = attacker_commit(root)
    write_loose(root, pin, "commit", raw(root, commit))
    git(root, "replace", "-f", pin, commit)  # even if replace were honoured, the raw commit bytes do not hash to the pin
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")


# 5: alternate object directories --------------------------------------------------------------------------------------

def stripped_clone(good_root: Path, dest: Path) -> Path:
    """A repository with no objects of its own (everything must come from an alternate)."""
    dest.mkdir()
    git(dest, "init", "-q")
    return dest


def test_alternates_file_supplying_forged_objects_is_refused(good, tmp_path):
    root, pin, anchors = good
    commit, tree, blob = attacker_commit(root)
    forged = tmp_path / "forged"
    forged.mkdir()
    git(forged, "init", "-q")
    for oid, kind, payload in ((pin, "commit", raw(root, commit)),):
        write_loose(forged, oid, kind, payload)
    victim = stripped_clone(root, tmp_path / "victim")
    (victim / ".git" / "objects" / "info").mkdir(parents=True, exist_ok=True)
    (victim / ".git" / "objects" / "info" / "alternates").write_text(str(forged / ".git" / "objects") + "\n")
    served = subprocess.run(["git", "-C", str(victim), "cat-file", "commit", pin], capture_output=True).stdout
    assert served == raw(root, commit) and tree.encode() in served  # git serves the alternate's forged commit
    with pytest.raises(ValueError):
        materialize(victim, pin, anchors, tmp_path / "copy")


def test_environment_object_redirection_is_ignored(good, tmp_path, monkeypatch):
    root, pin, anchors = good
    commit, _, _ = attacker_commit(root)
    forged = tmp_path / "forged"
    forged.mkdir()
    git(forged, "init", "-q")
    write_loose(forged, pin, "commit", raw(root, commit))
    victim = stripped_clone(root, tmp_path / "victim")
    # the genuine objects live only in `root`; the attacker points the victim at the forged directory instead
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(forged / ".git" / "objects"))
    monkeypatch.setenv("GIT_ALTERNATE_OBJECT_DIRECTORIES", str(forged / ".git" / "objects"))
    with pytest.raises(ValueError):  # victim has no genuine objects and the redirection is ignored -> missing, not forged
        materialize(victim, pin, anchors, tmp_path / "a")
    # and a repository that does hold the genuine objects is unaffected by the redirection
    dest = materialize(root, pin, anchors, tmp_path / "b")
    try:
        assert (dest / "models" / "lazy_mod.py").read_text() == STUBS["models/lazy_mod.py"]
    finally:
        unlock(dest)


def test_alternate_supplying_the_genuine_objects_is_not_followed(good, tmp_path):
    """R1-B3 adaptation: R1-B2 accepted genuine bytes served through ``objects/info/alternates`` (git followed it). The
    trusted reader no longer follows alternates at all (an alternate is repository-controlled redirection), so the same
    setup is refused deterministically; the genuine objects must live in the checkout's own object directory."""
    root, pin, anchors = good
    victim = stripped_clone(root, tmp_path / "victim")
    (victim / ".git" / "objects" / "info").mkdir(parents=True, exist_ok=True)
    (victim / ".git" / "objects" / "info" / "alternates").write_text(str(root / ".git" / "objects") + "\n")
    with pytest.raises(ValueError, match="missing or not authentic"):
        materialize(victim, pin, anchors, tmp_path / "copy")


# 6: malicious local refs / tags ----------------------------------------------------------------------------------------

def test_malicious_refs_tags_head_and_packed_refs_cannot_affect_selection(good, tmp_path):
    root, pin, anchors = good
    commit, _, _ = attacker_commit(root)
    git(root, "update-ref", "refs/heads/master", commit)
    git(root, "update-ref", "refs/heads/main", commit)
    git(root, "update-ref", f"refs/tags/{pin}", commit)
    git(root, "update-ref", "refs/tags/pinned", commit)
    (root / ".git" / "packed-refs").write_text(f"{commit} refs/tags/{pin[:12]}\n")
    (root / ".git" / "HEAD").write_text(f"{commit}\n")
    (root / ".git" / "shallow").write_text(f"{pin}\n")
    (root / ".git" / "info").mkdir(exist_ok=True)
    (root / ".git" / "info" / "grafts").write_text(f"{pin} {commit}\n")
    dest = materialize(root, pin, anchors, tmp_path / "copy")
    try:
        assert (dest / "models" / "lazy_mod.py").read_text() == STUBS["models/lazy_mod.py"]
    finally:
        unlock(dest)


# 7: detached bytes equal trusted blob ids -------------------------------------------------------------------------------

def test_materialized_files_hash_to_the_trusted_blob_ids(good, tmp_path):
    root, pin, anchors = good
    dest = materialize(root, pin, anchors, tmp_path / "copy")
    try:
        found = {}
        for here, _, names in os.walk(dest):
            for name in names:
                path = Path(here) / name
                data = path.read_bytes()
                found[path.relative_to(dest).as_posix()] = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
        assert found == {rel: blob for _, rel, blob in anchors.files}
    finally:
        unlock(dest)


# 8: untracked / shadow modules ---------------------------------------------------------------------------------------

def test_untracked_and_shadow_modules_cannot_influence_import(good, tmp_path):
    root, pin, _ = good
    (root / "models" / "evil_shadow.py").write_text("raise SystemExit('shadow imported')\n")
    (root / "utils" / "trust.py").write_text("raise SystemExit('tracked file replaced')\n")
    (root / "sitecustomize.py").write_text("raise SystemExit('sitecustomize')\n")
    (root / "models" / "lazy_mod.pyc").write_bytes(b"junk")
    body = "print('LAZY', a.verify_attestation.__globals__['lazy']())\n"
    done = run_adapter(root, pin, body, tmp_path)
    assert done.returncode == 0, done.stderr
    assert "LAZY ('pinned'," in done.stdout and "shadow" not in done.stdout + done.stderr


# 9: post-verification checkout mutation -------------------------------------------------------------------------------

def test_mutation_and_object_store_tampering_after_verification_do_not_change_execution(good, tmp_path):
    root, pin, _ = good
    body = f"""
    import pathlib, shutil
    root = pathlib.Path({str(root)!r})
    (root / 'models' / 'lazy_mod.py').write_text("VALUE = 'EVIL'\\n")
    shutil.rmtree(root / '.git' / 'objects')
    print('LAZY', a.verify_attestation.__globals__['lazy']()[0])
    """
    done = run_adapter(root, pin, body, tmp_path)
    assert done.returncode == 0, done.stderr
    assert "LAZY pinned" in done.stdout


# Adapter end to end: an attacker object database is refused by the real loader ----------------------------------------

def test_adapter_refuses_forged_object_database_end_to_end(good, tmp_path):
    root, pin, _ = good
    commit, _, _ = attacker_commit(root)
    write_loose(root, pin, "commit", raw(root, commit))
    done = run_adapter(root, pin, "print('loaded')\n", tmp_path)
    assert done.returncode != 0 and "loaded" not in done.stdout
    assert "cannot be authenticated" in done.stderr


# Production anchors -------------------------------------------------------------------------------------------------

def test_adapter_pin_and_trusted_anchors_move_in_lockstep():
    trusted = load("bitrep_trusted_objects")
    assert f'PIN = "{PRODUCTION_PIN}"' in ADAPTER.read_text(encoding="utf-8")
    assert trusted.COMMIT == PRODUCTION_PIN
    assert trusted.TREE == "96d9a687597c8a5e63c55a52c92fbfef35b791ba"
    assert len(trusted.FILES) == 71 and list(trusted.FILES) == sorted(trusted.FILES, key=lambda e: e[1])
    assert all(len(b) == 40 and m in ("100644", "100755", "120000") for m, _, b in trusted.FILES)


def test_adapter_refuses_if_anchors_do_not_belong_to_pin(tmp_path):
    work = tmp_path / "w"
    work.mkdir()
    shutil.copy(ADAPTER, work / "bitrep_adapter.py")
    shutil.copy(MODULE, work / "bitrep_checkout.py")
    (work / "bitrep_trusted_objects.py").write_text(f'COMMIT = "{"a" * 40}"\nTREE = "{"b" * 40}"\nFILES = ()\n')
    done = subprocess.run(["python3", "-I", "-c", "import sys; sys.path.insert(0, %r); import bitrep_adapter" % str(work)],
                          env={"BITREP_ROOT": str(tmp_path), "PATH": os.environ["PATH"]}, capture_output=True, text=True)
    assert done.returncode != 0 and "do not belong to PIN" in done.stderr


def unpack_packs(repo: Path) -> None:
    """Turn packed objects into loose ones so a single object can be replaced on disk."""
    packs = list((repo / ".git" / "objects" / "pack").glob("*.pack"))
    for pack in packs:
        moved = repo.parent / pack.name
        shutil.move(str(pack), moved)
        for idx in pack.parent.glob(pack.stem + ".*"):
            idx.unlink()
        subprocess.run(["git", "-C", str(repo), "unpack-objects", "-q"], stdin=moved.open("rb"), check=True)


needs_clone = pytest.mark.skipif(not (KNOWN_GOOD / ".git").exists(), reason="known-good BitRep clone not available")


@needs_clone
def test_production_anchors_verify_against_the_known_good_clone(tmp_path):
    trusted = load("bitrep_trusted_objects")
    anchors = checkout.TrustedObjects(trusted.COMMIT, trusted.TREE, tuple(trusted.FILES))
    dest = materialize(KNOWN_GOOD, trusted.COMMIT, anchors, tmp_path / "copy")
    try:
        assert (dest / "utils" / "verification.py").is_file()
    finally:
        unlock(dest)


@needs_clone
def test_committed_anchors_are_exactly_what_the_derivation_tool_produces():
    tool = load("derive_bitrep_trusted_objects")
    assert tool.render(KNOWN_GOOD, PRODUCTION_PIN) == (PYDIR / "bitrep_trusted_objects.py").read_text(encoding="utf-8")


@needs_clone
def test_production_anchors_refuse_a_one_byte_tampered_blob(tmp_path):
    trusted = load("bitrep_trusted_objects")
    anchors = checkout.TrustedObjects(trusted.COMMIT, trusted.TREE, tuple(trusted.FILES))
    clone = tmp_path / "clone"
    shutil.copytree(KNOWN_GOOD, clone)
    unpack_packs(clone)
    blob = dict((p, b) for _, p, b in trusted.FILES)["utils/verification.py"]
    data = subprocess.run(["git", "-C", str(clone), "cat-file", "blob", blob], check=True, capture_output=True).stdout
    write_loose(clone, blob, "blob", data + b"#")
    with pytest.raises(ValueError):
        materialize(clone, trusted.COMMIT, anchors, tmp_path / "copy")
