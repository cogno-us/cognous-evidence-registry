"""The unused ZK placeholder must not accept anything (B-F9)."""
from app.core.security import ZKProofPlaceholder, zk_proof


def test_verify_proof_is_fail_closed():
    generated = ZKProofPlaceholder.generate_proof({"claim": "c"})
    assert ZKProofPlaceholder.verify_proof(generated, {}) is False
    assert zk_proof.verify_proof("zk_proof_placeholder_anything", {"x": 1}) is False
    assert zk_proof.verify_proof("", {}) is False
