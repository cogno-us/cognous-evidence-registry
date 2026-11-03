"""R1-B3: the trusted object-read path starts no git process and reads attacker-supplied object bytes under hard bounds.

Findings csf_518b8599e95b7919b55fe371 (HIGH: repository-local partial-clone/promisor/protocol settings made
``git cat-file --batch`` lazy-fetch and run an attacker helper before Python authenticated any byte) and
csf_d7e271587bb3dc0dec7ac96f (MEDIUM: git batch output buffered without a byte limit before verification).

Hermetic: throwaway repositories built with real git (loose, packed, OFS_DELTA, REF_DELTA, mixed) plus hand-built
malformed packs. Test numbers follow the sprint text (R1-B3 section 8). ``git`` is used here only to BUILD fixtures and to
derive anchors independently of the reader under test.
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import os
import random
import shutil
import stat
import struct
import subprocess
import textwrap
import tracemalloc
import zlib
from pathlib import Path

import pytest

import test_r1b_source_verification as srcv
from test_bitrep_checkout import MODULE, checkout, git
from test_r1b_source_verification import STUBS, run_adapter
from test_r1b2_trusted_object_anchors import (
    KNOWN_GOOD, attacker_commit, forge_consistent_graph, forge_pack, load, needs_clone, raw, unlock, write_loose,
)

ADAPTER = MODULE.with_name("bitrep_adapter.py")
BIG = "".join(f"line {i} of a reasonably repetitive file\n" for i in range(400))
VARIANTS = ["loose", "packed", "ofs", "ref", "mixed"]


# --------------------------------------------------------------------------------------------------------------------
# fixtures

def git_anchors(root: Path, pin: str):
    """Anchors derived with git plumbing, independent of the reader under test."""
    tree = git(root, "rev-parse", f"{pin}^{{tree}}").strip()
    files = []
    for entry in git(root, "ls-tree", "-r", "-z", pin).split("\0"):
        if entry:
            meta, rel = entry.split("\t", 1)
            mode, _, blob = meta.split()
            files.append((mode, rel, blob))
    return checkout.TrustedObjects(pin, tree, tuple(sorted(files, key=lambda e: e[1])))


def build_repo(tmp_path: Path, variant: str, name: str = "repo"):
    root = tmp_path / name
    root.mkdir()
    for rel, text in {**STUBS, "data/big.txt": BIG}.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "pin")
    pin = git(root, "rev-parse", "HEAD").strip()
    if variant in ("ofs", "ref"):  # newer, larger versions become delta bases; the pinned version is stored as a delta
        for n in range(1, 5):
            (root / "data" / "big.txt").write_text(BIG + "".join(f"extra {i}\n" for i in range(n * 20)))
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", f"c{n}")
        if variant == "ref":
            git(root, "config", "repack.useDeltaBaseOffset", "false")
        git(root, "repack", "-a", "-d", "-f", "--window=50", "--depth=50")
        git(root, "prune-packed")
    elif variant in ("packed", "mixed"):
        git(root, "repack", "-a", "-d")
        git(root, "prune-packed")
        if variant == "mixed":  # the pinned commit, root tree, one subtree and one blob are loose; the rest is packed
            (root / "models" / "lazy_mod.py").write_text("VALUE = 'mixed'\n")
            git(root, "add", "-A")
            git(root, "commit", "-q", "-m", "pin2")
            pin = git(root, "rev-parse", "HEAD").strip()
    return root, pin, git_anchors(root, pin)


@pytest.fixture(params=VARIANTS)
def repo(request, tmp_path):
    root, pin, anchors = build_repo(tmp_path, request.param)
    if request.param in ("ofs", "ref"):
        blob = dict((p, b) for _, p, b in anchors.files)["data/big.txt"]
        listing = subprocess.run(["git", "-C", str(root), "verify-pack", "-v", *(root / ".git/objects/pack").glob("*.idx")],
                                 check=True, capture_output=True, text=True).stdout
        row = next(l.split() for l in listing.splitlines() if l.startswith(blob))
        assert len(row) >= 7, "fixture must store the pinned blob as a delta"
    return root, pin, anchors


@pytest.fixture()
def loose(tmp_path):
    return build_repo(tmp_path, "loose")


def materialize(root, pin, anchors, dest):
    return checkout.materialize_pinned(root, pin, dest=dest, anchors=anchors)


def assert_exact(dest: Path, anchors) -> None:
    found = {}
    for here, _, names in os.walk(dest):
        for name in names:
            data = (Path(here) / name).read_bytes()
            found[(Path(here) / name).relative_to(dest).as_posix()] = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()
    assert found == {rel: blob for _, rel, blob in anchors.files}


def object_path(root: Path, oid: str) -> Path:
    return root / ".git" / "objects" / oid[:2] / oid[2:]


def blob_of(anchors, rel: str) -> str:
    return dict((p, b) for _, p, b in anchors.files)[rel]


def adapter_anchors(monkeypatch, root: Path, pin: str, anchors) -> None:
    """run_adapter derives anchors from the repository itself; the exploit tests need anchors from the PRISTINE repository."""
    text = f'COMMIT = "{anchors.commit}"\nTREE = "{anchors.tree}"\nFILES = {anchors.files!r}\n'
    monkeypatch.setattr(srcv, "anchors_module_text", lambda *_: text)


# --------------------------------------------------------------------------------------------------------------------
# 1. normal pinned source passes (loose, packed, OFS_DELTA, REF_DELTA, mixed) and 15. bytes hash to the trusted blob ids

def test_01_normal_pinned_source_passes_in_every_storage_form(repo, tmp_path):
    root, pin, anchors = repo
    dest = materialize(root, pin, anchors, tmp_path / "copy")
    try:
        assert_exact(dest, anchors)  # 15: every materialized file hashes to its trusted blob id
        assert (dest / "data" / "big.txt").read_bytes() == subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob", blob_of(anchors, "data/big.txt")], check=True, capture_output=True).stdout
    finally:
        unlock(dest)


@pytest.mark.parametrize("variant", ["ofs", "ref"])
def test_delta_kinds_are_present_in_the_fixtures(tmp_path, variant):
    root, pin, anchors = build_repo(tmp_path, variant)
    data = next((root / ".git/objects/pack").glob("*.pack")).read_bytes()
    kinds = set()
    with checkout._ObjectStore(root) as store:
        offset = store.packs()[0].find(blob_of(anchors, "data/big.txt"))
    kinds.add((data[offset] >> 4) & 7)
    assert kinds == ({6} if variant == "ofs" else {7})


@needs_clone
def test_01_production_packed_clone_verifies_with_git_unavailable(tmp_path, monkeypatch):
    trusted = load("bitrep_trusted_objects")
    anchors = checkout.TrustedObjects(trusted.COMMIT, trusted.TREE, tuple(trusted.FILES))
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(checkout.subprocess, "run", _boom)
    dest = materialize(KNOWN_GOOD, trusted.COMMIT, anchors, tmp_path / "copy")
    try:
        assert_exact(dest, anchors)
    finally:
        unlock(dest)


def _boom(*a, **k):
    raise AssertionError("a git/subprocess invocation happened on the trusted path")


# --------------------------------------------------------------------------------------------------------------------
# 2. forged object graph (the R1-B2 exploit primitive: a forged pack index claims a genuine id for attacker bytes)

def test_02_forged_pack_index_claiming_genuine_ids_is_refused(loose, tmp_path):
    root, pin, anchors = loose
    forge_consistent_graph(root, pin, anchors)
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")


def test_02_forged_pack_never_wins_over_or_beside_genuine_packed_objects(tmp_path):
    root, pin, anchors = build_repo(tmp_path, "packed")
    forge_consistent_graph(root, pin, anchors)
    dest = materialize(root, pin, anchors, tmp_path / "copy")  # genuine pack still supplies authentic bytes
    try:
        assert_exact(dest, anchors)
        assert b"EVIL" not in (dest / "models" / "lazy_mod.py").read_bytes()
    finally:
        unlock(dest)


def test_02_forged_pack_alone_in_a_packed_repository_is_refused(tmp_path):
    root, pin, anchors = build_repo(tmp_path, "packed")
    genuine = list((root / ".git/objects/pack").iterdir())
    forge_consistent_graph(root, pin, anchors)
    for f in genuine:
        f.unlink()
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")


# --------------------------------------------------------------------------------------------------------------------
# 3-6. csf_518b: repository-local partial-clone / promisor / protocol helper settings, real adapter, marker file

def _helper(tmp_path: Path, marker: Path) -> Path:
    helper = tmp_path / "helper.sh"
    helper.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 1\n")
    helper.chmod(0o755)
    return helper


def _append_config(root: Path, text: str, *, partial: bool = True) -> None:
    cfg = root / ".git" / "config"
    body = cfg.read_text()
    if partial:
        body = body.replace("repositoryformatversion = 0", "repositoryformatversion = 1")
    cfg.write_text(body + text)


def _delete_object(root: Path, oid: str) -> None:
    path = object_path(root, oid)
    path.chmod(0o644)
    path.unlink()


def _expect_refused(done) -> None:
    assert done.returncode != 0 and "loaded" not in done.stdout, done.stdout + done.stderr
    assert "cannot be authenticated" in done.stderr, done.stderr


@pytest.mark.parametrize("missing", ["blob", "tree", "commit"])
def test_03_repository_local_promisor_configuration_cannot_execute_commands(loose, tmp_path, monkeypatch, missing):
    root, pin, anchors = loose
    adapter_anchors(monkeypatch, root, pin, anchors)
    marker = tmp_path / "MARKER"
    helper = _helper(tmp_path, marker)
    target = {"blob": blob_of(anchors, "utils/trust.py"), "tree": anchors.tree, "commit": pin}[missing]
    _delete_object(root, target)
    _append_config(root, f'[extensions]\n\tpartialClone = evil\n[remote "evil"]\n\turl = ext::sh {helper}\n'
                         f'\tpromisor = true\n\tpartialclonefilter = blob:none\n[protocol "ext"]\n\tallow = always\n')
    done = run_adapter(root, pin, "print('loaded')\n", tmp_path)
    assert not marker.exists(), "attacker helper was executed (csf_518b8599e95b7919b55fe371)"
    _expect_refused(done)


@pytest.mark.parametrize("where", ["local-config", "environment"])
def test_04_protocol_ext_allow_always_cannot_enable_helper_execution(loose, tmp_path, monkeypatch, where):
    root, pin, anchors = loose
    adapter_anchors(monkeypatch, root, pin, anchors)
    marker = tmp_path / "MARKER"
    helper = _helper(tmp_path, marker)
    _delete_object(root, blob_of(anchors, "models/lazy_mod.py"))
    env = {}
    remote = f'[remote "evil"]\n\turl = ext::sh {helper}\n\tpromisor = true\n'
    if where == "local-config":
        _append_config(root, remote + '[protocol "ext"]\n\tallow = always\n')
    else:
        _append_config(root, remote)
        env = {"GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "protocol.ext.allow", "GIT_CONFIG_VALUE_0": "always",
               "GIT_CONFIG_KEY_1": "extensions.partialClone", "GIT_CONFIG_VALUE_1": "evil", "GIT_ALLOW_PROTOCOL": "ext"}
    done = run_adapter(root, pin, "print('loaded')\n", tmp_path, env_extra=env)
    assert not marker.exists()
    _expect_refused(done)


def test_05_missing_anchored_object_cannot_cause_a_lazy_fetch(loose, tmp_path, monkeypatch):
    """A promisor remote that really holds the object (local path) must not be asked: the object is simply missing."""
    root, pin, anchors = loose
    source = tmp_path / "source"
    shutil.copytree(root, source)
    adapter_anchors(monkeypatch, root, pin, anchors)
    target = blob_of(anchors, "utils/trust.py")
    _delete_object(root, target)
    before = sorted(str(p) for p in (root / ".git").rglob("*") if p.is_file() and p.name != "config")
    _append_config(root, f'[extensions]\n\tpartialClone = origin\n[remote "origin"]\n\turl = {source}\n\tpromisor = true\n'
                         f'\tpartialclonefilter = blob:none\n[protocol "file"]\n\tallow = always\n[protocol]\n\tallow = always\n')
    done = run_adapter(root, pin, "print('loaded')\n", tmp_path)
    _expect_refused(done)
    after = sorted(str(p) for p in (root / ".git").rglob("*") if p.is_file() and p.name != "config")
    assert after == before and not object_path(root, target).exists(), "an object was fetched into the checkout"
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")


@pytest.mark.parametrize("variant", ["ext", "ext-no-promisor", "remote-vcs-helper", "uploadpack-program", "ssh-command", "git-proxy"])
def test_06_malicious_remote_helper_marker_is_never_created(loose, tmp_path, monkeypatch, variant):
    root, pin, anchors = loose
    adapter_anchors(monkeypatch, root, pin, anchors)
    marker = tmp_path / "MARKER"
    helper = _helper(tmp_path, marker)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    shutil.copy(helper, bindir / "git-remote-evil")
    _delete_object(root, blob_of(anchors, "models/verification.py"))
    other = tmp_path / "other"
    shutil.copytree(root, other)
    config = {
        "ext": f'[remote "e"]\n\turl = ext::sh {helper}\n\tpromisor = true\n[protocol "ext"]\n\tallow = always\n',
        "ext-no-promisor": f'[extensions]\n\tpartialClone = e\n[remote "e"]\n\turl = ext::sh {helper}\n[protocol]\n\tallow = always\n',
        "remote-vcs-helper": '[remote "e"]\n\turl = evil::x\n\tpromisor = true\n[protocol]\n\tallow = always\n',
        "uploadpack-program": f'[remote "e"]\n\turl = {other}\n\tuploadpack = {helper}\n\tpromisor = true\n[protocol]\n\tallow = always\n',
        "ssh-command": f'[core]\n\tsshCommand = {helper}\n[remote "e"]\n\turl = ssh://localhost/x\n\tpromisor = true\n[protocol]\n\tallow = always\n',
        "git-proxy": f'[core]\n\tgitProxy = {helper}\n[remote "e"]\n\turl = git://127.0.0.1:1/x\n\tpromisor = true\n[protocol]\n\tallow = always\n',
    }[variant]
    _append_config(root, config)
    done = run_adapter(root, pin, "print('loaded')\n", tmp_path, env_extra={"PATH": f"{bindir}:{os.environ['PATH']}"})
    assert not marker.exists(), "attacker helper was executed"
    _expect_refused(done)


# --------------------------------------------------------------------------------------------------------------------
# 7-8. GIT_OBJECT_DIRECTORY / GIT_ALTERNATE_OBJECT_DIRECTORIES / alternates files

def _forged_store(tmp_path, root, pin):
    commit, _, _ = attacker_commit(root)
    forged = tmp_path / "forged"
    forged.mkdir()
    git(forged, "init", "-q")
    write_loose(forged, pin, "commit", raw(root, commit))
    return forged


def _empty_clone(tmp_path):
    victim = tmp_path / "victim"
    victim.mkdir()
    git(victim, "init", "-q")
    return victim


def test_07_git_object_directory_cannot_redirect_trusted_identities(loose, tmp_path, monkeypatch):
    root, pin, anchors = loose
    adapter_anchors(monkeypatch, root, pin, anchors)
    forged = _forged_store(tmp_path, root, pin)
    env = {"GIT_OBJECT_DIRECTORY": str(forged / ".git" / "objects"), "GIT_DIR": str(forged / ".git")}
    ok = run_adapter(root, pin, "print('loaded')\n", tmp_path, env_extra=env)
    assert ok.returncode == 0 and "loaded" in ok.stdout, ok.stderr  # the checkout's own genuine objects are used
    victim = _empty_clone(tmp_path)
    done = run_adapter(victim, pin, "print('loaded')\n", tmp_path, env_extra=env)
    _expect_refused(done)  # redirection is ignored: missing, never forged
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", str(forged / ".git" / "objects"))
    with pytest.raises(ValueError):
        materialize(victim, pin, anchors, tmp_path / "copy")


def test_08_git_alternate_object_directories_and_alternates_files_cannot_redirect(loose, tmp_path, monkeypatch):
    root, pin, anchors = loose
    adapter_anchors(monkeypatch, root, pin, anchors)
    forged = _forged_store(tmp_path, root, pin)
    victim = _empty_clone(tmp_path)
    done = run_adapter(victim, pin, "print('loaded')\n", tmp_path,
                       env_extra={"GIT_ALTERNATE_OBJECT_DIRECTORIES": str(forged / ".git" / "objects")})
    _expect_refused(done)
    # an alternates file naming the GENUINE store is not followed either (no repository-controlled redirection at all)
    (victim / ".git" / "objects" / "info").mkdir(parents=True, exist_ok=True)
    (victim / ".git" / "objects" / "info" / "alternates").write_text(str(root / ".git" / "objects") + "\n")
    (victim / ".git" / "objects" / "info" / "http-alternates").write_text("http://127.0.0.1:1/objects\n")
    with pytest.raises(ValueError, match="missing or not authentic"):
        materialize(victim, pin, anchors, tmp_path / "copy")
    done = run_adapter(victim, pin, "print('loaded')\n", tmp_path)
    _expect_refused(done)


# --------------------------------------------------------------------------------------------------------------------
# 9. replace refs, grafts, shallow, packed-refs, HEAD, tags

def test_09_replace_refs_and_other_ref_metadata_are_ignored(repo, tmp_path, monkeypatch):
    root, pin, anchors = repo
    commit, tree, blob = attacker_commit(root)
    git(root, "replace", pin, commit)
    git(root, "replace", anchors.tree, tree)
    git(root, "replace", blob_of(anchors, "models/lazy_mod.py"), blob)
    (root / ".git" / "packed-refs").write_text(f"{commit} refs/replace/{pin}\n{commit} refs/tags/{pin[:12]}\n")
    (root / ".git" / "HEAD").write_text(f"{commit}\n")
    (root / ".git" / "shallow").write_text(f"{pin}\n")
    (root / ".git" / "info").mkdir(exist_ok=True)
    (root / ".git" / "info" / "grafts").write_text(f"{pin} {commit}\n")
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/replace/")
    dest = materialize(root, pin, anchors, tmp_path / "copy")
    try:
        assert_exact(dest, anchors)
        assert b"EVIL" not in (dest / "models" / "lazy_mod.py").read_bytes()
    finally:
        unlock(dest)


# --------------------------------------------------------------------------------------------------------------------
# 10. local / global / system configuration cannot influence retrieval

def test_10_local_global_and_system_configuration_cannot_influence_trusted_retrieval(repo, tmp_path, monkeypatch):
    root, pin, anchors = repo
    adapter_anchors(monkeypatch, root, pin, anchors)
    marker = tmp_path / "MARKER"
    helper = _helper(tmp_path, marker)
    home = tmp_path / "home"
    home.mkdir()
    hostile = f"[core]\n\tfsmonitor = {helper}\n\tpager = {helper}\n\thooksPath = {tmp_path}\n[uploadpack]\n\tpackObjectsHook = {helper}\n"
    (home / ".gitconfig").write_text(hostile)
    system = tmp_path / "system.cfg"
    system.write_text(hostile + f"[include]\n\tpath = {home / '.gitconfig'}\n")
    # a local config git itself would reject outright (unknown repository format) or misread (object format) is irrelevant
    _append_config(root, hostile + "[extensions]\n\tobjectformat = sha256\n\tfutureThing = 1\n")
    cfg = root / ".git" / "config"
    cfg.write_text(cfg.read_text().replace("repositoryformatversion = 1", "repositoryformatversion = 99"))
    env = {"HOME": str(home), "XDG_CONFIG_HOME": str(home), "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
           "GIT_CONFIG_SYSTEM": str(system), "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.fsmonitor",
           "GIT_CONFIG_VALUE_0": str(helper)}
    done = run_adapter(root, pin, "print('loaded')\n", tmp_path, env_extra=env)
    assert done.returncode == 0 and "loaded" in done.stdout, done.stderr
    assert not marker.exists()


# --------------------------------------------------------------------------------------------------------------------
# 11-12. shadow modules and post-verification mutation (packed repositories, real adapter)

@pytest.mark.parametrize("variant", ["packed", "ofs"])
def test_11_untracked_and_shadow_modules_cannot_influence_import(tmp_path, variant):
    root, pin, anchors = build_repo(tmp_path, variant)
    (root / "models" / "evil_shadow.py").write_text("raise SystemExit('shadow imported')\n")
    (root / "utils" / "trust.py").write_text("raise SystemExit('tracked file replaced')\n")
    (root / "sitecustomize.py").write_text("raise SystemExit('sitecustomize')\n")
    (root / "models" / "lazy_mod.pyc").write_bytes(b"junk")
    done = run_adapter(root, pin, "print('LAZY', a.verify_attestation.__globals__['lazy']())\n", tmp_path)
    assert done.returncode == 0, done.stderr
    assert "LAZY ('pinned'," in done.stdout and "shadow" not in done.stdout + done.stderr


@pytest.mark.parametrize("variant", ["packed", "ref"])
def test_12_post_verification_mutation_and_object_store_deletion_do_not_change_execution(tmp_path, variant):
    root, pin, _ = build_repo(tmp_path, variant)
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


# --------------------------------------------------------------------------------------------------------------------
# git is not on the trusted path at all

@pytest.mark.parametrize("variant", VARIANTS)
def test_verification_succeeds_with_git_unavailable_and_no_subprocess_started(tmp_path, variant):
    root, pin, _ = build_repo(tmp_path, variant)
    preamble = """
    import os, subprocess
    def boom(*a, **k):
        raise AssertionError('subprocess started on the trusted path')
    subprocess.run = subprocess.Popen = subprocess.call = subprocess.check_call = subprocess.check_output = boom
    os.system = os.popen = os.posix_spawn = os.execv = os.execvp = os.fork = boom
    """
    done = run_adapter(root, pin, "print('LAZY', a.verify_attestation.__globals__['lazy']()[0])\n", tmp_path,
                       env_extra={"PATH": str(tmp_path / "no-such-dir")}, preamble=preamble)
    assert done.returncode == 0, done.stderr
    assert done.stdout.split()[-1] in ("pinned", "mixed")


def test_trusted_path_source_has_no_git_or_subprocess_reference():
    names = ("_ObjectStore", "_Pack", "_Inflater", "_apply_delta", "_open_regular", "_pread_exact", "verify_commit",
             "verified_tree_entries", "verify_anchored", "materialize_pinned")
    module_source = MODULE.read_text(encoding="utf-8")
    nodes = {n.name: n for n in ast.parse(module_source).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    for name in names:
        source = ast.get_source_segment(module_source, nodes[name])
        assert "subprocess" not in source and "_git(" not in source and "_git_cmd" not in source, name
        assert "checkout_problems" not in source, name
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    used = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "subprocess"}
    assert used <= {"CalledProcessError"}, used  # the adapter only names the exception type
    assert "checkout_problems" not in ADAPTER.read_text(encoding="utf-8")
    assert not hasattr(checkout, "_git_bytes")


# --------------------------------------------------------------------------------------------------------------------
# 13. bounds: oversized / bomb inputs refuse before unbounded buffering (csf_d7e271587bb3dc0dec7ac96f)

def peak_while(fn) -> int:
    tracemalloc.start()
    try:
        try:
            fn()
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def test_13_loose_object_declaring_a_huge_size_refuses_without_buffering_it(loose, tmp_path):
    root, pin, anchors = loose
    target = blob_of(anchors, "utils/trust.py")
    path = object_path(root, target)
    path.chmod(0o644)
    path.write_bytes(zlib.compress(b"blob %d\0" % (64 << 20) + b"\0" * (64 << 20)))  # 64 MiB zeros: a ~64 KiB compressed bomb
    assert path.stat().st_size < 100_000
    peak = peak_while(lambda: materialize(root, pin, anchors, tmp_path / "copy"))
    assert peak < 3 * 1024 * 1024, peak


def test_13_loose_bomb_with_a_small_declared_size_refuses_without_buffering_it(loose, tmp_path):
    root, pin, anchors = loose
    path = object_path(root, blob_of(anchors, "utils/trust.py"))
    path.chmod(0o644)
    path.write_bytes(zlib.compress(b"blob 10\0" + b"\0" * (64 << 20)))
    assert peak_while(lambda: materialize(root, pin, anchors, tmp_path / "copy")) < 3 * 1024 * 1024


def test_13_oversized_compressed_input_is_refused_before_reading_it(loose, tmp_path):
    root, pin, anchors = loose
    path = object_path(root, blob_of(anchors, "utils/trust.py"))
    path.chmod(0o644)
    path.write_bytes(os.urandom(checkout.MAX_COMPRESSED + 4096))
    assert peak_while(lambda: materialize(root, pin, anchors, tmp_path / "copy")) < 1024 * 1024


def test_13_pack_object_declaring_an_oversized_size_never_reaches_inflate(tmp_path, monkeypatch):
    root = tmp_path / "r"
    oid = _sha(b"blob", b"x")
    write_pack(root, [(oid, entry(3, b"x", declared=1 << 30))])
    monkeypatch.setattr(checkout, "_Inflater", _boom)  # would raise AssertionError (not ValueError) if reached
    with checkout._ObjectStore(root) as store:
        pack = store.packs()[0]
        with pytest.raises(ValueError, match="size above the bound"):
            pack.read(pack.find(oid))
        with pytest.raises(ValueError, match="missing or not authentic"):
            store.read(oid, "blob")


def test_13_pack_bomb_with_a_small_declared_size_is_refused_early(tmp_path):
    root = tmp_path / "r"
    oid = _sha(b"blob", b"x")
    write_pack(root, [(oid, vhdr(3, 10) + zlib.compress(b"\0" * (64 << 20)))])

    def attempt():
        with checkout._ObjectStore(root) as store:
            store.read(oid, "blob")

    assert peak_while(attempt) < 1024 * 1024


def test_13_tree_entry_total_bytes_and_object_count_bounds(tmp_path, monkeypatch):
    root = tmp_path / "many"
    root.mkdir()
    for i in range(checkout.MAX_TREE_ENTRIES + 1):
        (root / f"f{i}.txt").write_text(str(i))
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "many")
    pin = git(root, "rev-parse", "HEAD").strip()
    tree = git(root, "rev-parse", "HEAD^{tree}").strip()
    with pytest.raises(ValueError, match="too many entries"):
        checkout.verify_anchored(root, checkout.TrustedObjects(pin, tree, ()))
    good_root, good_pin, anchors = build_repo(tmp_path, "packed", "good")
    monkeypatch.setattr(checkout, "MAX_TOTAL_BYTES", 1000)
    with pytest.raises(ValueError, match="total byte bound"):
        checkout.verify_anchored(good_root, anchors)
    monkeypatch.undo()
    monkeypatch.setattr(checkout, "MAX_OBJECTS", 3)
    with pytest.raises(ValueError, match="too many objects"):
        checkout.verify_anchored(good_root, anchors)


def test_13_production_bounds_have_headroom_over_the_known_use_case():
    assert checkout.MAX_OBJECT_SIZE >= 4 * 34527 and checkout.MAX_TOTAL_BYTES >= 4 * 438643
    assert checkout.MAX_TOTAL_BYTES <= 16 * 1024 * 1024 and checkout.MAX_TREE_ENTRIES >= 71


# --------------------------------------------------------------------------------------------------------------------
# 14. malformed pack / index / object input refuses deterministically

def _sha(kind: bytes, payload: bytes) -> str:
    return hashlib.sha1(kind + b" %d\0" % len(payload) + payload).hexdigest()


def vhdr(kind: int, size: int) -> bytes:
    out = bytearray([(kind << 4) | (size & 15) | (0x80 if size >> 4 else 0)])
    size >>= 4
    while size:
        out.append((size & 0x7F) | (0x80 if size >> 7 else 0))
        size >>= 7
    return bytes(out)


def ofs_enc(n: int) -> bytes:
    out = [n & 0x7F]
    n >>= 7
    while n:
        n -= 1
        out.append(0x80 | (n & 0x7F))
        n >>= 7
    return bytes(reversed(out))


def dvar(n: int) -> bytes:
    out = bytearray()
    while True:
        out.append((n & 0x7F) | (0x80 if n >> 7 else 0))
        n >>= 7
        if not n:
            return bytes(out)


def copy_all(base_len: int, tail: bytes = b"") -> bytes:
    """A delta that reproduces its base followed by ``tail``."""
    ops, pos = b"", 0
    while pos < base_len:
        n, o = min(base_len - pos, 0xFFFF), pos
        op, extra = 0x80, b""
        for i in range(4):
            if (o >> (8 * i)) & 0xFF:
                op |= 1 << i
                extra += bytes([(o >> (8 * i)) & 0xFF])
        for i in range(3):
            if (n >> (8 * i)) & 0xFF:
                op |= 0x10 << i
                extra += bytes([(n >> (8 * i)) & 0xFF])
        ops += bytes([op]) + extra
        pos += n
    if tail:
        ops += bytes([len(tail)]) + tail
    return dvar(base_len) + dvar(base_len + len(tail)) + ops


def entry(kind: int, payload: bytes, declared: int | None = None) -> bytes:
    return vhdr(kind, len(payload) if declared is None else declared) + zlib.compress(payload)


def write_pack(root: Path, items: list[tuple[str, bytes]], *, idx_edit=None, pack_edit=None) -> tuple[Path, Path, list[int]]:
    """items: [(40-hex id, encoded pack entry)]; offsets of OFS_DELTA bases are the caller's job (see ``chain``)."""
    body, offsets = b"PACK" + struct.pack(">II", 2, len(items)), []
    for _, enc in items:
        offsets.append(len(body))
        body += enc
    trailer = hashlib.sha1(body).digest()
    order = sorted(range(len(items)), key=lambda i: items[i][0])
    fan, total = [0] * 256, 0
    for i in order:
        fan[int(items[i][0][:2], 16)] += 1
    fanout = b""
    for c in fan:
        total += c
        fanout += struct.pack(">I", total)
    idx = b"\xfftOc" + struct.pack(">I", 2) + fanout + b"".join(bytes.fromhex(items[i][0]) for i in order)
    idx += b"".join(struct.pack(">I", zlib.crc32(items[i][1])) for i in order)
    idx += b"".join(struct.pack(">I", offsets[i]) for i in order) + trailer
    idx += hashlib.sha1(idx).digest()
    pack = body + trailer
    if idx_edit:
        idx = idx_edit(idx)
    if pack_edit:
        pack = pack_edit(pack)
    pack_dir = root / ".git" / "objects" / "pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    name = f"pack-{trailer.hex()}"
    (pack_dir / (name + ".pack")).write_bytes(pack)
    (pack_dir / (name + ".idx")).write_bytes(idx)
    return pack_dir / (name + ".pack"), pack_dir / (name + ".idx"), offsets


