"""R1-B: source verification never runs repository-controlled git machinery and imports only authenticated bytes.

Hermetic: throwaway git repositories, no network, no real BitRep. Findings csf_612ced4ef93a62df3d54b797 (HIGH) and
csf_db3f244ab2fd16c3a657eb5d (MEDIUM).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from test_bitrep_checkout import MODULE, checkout, fake_bitrep, git, problems  # noqa: F401  (fixture reused)

ADAPTER = MODULE.with_name("bitrep_adapter.py")


def anchors_for(root: Path, pin: str):
    """Trusted anchors for a throwaway stand-in repository, derived by the same tool used for the real pin (R1-B2)."""
    tree = checkout.verify_commit(root, pin)
    return checkout.TrustedObjects(pin, tree, tuple(checkout.verified_tree_entries(root, tree)))


def anchors_module_text(root: Path, pin: str) -> str:
    try:
        a = anchors_for(root, pin)
    except Exception:  # unknown pin: anchors that cannot match anything
        return f'COMMIT = "{pin}"\nTREE = "{"0" * 40}"\nFILES = ()\n'
    return f'COMMIT = "{a.commit}"\nTREE = "{a.tree}"\nFILES = {a.files!r}\n'

VERIFY_V1 = "def verify(sig):\n    return sig == b'valid'\n"

STUBS = {
    "models/verification.py": "class AttestationEnvelope:\n    pass\n",
    "utils/trust.py": "class TrustRegistry:\n    pass\n\n\ndef strict_json(raw):\n    return raw\n",
    "utils/verification.py": (
        "def statement_digest(s):\n    return s\n\n\ndef verify_attestation(a, r, n):\n    return None\n\n\n"
        "def lazy():\n    import models.lazy_mod as m\n    return m.VALUE, m.__file__\n"
    ),
    "models/lazy_mod.py": "VALUE = 'pinned'\n",
}


def install_marker_filter(root: Path, marker: Path, *, via: str = "config") -> None:
    """A clean filter that touches ``marker`` and always emits a fixed (attacker-chosen) stream."""
    script = root.parent / "evil_filter.sh"
    script.write_text(f"#!/bin/sh\ncat >/dev/null\ntouch '{marker}'\nprintf '%s' \"$FILTER_OUT\"\n")
    script.chmod(0o755)
    git(root, "config", "filter.evil.clean", str(script))
    git(root, "config", "filter.evil.required", "true")
    attrs = "*.py filter=evil\n"
    if via == "gitattributes":
        (root / ".gitattributes").write_text(attrs)
    else:
        (root / ".git" / "info").mkdir(exist_ok=True)
        (root / ".git" / "info" / "attributes").write_text(attrs)


@pytest.fixture()
def stub_bitrep(tmp_path):
    root = tmp_path / "bitrep"
    for rel, text in STUBS.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    for pkg in ("models", "utils"):
        (root / pkg / "__init__.py").write_text("")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "pinned")
    return root, git(root, "rev-parse", "HEAD").strip()


def run_adapter(root: Path, pin: str, body: str, tmp_path: Path, env_extra: dict | None = None, preamble: str = ""):
    """Run a copy of the real adapter (only PIN substituted) in a fresh interpreter; ``body`` runs after the import."""
    work = tmp_path / "adapter_copy"
    work.mkdir(exist_ok=True)
    source = ADAPTER.read_text(encoding="utf-8")
    prod = 'PIN = "981036c315856c71207984797b0c4e48d3b3921d"'
    assert prod in source
    (work / "bitrep_adapter.py").write_text(source.replace(prod, f'PIN = "{pin}"'), encoding="utf-8")
    (work / "bitrep_checkout.py").write_text(MODULE.read_text(encoding="utf-8"), encoding="utf-8")
    (work / "bitrep_trusted_objects.py").write_text(anchors_module_text(root, pin), encoding="utf-8")
    (work / "runner.py").write_text(f"import sys\nsys.path.insert(0, {str(work)!r})\n" + textwrap.dedent(preamble) + "import bitrep_adapter as a\n" + textwrap.dedent(body), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(BITREP_ROOT=str(root), PYTHONPATH="", **(env_extra or {}))
    return subprocess.run([sys.executable, "-I", str(work / "runner.py")], cwd=work, env=env, text=True,
                          capture_output=True, timeout=60, check=False)


# 1-3: a clean filter configured in the local repository must neither run nor satisfy verification -----------------

def tamper_and_filter(root, marker, via):
    target = root / "utils" / "verification.py"
    target.write_text("def verify(sig):\n    return True\n")
    install_marker_filter(root, marker, via=via)
    return target


@pytest.mark.parametrize("via", ["gitattributes", "info-attributes"])
def test_clean_filter_is_never_executed_and_marker_is_not_created(fake_bitrep, tmp_path, via, monkeypatch):
    root, pin = fake_bitrep
    marker = tmp_path / "MARKER"
    monkeypatch.setenv("FILTER_OUT", VERIFY_V1)
    target = tamper_and_filter(root, marker, "gitattributes" if via == "gitattributes" else "info")
    found = problems(root, pin)
    assert not marker.exists(), "repository-controlled clean filter ran during verification"
    assert "content differs from the revision: utils/verification.py" in found
    assert target.read_text().endswith("return True\n")


def test_filter_emitting_the_correct_blob_cannot_launder_a_tampered_file(fake_bitrep, tmp_path, monkeypatch):
    """Test 4: tampered file + filter that prints exactly the pinned bytes must still be refused."""
    root, pin = fake_bitrep
    marker = tmp_path / "MARKER"
    monkeypatch.setenv("FILTER_OUT", VERIFY_V1)
    tamper_and_filter(root, marker, "gitattributes")
    assert "content differs from the revision: utils/verification.py" in problems(root, pin)
    assert not marker.exists()


def test_gitattributes_attack_with_text_eol_cannot_hide_crlf_edit(fake_bitrep):
    """Test 5: ``text eol=crlf``-style attributes must not make a mutated file look like the blob."""
    root, pin = fake_bitrep
    (root / ".gitattributes").write_text("* text eol=lf\n*.py text=auto eol=crlf\n")
    (root / "utils" / "verification.py").write_bytes(VERIFY_V1.replace("\n", "\r\n").encode())
    found = problems(root, pin)
    assert "content differs from the revision: utils/verification.py" in found


def test_info_attributes_attack_with_ident_or_eol_is_refused(fake_bitrep):
    """Test 6."""
    root, pin = fake_bitrep
    (root / ".git" / "info").mkdir(exist_ok=True)
    (root / ".git" / "info" / "attributes").write_text("*.py text eol=lf\n")
    (root / "utils" / "verification.py").write_bytes(VERIFY_V1.replace("\n", "\r\n").encode())
    assert "content differs from the revision: utils/verification.py" in problems(root, pin)


def test_global_system_and_local_filter_config_cannot_influence_verification(fake_bitrep, tmp_path, monkeypatch):
    """Test 7: filters in GIT_CONFIG_GLOBAL, GIT_CONFIG_SYSTEM, $HOME/.gitconfig and local config are all inert."""
    root, pin = fake_bitrep
    marker = tmp_path / "MARKER"
    script = tmp_path / "f.sh"
    script.write_text(f"#!/bin/sh\ncat >/dev/null\ntouch '{marker}'\nprintf '%s' \"$FILTER_OUT\"\n")
    script.chmod(0o755)
    cfg = tmp_path / "evil.gitconfig"
    cfg.write_text(f"[filter \"evil\"]\n\tclean = {script}\n\trequired = true\n[core]\n\tfsmonitor = {script}\n"
                   f"\thooksPath = {tmp_path}\n[alias]\n\trev-parse = !touch {marker}\n")
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text(cfg.read_text())
    monkeypatch.setenv("FILTER_OUT", VERIFY_V1)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "filter.evil.clean")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", str(script))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nonexistent-git-dir"))
    (root / ".gitattributes").write_text("*.py filter=evil\n")
    git_local = ["git", "-C", str(root), "config", "core.fsmonitor", str(script)]
    subprocess.run(git_local, check=True, env={**{k: v for k, v in os.environ.items() if k != "GIT_DIR"}, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull})
    (root / "utils" / "verification.py").write_text("def verify(sig):\n    return True\n")
    found = problems(root, pin)
    assert not marker.exists()
    assert "content differs from the revision: utils/verification.py" in found
    # And a pristine checkout still verifies under the same hostile ambient configuration.
    (root / "utils" / "verification.py").write_text(VERIFY_V1)
    assert problems(root, pin) == []
    assert not marker.exists()


def test_every_git_invocation_is_hardened(monkeypatch, fake_bitrep):
    root, pin = fake_bitrep
    calls = []
    real = subprocess.run

    def spy(cmd, *a, **kw):
        calls.append((cmd, kw.get("env")))
        return real(cmd, *a, **kw)

    monkeypatch.setattr(checkout.subprocess, "run", spy)
    monkeypatch.setenv("GIT_DIR", "/nonexistent")
    checkout.checkout_problems(root, pin)
    checkout.materialize_pinned(root, pin, anchors=anchors_for(root, pin))
    assert calls
    for cmd, env in calls:
        assert "--no-replace-objects" in cmd and "core.fsmonitor=false" in cmd
        assert f"core.hooksPath={os.devnull}" in cmd and f"core.attributesFile={os.devnull}" in cmd
        assert env["GIT_CONFIG_NOSYSTEM"] == "1" and env["GIT_CONFIG_GLOBAL"] == os.devnull
        assert not any(k in env for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"))
        assert "hash-object" not in cmd, "no command that can apply filters may be used"


# 8-10: detached authenticated copy ------------------------------------------------------------------------------------

def test_untracked_shadow_module_cannot_affect_import_resolution(stub_bitrep, tmp_path):
    root, pin = stub_bitrep
    (root / "models" / "lazy_mod.py").write_text("VALUE = 'tracked-edit'\n")  # tracked edit, would be refused by check
    (root / "json.py").write_text("raise SystemExit('shadow executed')\n")
    (root / "sitecustomize.py").write_text("raise SystemExit('shadow executed')\n")
    (root / "utils" / "trust2.py").write_text("raise SystemExit('shadow executed')\n")
    (root / "models" / "verification.pyc").write_bytes(b"junk")
    done = run_adapter(root, pin, "print(a.verify_attestation.__module__)\nprint(a.verify_attestation.__globals__['lazy']()[0])\n", tmp_path)
    assert done.returncode == 0, done.stderr
    assert "shadow" not in done.stdout + done.stderr
    assert done.stdout.split()[-1] == "pinned"


def test_mutation_after_verification_does_not_change_executed_bytes(stub_bitrep, tmp_path):
    """Tests 9 and 10: post-load edits, deletion and shadowing in the original checkout cannot reach lazy imports."""
    root, pin = stub_bitrep
    body = f"""
    import hashlib, pathlib, sys
    root = pathlib.Path({str(root)!r})
    (root / 'models' / 'lazy_mod.py').write_text("VALUE = 'MUTATED'\\n")
    (root / 'models' / 'verification.py').write_text("raise SystemExit('mutated verification executed')\\n")
    (root / 'utils' / 'extra.py').write_text("raise SystemExit('shadow')\\n")
    value, path = a.verify_attestation.__globals__['lazy']()
    print('VALUE', value)
    print('FILE', path)
    detached = pathlib.Path(path).resolve()
    assert not detached.is_relative_to(root.resolve()), 'imported from mutable checkout'
    import os
    for rel in ('models/verification.py', 'utils/trust.py', 'utils/verification.py', 'models/lazy_mod.py'):
        print('SRC', rel, pathlib.Path(path).parent.parent.joinpath(rel).read_bytes().hex())
    print('ROOTS', [p for p in sys.path if p.startswith(str(root))])
    """
    done = run_adapter(root, pin, body, tmp_path)
    assert done.returncode == 0, done.stderr
    assert "VALUE pinned" in done.stdout
    assert "ROOTS []" in done.stdout
    # Test 10: executed bytes are exactly the pinned objects.
    file_line = next(line for line in done.stdout.splitlines() if line.startswith("FILE "))
    detached_dir = Path(file_line[5:]).parent.parent
    seen = {l.split()[1]: bytes.fromhex(l.split()[2]) for l in done.stdout.splitlines() if l.startswith("SRC ")}
    assert set(seen) == {"models/verification.py", "utils/trust.py", "utils/verification.py", "models/lazy_mod.py"}
    for rel, got in seen.items():
        blob_id = git(root, "rev-parse", f"{pin}:{rel}").strip()
        assert hashlib.sha1(b"blob %d\0" % len(got) + got).hexdigest() == blob_id, rel  # executed bytes == pinned object
    assert not detached_dir.exists()  # private copy removed at interpreter exit


def test_materialized_copy_equals_pinned_objects_byte_for_byte(stub_bitrep, tmp_path):
    root, pin = stub_bitrep
    (root / "models" / "lazy_mod.py").write_bytes(b"VALUE = 'x'\r\n")  # worktree differs; irrelevant to the copy
    dest = checkout.materialize_pinned(root, pin, dest=tmp_path / "copy", anchors=anchors_for(root, pin))
    try:
        for rel, text in STUBS.items():
            assert (dest / rel).read_bytes() == text.encode()
        assert not (dest / ".git").exists()
        assert (dest / "models" / "lazy_mod.py").stat().st_mode & 0o222 == 0
    finally:
        for here, dirs, _ in os.walk(dest):
            for d in dirs:
                os.chmod(os.path.join(here, d), 0o700)
        os.chmod(dest, 0o700)


def test_materialize_ignores_filters_and_marker_is_not_created(stub_bitrep, tmp_path, monkeypatch):
    root, pin = stub_bitrep
    marker = tmp_path / "MARKER"
    monkeypatch.setenv("FILTER_OUT", "EVIL")
    install_marker_filter(root, marker, via="gitattributes")
    dest = checkout.materialize_pinned(root, pin, dest=tmp_path / "copy", anchors=anchors_for(root, pin))
    assert (dest / "models" / "lazy_mod.py").read_text() == STUBS["models/lazy_mod.py"]
    assert not marker.exists()


def test_materialize_refuses_non_commit_and_replaced_objects(stub_bitrep, tmp_path):
    root, pin = stub_bitrep
    with pytest.raises(ValueError):
        checkout.materialize_pinned(root, "HEAD", dest=tmp_path / "a", anchors=anchors_for(root, pin))
    tree = git(root, "rev-parse", f"{pin}^{{tree}}").strip()
    with pytest.raises(ValueError):
        checkout.materialize_pinned(root, tree, dest=tmp_path / "b", anchors=anchors_for(root, pin))
    # replace ref pointing the pinned lazy_mod blob at different content must not redirect the copy
    evil = subprocess.run(["git", "-C", str(root), "hash-object", "-w", "--stdin"], input="VALUE = 'replaced'\n",
                          text=True, capture_output=True, check=True,
                          env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull}).stdout.strip()
    good = git(root, "rev-parse", f"{pin}:models/lazy_mod.py").strip()
    git(root, "replace", good, evil)
    dest = checkout.materialize_pinned(root, pin, dest=tmp_path / "c", anchors=anchors_for(root, pin))
    assert (dest / "models" / "lazy_mod.py").read_text() == STUBS["models/lazy_mod.py"]


# 11: CRLF policy -----------------------------------------------------------------------------------------------------

def test_crlf_mutated_tracked_file_is_refused_by_checkout_check(fake_bitrep):
    root, pin = fake_bitrep
    (root / "utils" / "verification.py").write_bytes(VERIFY_V1.replace("\n", "\r\n").encode())
    git(root, "config", "core.autocrlf", "true")
    assert "content differs from the revision: utils/verification.py" in problems(root, pin)


def test_crlf_mutated_checkout_executes_only_the_lf_pinned_bytes_from_the_detached_copy(stub_bitrep, tmp_path):
    root, pin = stub_bitrep
    git(root, "config", "core.autocrlf", "true")
    (root / "models" / "lazy_mod.py").write_bytes(b"VALUE = 'pinned'\r\n")
    assert "content differs from the revision: models/lazy_mod.py" in problems(root, pin)
    done = run_adapter(root, pin, "print('OUT', a.verify_attestation.__globals__['lazy']()[0])\n", tmp_path)
    assert done.returncode == 0, done.stderr
    assert "OUT pinned" in done.stdout
    # the detached bytes are LF: the interpreter would have reported a SyntaxError-free but different file otherwise
    copy = checkout.materialize_pinned(root, pin, dest=tmp_path / "crlfcopy", anchors=anchors_for(root, pin))
    assert (copy / "models" / "lazy_mod.py").read_bytes() == b"VALUE = 'pinned'\n"


# 12: legitimate pinned checkout ---------------------------------------------------------------------------------------

def test_legitimate_pinned_checkout_still_verifies_and_loads(stub_bitrep, tmp_path):
    root, pin = stub_bitrep
    assert problems(root, pin) == []
    done = run_adapter(root, pin, "print('OK', a.Envelope.__name__, a.Registry.__name__)\n", tmp_path)
    assert done.returncode == 0, done.stderr
    assert "OK AttestationEnvelope TrustRegistry" in done.stdout


def test_wrong_pin_cannot_be_loaded(stub_bitrep, tmp_path):
    root, _ = stub_bitrep
    done = run_adapter(root, "0" * 40, "print('loaded')\n", tmp_path)
    assert done.returncode != 0 and "loaded" not in done.stdout
