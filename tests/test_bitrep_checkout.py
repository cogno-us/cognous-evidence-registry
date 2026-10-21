"""The BitRep checkout check compares file content with the pinned commit, not what ``git status`` reports (B-F3).

Hermetic: every case builds a throwaway git repository holding a tiny stand-in for BitRep. No network, no real BitRep
clone. The production pin is untouched; the check takes the pin as an argument.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "chain" / "python" / "bitrep_checkout.py"
spec = importlib.util.spec_from_file_location("bitrep_checkout_under_test", MODULE)
checkout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkout)

PRODUCTION_PIN = "981036c315856c71207984797b0c4e48d3b3921d"


def git(root: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
    return subprocess.run(["git", "-C", str(root), *args], check=True, text=True, capture_output=True, env=env).stdout


@pytest.fixture()
def fake_bitrep(tmp_path):
    root = tmp_path / "bitrep"
    (root / "utils").mkdir(parents=True)
    (root / "models").mkdir()
    (root / ".gitignore").write_text("__pycache__/\n*.py[cod]\n*.so\nignored_dir/\n")
    (root / "utils" / "__init__.py").write_text("")
    (root / "utils" / "verification.py").write_text("def verify(sig):\n    return sig == b'valid'\n")
    (root / "models" / "__init__.py").write_text("")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "pinned")
    pin = git(root, "rev-parse", "HEAD").strip()
    return root, pin


def problems(root, pin):
    return checkout.checkout_problems(root, pin)


def test_clean_pinned_checkout_has_no_problems(fake_bitrep):
    root, pin = fake_bitrep
    assert problems(root, pin) == []


def test_head_that_is_not_the_pin_is_refused(fake_bitrep):
    root, _ = fake_bitrep
    assert any("is not the pin" in p for p in problems(root, "0" * 40))


def test_production_pin_is_unchanged():
    source = (MODULE.with_name("bitrep_adapter.py")).read_text(encoding="utf-8")
    assert f'PIN = "{PRODUCTION_PIN}"' in source


def test_skip_worktree_hidden_edit_is_refused_although_git_status_is_clean(fake_bitrep):
    """The r8 reproduction: the edit is invisible to ``git status`` but the verifier bytes differ from the pin."""
    root, pin = fake_bitrep
    target = root / "utils" / "verification.py"
    git(root, "update-index", "--skip-worktree", "utils/verification.py")
    target.write_text("def verify(sig):\n    return True\n")
    assert git(root, "status", "--porcelain", "--untracked-files=normal").strip() == ""
    found = problems(root, pin)
    assert "index flag hides modifications: utils/verification.py" in found
    assert "content differs from the revision: utils/verification.py" in found


def test_assume_unchanged_hidden_edit_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    git(root, "update-index", "--assume-unchanged", "utils/verification.py")
    (root / "utils" / "verification.py").write_text("def verify(sig):\n    return True\n")
    assert git(root, "status", "--porcelain").strip() == ""
    found = problems(root, pin)
    assert any(p.startswith("index flag hides modifications") for p in found)
    assert any(p.startswith("content differs from the revision") for p in found)


def test_flag_alone_without_an_edit_is_still_refused(fake_bitrep):
    root, pin = fake_bitrep
    git(root, "update-index", "--skip-worktree", "utils/verification.py")
    assert problems(root, pin) == ["index flag hides modifications: utils/verification.py"]


def test_visible_edit_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    (root / "utils" / "verification.py").write_text("changed\n")
    assert problems(root, pin) == ["content differs from the revision: utils/verification.py"]


def test_deleted_tracked_file_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    (root / "utils" / "verification.py").unlink()
    assert problems(root, pin) == ["content differs from the revision: utils/verification.py"]


@pytest.mark.parametrize("rel", ["json.py", "utils/shadow.py", "ignored_dir/hidden.py", "utils/native.so", "stale.pyc"])
def test_untracked_or_ignored_importable_file_is_refused(fake_bitrep, rel):
    root, pin = fake_bitrep
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x = 1\n")
    assert any(p.startswith("untracked or ignored importable file") and rel in p for p in problems(root, pin))


def test_bytecode_cache_directory_alone_is_not_a_problem(fake_bitrep):
    root, pin = fake_bitrep
    cache = root / "utils" / "__pycache__"
    cache.mkdir()
    (cache / "verification.cpython-312.pyc").write_bytes(b"\0")
    assert problems(root, pin) == []


def test_non_importable_untracked_file_is_not_a_problem(fake_bitrep):
    root, pin = fake_bitrep
    (root / "notes.txt").write_text("n")
    assert problems(root, pin) == []
