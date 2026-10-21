"""The clean-checkout gate trusts the pinned tree, not the index (scan6 F1). Hermetic throwaway repositories."""
from __future__ import annotations

from test_bitrep_checkout import checkout, fake_bitrep, git, problems  # noqa: F401  (fixture reused)


def test_staged_but_uncommitted_importable_file_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    (root / "evil.py").write_text("print('pwn')\n")
    git(root, "add", "evil.py")
    found = problems(root, pin)
    assert any("importable file: evil.py" in p for p in found)
    assert any("staged change: evil.py" in p for p in found)


def test_intent_to_add_file_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    (root / "evil.py").write_text("x = 1\n")
    git(root, "add", "-N", "evil.py")
    assert any("importable file: evil.py" in p for p in problems(root, pin))


def test_staged_edit_of_tracked_file_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    target = root / "utils" / "verification.py"
    target.write_text("def verify(sig):\n    return True\n")
    git(root, "add", "utils/verification.py")
    found = problems(root, pin)
    assert any("staged change: utils/verification.py" in p for p in found)
    assert any("content differs from the revision: utils/verification.py" in p for p in found)


def test_staged_deletion_is_refused(fake_bitrep):
    root, pin = fake_bitrep
    git(root, "rm", "-q", "models/__init__.py")
    assert any("staged change: models/__init__.py" in p for p in problems(root, pin))


def test_clean_checkout_is_still_accepted(fake_bitrep):
    root, pin = fake_bitrep
    assert problems(root, pin) == []
