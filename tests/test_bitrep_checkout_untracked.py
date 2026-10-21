"""Untracked content the clean-checkout gate must see: nested repositories, symlinks, ignored files, __pycache__ (scan5 C-T1-4)."""
from __future__ import annotations

import os

import pytest

from test_bitrep_checkout import checkout, fake_bitrep, git, problems  # noqa: F401  (fixture reused)



def test_untracked_nested_repo_directory_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    evil = root / "evil"
    evil.mkdir()
    git(evil, "init", "-q")
    (evil / "__init__.py").write_text("print('pwn')\n")
    found = problems(root, pin)
    assert any("nested git repository: evil" in p for p in found)
    assert any("importable file: evil/__init__.py" in p for p in found)


@pytest.mark.parametrize("name", ["pydantic", "cryptography"])
def test_nested_repo_named_like_a_dependency_is_refused(fake_bitrep, name):
    root, pin = fake_bitrep
    shadow = root / name
    shadow.mkdir()
    git(shadow, "init", "-q")
    (shadow / "__init__.py").write_text("")
    assert any(f"nested git repository: {name}" in p for p in problems(root, pin))


def test_nested_repo_without_importable_files_is_still_refused(fake_bitrep):
    root, pin = fake_bitrep
    (root / "data").mkdir()
    git(root / "data", "init", "-q")
    assert any("nested git repository: data" in p for p in problems(root, pin))


def test_importable_file_inside_nested_dot_git_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    nested = root / "vendor" / "inner"
    nested.mkdir(parents=True)
    git(nested, "init", "-q")
    (nested / ".git" / "sneaky.py").write_text("x = 1\n")
    assert any("importable file: vendor/inner/.git/sneaky.py" in p for p in problems(root, pin))


def test_gitfile_style_nested_repo_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    (root / "wt").mkdir()
    (root / "wt" / ".git").write_text("gitdir: ../elsewhere\n")
    assert any("nested git repository: wt" in p for p in problems(root, pin))


def test_untracked_symlinked_directory_is_refused(fake_bitrep, tmp_path):
    root, pin = fake_bitrep
    outside = tmp_path / "outside_pkg"
    outside.mkdir()
    (outside / "__init__.py").write_text("")
    os.symlink(outside, root / "pydantic")
    assert any("symlink: pydantic" in p for p in problems(root, pin))


def test_untracked_symlink_to_file_without_importable_name_is_refused(fake_bitrep, tmp_path):
    root, pin = fake_bitrep
    target = tmp_path / "t.txt"
    target.write_text("x")
    os.symlink(target, root / "link")
    assert any("symlink: link" in p for p in problems(root, pin))


def test_dangling_untracked_symlink_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    os.symlink(root / "nope", root / "dangling")
    assert any("symlink: dangling" in p for p in problems(root, pin))


def test_symlink_is_not_followed_into_outside_tree(fake_bitrep, tmp_path):
    root, pin = fake_bitrep
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big.py").write_text("")
    os.symlink(outside, root / "ln")
    found = problems(root, pin)
    assert found == ["untracked or ignored symlink: ln"]


@pytest.mark.parametrize("rel", ["ignored_dir/deep/er/hidden.py", "utils/lib.so", "utils/ext.pyd"])
def test_ignored_importable_files_are_refused(fake_bitrep, rel):
    root, pin = fake_bitrep
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    assert any(rel in p for p in problems(root, pin))


@pytest.mark.parametrize("name", ["evil.py", "evil.so", "evil.pyw", "evil.pyd"])
def test_importable_source_under_pycache_is_refused(fake_bitrep, name):
    root, pin = fake_bitrep
    cache = root / "utils" / "__pycache__"
    cache.mkdir()
    (cache / name).write_text("x = 1\n")
    assert any(f"utils/__pycache__/{name}" in p for p in problems(root, pin))


def test_only_pyc_is_tolerated_under_pycache(fake_bitrep):
    root, pin = fake_bitrep
    cache = root / "utils" / "__pycache__"
    cache.mkdir()
    (cache / "verification.cpython-312.pyc").write_bytes(b"\0")
    (cache / "notes.txt").write_text("n")
    assert problems(root, pin) == []


def test_nested_repo_under_pycache_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    cache = root / "__pycache__" / "pkg"
    cache.mkdir(parents=True)
    git(cache, "init", "-q")
    assert any("nested git repository: __pycache__/pkg" in p for p in problems(root, pin))


def test_clean_checkout_with_tracked_symlink_and_empty_dir_passes(fake_bitrep):
    root, pin = fake_bitrep
    (root / "empty").mkdir()
    assert problems(root, pin) == []


def test_tracked_symlink_in_pinned_tree_is_not_reported(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    (root / "a.py").write_text("")
    os.symlink("a.py", root / "alias.py")
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "p")
    assert checkout.checkout_problems(root, git(root, "rev-parse", "HEAD").strip()) == []
