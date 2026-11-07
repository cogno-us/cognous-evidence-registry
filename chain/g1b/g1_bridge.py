"""G1b DEVELOPMENT-ONLY bridge to the merged G1 Verifier-result attestation profile.

Not a verifier of record and not chain-bound. It reuses, without copying, the Registry's authenticated BitRep
loader (adapter PIN) and the merged G1 profile file (`profiles/verifier_result.py`, blob-pinned below) so the
signature/binding checks are the native ones. `make-envelope` uses G1's own builder and its TEST-SCOPE signing
helper with a fresh in-memory key and a per-run synthetic trust snapshot; nothing is persisted except the files
the caller asks for. Results mean `issuer_signature_only` under the supplied snapshot, observer-relative.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
import types
from pathlib import Path

G1_REVISION = "b7d23dc7fa30359f129481149d0fdd3405dbf1b1"
G1_BLOBS = {  # git blob ids at G1_REVISION; the files are re-hashed before they are executed
    "profiles/verifier_result.py": "2e4377139251e2f08b93627ce20fe10fb2d007ed",
    "tests/verifier_result_signing.py": "13b8e2cc3811981ea9ae504bed5f36d3011a2dc1",
}


def _git_blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\x00" % len(data) + data).hexdigest()  # noqa: S324 - git object id, not security


def _load_pinned(root: Path, rel: str, name: str):
    data = (root / rel).read_bytes()
    if _git_blob_id(data) != G1_BLOBS[rel]:
        raise ValueError(f"G1 file is not the pinned blob: {rel}")
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__file__ = str(root / rel)
    sys.modules[name] = module
    exec(compile(data, str(root / rel), "exec"), module.__dict__)  # noqa: S102 - blob-pinned reviewed source
    return module


def load():
    """(adapter module, G1 profile module, G1 signing helper module)."""
    here = Path(__file__).resolve().parent.parent / "python"
    sys.path.insert(0, str(here))
    import bitrep_adapter  # authenticates BitRep at its PIN from BITREP_ROOT git objects

    root = Path(os.environ["G1_ROOT"]).resolve()
    sys.modules.setdefault("profiles", types.ModuleType("profiles"))
    profile = _load_pinned(root, "profiles/verifier_result.py", "profiles.verifier_result")
    helper = _load_pinned(root, "tests/verifier_result_signing.py", "verifier_result_signing")
    return bitrep_adapter, profile, helper


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def make_envelope(report: Path, out: Path, revision: str) -> dict:
    adapter, profile, helper = load()
    now = int(time.time())
    raw = report.read_bytes()
    statement = profile.build_unsigned_statement(
        raw, verifier_revision=revision, issuer=helper.ISSUER, key_id=helper.KEY_ID, now=now
    )
    key, trust = helper.ephemeral_signer(now)  # fresh in-memory key; discarded when this process exits
    envelope = helper.sign(key, statement)
    out.mkdir(parents=True, exist_ok=True)
    env_bytes, trust_bytes = _canon(envelope), _canon(trust)
    (out / "envelope.json").write_bytes(env_bytes)
    (out / "trust.json").write_bytes(trust_bytes)
    return {"envelope_sha256": adapter.digest(env_bytes), "statement_digest": adapter.statement_digest(statement),
            "issued_at": now, "g1_revision": G1_REVISION}


def verify(report: Path | None, envelope: Path, trust: Path, now: int) -> dict:
    adapter, profile, _ = load()
    raw = report.read_bytes() if report is not None else None
    env = adapter.Envelope.model_validate(adapter.strict_json(envelope.read_bytes()))
    registry = adapter.Registry.model_validate(adapter.strict_json(trust.read_bytes()))
    base = {"g1_revision": G1_REVISION, "snapshot_fingerprint": registry.fingerprint(),
            "statement_digest": adapter.statement_digest(env.statement),
            "envelope_sha256": adapter.digest(envelope.read_bytes()), "evaluated_at": now,
            "report_sha256": adapter.digest(raw) if raw is not None else None}
    if raw is None:
        return {**base, "accepted": False, "reason": "report_unavailable", "assurance": "none"}
    try:
        facts = profile.parse_report(raw)
        subject = facts.subject_digest
    except profile.ProfileRefusal as exc:
        return {**base, "accepted": False, "reason": exc.reason, "assurance": "none"}
    result = profile.verify_verifier_result(raw, env, registry, now)
    return {**base, "accepted": result.accepted, "reason": result.reason, "assurance": result.assurance,
            "native_outcome": result.native_outcome, "report_overall": result.report_overall,
            "report_subject_digest": subject,
            "verifier_revision_asserted": result.verifier_revision_asserted,
            "statement_type": env.statement.statement_type, "audience": env.statement.audience,
            "report_execution_absent": list(result.report_execution_absent)}


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make-envelope")
    m.add_argument("--report", required=True), m.add_argument("--out", required=True)
    m.add_argument("--revision", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--report"), v.add_argument("--envelope", required=True)
    v.add_argument("--trust", required=True), v.add_argument("--now", type=int, required=True)
    a = p.parse_args()
    if a.cmd == "make-envelope":
        out = make_envelope(Path(a.report), Path(a.out), a.revision)
    else:
        out = verify(Path(a.report) if a.report else None, Path(a.envelope), Path(a.trust), a.now)
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