def read_blob(root: Path, oid: str) -> bytes:
    with checkout._ObjectStore(root) as store:
        return store.read(oid, "blob")


def test_14_hand_built_pack_reader_accepts_a_wellformed_pack(tmp_path):
    root = tmp_path / "r"
    payload = b"hello pack\n" * 20
    oid = _sha(b"blob", payload)
    write_pack(root, [(oid, entry(3, payload))])
    assert read_blob(root, oid) == payload


def chain_pack(root: Path, depth: int, payload: bytes) -> str:
    items, offset = [(hashlib.sha1(b"base").hexdigest(), entry(3, payload))], 12
    offsets = [12]
    pos = 12 + len(items[0][1])
    for n in range(depth):
        delta = copy_all(len(payload))
        enc = vhdr(6, len(delta)) + ofs_enc(pos - offsets[-1]) + zlib.compress(delta)
        oid = _sha(b"blob", payload) if n == depth - 1 else hashlib.sha1(b"mid%d" % n).hexdigest()
        items.append((oid, enc))
        offsets.append(pos)
        pos += len(enc)
    write_pack(root, items)
    return items[-1][0]


def test_14_delta_chain_at_the_bound_resolves_and_beyond_it_is_refused(tmp_path):
    payload = b"chain payload\n" * 30
    root = tmp_path / "ok"
    oid = chain_pack(root, checkout.MAX_DELTA_DEPTH, payload)
    assert read_blob(root, oid) == payload
    root = tmp_path / "deep"
    oid = chain_pack(root, checkout.MAX_DELTA_DEPTH + 1, payload)
    with pytest.raises(ValueError):
        read_blob(root, oid)
    with checkout._ObjectStore(root) as store:
        with pytest.raises(ValueError, match="cyclic or too deep"):
            store.packs()[0].read(store.packs()[0].find(oid))


