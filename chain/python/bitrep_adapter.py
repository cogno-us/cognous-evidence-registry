"""Index-side binding checks; cryptographic decisions delegated to pinned BitRep.

Run in an isolated Python process because upstream uses top-level models/utils.
The caller is an independent verifier, NOT an on-chain proof producer.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PIN = "5b5077dafde232a7801cb425c4efddcffb468723"


def load_bitrep():
    root = Path(os.environ["BITREP_ROOT"]).resolve()
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=normal"], text=True
    ).strip()
    if head != PIN or dirty:
        raise ValueError("BitRep checkout must be clean and pinned")
    sys.path.insert(0, str(root))
    from models.verification import AttestationEnvelope
    from utils.trust import TrustRegistry, strict_json
    from utils.verification import statement_digest, verify_attestation

    return AttestationEnvelope, TrustRegistry, strict_json, statement_digest, verify_attestation


Envelope, Registry, strict_json, statement_digest, verify_attestation = load_bitrep()


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def evaluate(raw, content, expected, registry, trusted_snapshot_digest, now):
    """Explicit evaluation time for deterministic *tests/reproduction*, not signing time proof.

    CLI always supplies current local time. Expected bindings must come from independently
    reconstructed chain data and local policy; never from the untrusted envelope itself.
    trusted_snapshot_digest must be authenticated out of band, not copied from a result.
    """
    if len(raw) > 16384:
        raise ValueError("input_too_large")
    att = Envelope.model_validate(strict_json(raw))
    if registry.fingerprint() != trusted_snapshot_digest:
        raise ValueError("untrusted snapshot")
    if content is None:
        raise ValueError("evidence unavailable")
    actual = digest(content)
    if actual != expected["content_digest"] or actual != att.statement.content_digest:
        raise ValueError("content commitment mismatch")
    for field in ("subject", "statement_type", "audience"):
        if getattr(att.statement, field) != expected[field]:
            raise ValueError(f"{field} mismatch")
    if statement_digest(att.statement) != expected["statement_digest"]:
        raise ValueError("statement digest mismatch")
    if registry.audience != expected["audience"]:
        raise ValueError("trust audience mismatch")
    result = verify_attestation(att, registry, now)
    # Never accept externally supplied verification JSON.
    if result.result_version != "bitrep-verification/1":
        raise ValueError("unsupported result")
    return result.model_dump()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestation", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--trust", required=True)
    parser.add_argument("--trust-digest", required=True)
    args = parser.parse_args()
    result = evaluate(
        Path(args.attestation).read_bytes(),
        Path(args.content).read_bytes(),
        strict_json(Path(args.expected).read_bytes()),
        Registry.model_validate(strict_json(Path(args.trust).read_bytes())),
        args.trust_digest,
        int(time.time()),
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "verified" else 1


if __name__ == "__main__":
    sys.exit(main())