def test_14_ref_delta_to_an_unknown_base_is_refused(tmp_path):
    root = tmp_path / "r"
    payload = b"payload\n" * 10
    delta = copy_all(len(payload))
    oid = _sha(b"blob", payload)
    write_pack(root, [(oid, vhdr(7, len(delta)) + os.urandom(20) + zlib.compress(delta))])
    with checkout._ObjectStore(root) as store:
        with pytest.raises(ValueError, match="REF_DELTA base"):
            store.packs()[0].read(store.packs()[0].find(oid))
    with pytest.raises(ValueError):
        read_blob(root, oid)


def test_14_ref_delta_to_a_known_base_in_the_same_pack_resolves(tmp_path):
    root = tmp_path / "r"
    base = b"base payload\n" * 10
    base_id = _sha(b"blob", base)
    delta = copy_all(len(base), b"tail\n")
    out = base + b"tail\n"
    write_pack(root, [(base_id, entry(3, base)), (_sha(b"blob", out), vhdr(7, len(delta)) + bytes.fromhex(base_id) + zlib.compress(delta))])
    assert read_blob(root, _sha(b"blob", out)) == out


def test_14_delta_with_bad_instructions_is_refused(tmp_path):
    base = b"b" * 50
    for name, delta in {
        "copy outside base": dvar(50) + dvar(10) + bytes([0x91, 45, 10]),
        "result size mismatch": dvar(50) + dvar(10) + bytes([3]) + b"abc",
        "base size mismatch": dvar(49) + dvar(3) + bytes([3]) + b"abc",
        "reserved opcode": dvar(50) + dvar(3) + bytes([0]),
        "oversized result": dvar(50) + dvar(checkout.MAX_OBJECT_SIZE + 1) + bytes([1]) + b"a",
        "truncated insert": dvar(50) + dvar(5) + bytes([5]) + b"ab",
        "truncated header": b"\x80",
    }.items():
        with pytest.raises(ValueError):
            checkout._apply_delta(base, delta)


def mutate(path: Path, fn) -> None:
    path.write_bytes(fn(path.read_bytes()))


MALFORMED = {
    "pack truncated to half": lambda p, i: (p, lambda b: b[: len(b) // 2]),
    "pack truncated to header": lambda p, i: (p, lambda b: b[:12]),
    "pack empty": lambda p, i: (p, lambda b: b""),
    "pack bad magic": lambda p, i: (p, lambda b: b"XXXX" + b[4:]),
    "pack bad version": lambda p, i: (p, lambda b: b[:4] + struct.pack(">I", 9) + b[8:]),
    "pack count mismatch": lambda p, i: (p, lambda b: b[:8] + struct.pack(">I", 12345) + b[12:]),
    "pack entries zeroed": lambda p, i: (p, lambda b: b[:12] + b"\0" * (len(b) - 12)),
    "pack entries 0xff": lambda p, i: (p, lambda b: b[:12] + b"\xff" * (len(b) - 12)),
    "idx truncated": lambda p, i: (i, lambda b: b[: len(b) // 2]),
    "idx truncated to header": lambda p, i: (i, lambda b: b[:8]),
    "idx empty": lambda p, i: (i, lambda b: b""),
    "idx bad magic": lambda p, i: (i, lambda b: b"\xfftOd" + b[4:]),
    "idx version 1": lambda p, i: (i, lambda b: b[:4] + struct.pack(">I", 1) + b[8:]),
    "idx fanout non-monotonic": lambda p, i: (i, lambda b: b[:8 + 4 * 10] + struct.pack(">I", 99999) + b[8 + 4 * 11:]),
    "idx fanout huge": lambda p, i: (i, lambda b: b[:8 + 4 * 255] + struct.pack(">I", 0x7FFFFFFF) + b[8 + 4 * 256:]),
    "idx names zeroed": lambda p, i: (i, lambda b: b[:1032] + b"\0" * (len(b) - 1032)),
}


@pytest.mark.parametrize("case", sorted(MALFORMED))
def test_14_malformed_pack_or_index_refuses_deterministically(tmp_path, case):
    root, pin, anchors = build_repo(tmp_path, "packed")
    pack = next((root / ".git/objects/pack").glob("*.pack"))
    idx = pack.with_suffix(".idx")
    victim, edit = MALFORMED[case](pack, idx)
    victim.chmod(0o644)
    mutate(victim, edit)
    messages = set()
    for attempt in range(2):
        with pytest.raises(ValueError) as caught:
            materialize(root, pin, anchors, tmp_path / f"copy{attempt}")
        assert type(caught.value) is ValueError
        messages.add(str(caught.value))
    assert len(messages) == 1  # same refusal every time
    assert not (tmp_path / "copy0").exists() or not any((tmp_path / "copy0").iterdir())


def test_14_idx_offsets_pointing_outside_the_pack_are_refused(tmp_path):
    root = tmp_path / "r"
    payload = b"x" * 40
    oid = _sha(b"blob", payload)

    def bad_offset(idx: bytes) -> bytes:
        pos = 1032 + 20 + 4
        return idx[:pos] + struct.pack(">I", 10_000_000) + idx[pos + 4:]

    write_pack(root, [(oid, entry(3, payload))], idx_edit=bad_offset)
    with pytest.raises(ValueError):
        read_blob(root, oid)

    root2 = tmp_path / "r2"
    write_pack(root2, [(oid, entry(3, payload))], idx_edit=lambda idx: idx[:1032 + 20 + 4] + struct.pack(">I", 0x80000005) + idx[1032 + 20 + 8:])
    with pytest.raises(ValueError):
        read_blob(root2, oid)

    root3 = tmp_path / "r3"  # offset into the pack header
    write_pack(root3, [(oid, entry(3, payload))], idx_edit=lambda idx: idx[:1032 + 20 + 4] + struct.pack(">I", 4) + idx[1032 + 20 + 8:])
    with pytest.raises(ValueError):
        read_blob(root3, oid)


@pytest.mark.parametrize("case", ["truncated zlib", "bad adler", "wrong header size larger", "wrong header size smaller",
                                  "tag type", "unknown type 5", "ofs delta to itself", "ofs delta before pack"])
def test_14_malformed_pack_entries_are_refused(tmp_path, case):
    root = tmp_path / "r"
    payload = b"some payload bytes\n" * 8
    oid = _sha(b"blob", payload)
    z = zlib.compress(payload)
    enc = {
        "truncated zlib": vhdr(3, len(payload)) + z[: len(z) // 2],
        "bad adler": vhdr(3, len(payload)) + z[:-1] + bytes([z[-1] ^ 1]),
        "wrong header size larger": vhdr(3, len(payload) + 1) + z,
        "wrong header size smaller": vhdr(3, len(payload) - 1) + z,
        "tag type": vhdr(4, len(payload)) + z,
        "unknown type 5": vhdr(5, len(payload)) + z,
        "ofs delta to itself": vhdr(6, 3) + ofs_enc(1) + zlib.compress(b"\x00\x00\x00"),
        "ofs delta before pack": vhdr(6, 3) + ofs_enc(100) + zlib.compress(b"\x00\x00\x00"),
    }[case]
    write_pack(root, [(oid, enc)])
    if case == "truncated zlib":  # the pack ends right after the cut stream (trailer bytes follow): still never accepted
        pass
    with pytest.raises(ValueError):
        read_blob(root, oid)


@pytest.mark.parametrize("case", ["garbage", "truncated", "wrong header size", "wrong type", "trailing data", "no nul",
                                  "negative size", "leading zeros", "empty"])
def test_14_malformed_loose_objects_are_refused(loose, tmp_path, case):
    root, pin, anchors = loose
    target = blob_of(anchors, "utils/trust.py")
    genuine = subprocess.run(["git", "-C", str(root), "cat-file", "blob", target], check=True, capture_output=True).stdout
    good = b"blob %d\0" % len(genuine) + genuine
    data = {
        "garbage": b"not zlib at all" * 5,
        "truncated": zlib.compress(good)[:-6],
        "wrong header size": zlib.compress(b"blob %d\0" % (len(genuine) + 3) + genuine),
        "wrong type": zlib.compress(b"tree %d\0" % len(genuine) + genuine),
        "trailing data": zlib.compress(good) + b"junk",
        "no nul": zlib.compress(b"blob " + genuine),
        "negative size": zlib.compress(b"blob -1\0" + genuine),
        "leading zeros": zlib.compress(b"blob 0%d\0" % len(genuine) + genuine),
        "empty": b"",
    }[case]
    path = object_path(root, target)
    path.chmod(0o644)
    path.write_bytes(data)
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")


def test_14_non_regular_object_files_are_refused_without_blocking(loose, tmp_path):
    root, pin, anchors = loose
    path = object_path(root, blob_of(anchors, "utils/trust.py"))
    path.chmod(0o644)
    path.unlink()
    os.mkfifo(path)
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy")
    path.unlink()
    os.symlink("/dev/zero", path)
    with pytest.raises(ValueError):
        materialize(root, pin, anchors, tmp_path / "copy2")


def test_14_only_sha1_commit_tree_blob_are_accepted(loose):
    root, pin, anchors = loose
    with checkout._ObjectStore(root) as store:
        with pytest.raises(ValueError):
            store.read("0" * 64, "blob")
        with pytest.raises(ValueError):
            store.read(pin, "tag")
        with pytest.raises(ValueError):
            store.read(pin, "tree")  # right id, wrong type
        with pytest.raises(ValueError):
            store.read(pin.upper(), "commit")
    with pytest.raises(ValueError):
        checkout.verify_anchored(root, checkout.TrustedObjects("0" * 64, "1" * 64, ()))


@pytest.mark.parametrize("target", ["pack", "idx"])
def test_14_random_byte_corruption_never_yields_anything_but_genuine_bytes_or_valueerror(tmp_path, target):
    root, pin, anchors = build_repo(tmp_path, "ofs")
    pack = next((root / ".git/objects/pack").glob("*.pack"))
    victim = pack if target == "pack" else pack.with_suffix(".idx")
    original = victim.read_bytes()
    victim.chmod(0o644)
    rng = random.Random(20261103)
    for i in range(120):
        data = bytearray(original)
        for _ in range(rng.choice((1, 1, 2, 5))):
            data[rng.randrange(len(data))] = rng.randrange(256)
        victim.write_bytes(bytes(data))
        dest = tmp_path / f"c{i}"
        try:
            materialize(root, pin, anchors, dest)
        except ValueError:
            continue
        try:
            assert_exact(dest, anchors)  # a surviving flip hit unused bytes: result is still exactly authentic
        finally:
            unlock(dest)


def test_14_unusable_pack_next_to_a_good_one_does_not_hide_authentic_objects(tmp_path):
    root, pin, anchors = build_repo(tmp_path, "packed")
    pack_dir = root / ".git/objects/pack"
    (pack_dir / ("pack-" + "a" * 40 + ".idx")).write_bytes(b"junk")
    (pack_dir / ("pack-" + "a" * 40 + ".pack")).write_bytes(b"junk")
    dest = materialize(root, pin, anchors, tmp_path / "copy")
    try:
        assert_exact(dest, anchors)
    finally:
        unlock(dest)


def test_14_gitfile_indirection_is_not_followed(loose, tmp_path):
    root, pin, anchors = loose
    moved = tmp_path / "elsewhere"
    shutil.move(str(root / ".git"), moved)
    (root / ".git").write_text(f"gitdir: {moved}\n")
    with pytest.raises(ValueError, match="missing or not authentic"):
        materialize(root, pin, anchors, tmp_path / "copy")


# --------------------------------------------------------------------------------------------------------------------
# misc

def test_materialize_pinned_signature_and_public_api_are_unchanged():
    sig = inspect.signature(checkout.materialize_pinned)
    assert list(sig.parameters) == ["root", "pin", "dest", "anchors"]
    for name in ("checkout_problems", "verify_commit", "verified_tree_entries", "verify_anchored", "TrustedObjects", "materialize_pinned"):
        assert hasattr(checkout, name)
