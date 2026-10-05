"""Synthetic, reproducible tests. Fixed time is NOT a production current-time result."""

import base64
import json
import os
import unittest
from copy import deepcopy
from pathlib import Path

from bitrep_adapter import Envelope, Registry, digest, evaluate, statement_digest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from utils.trust import TrustUnavailable
from utils.verification import canonical_bytes

ROOT = Path(os.environ["BITREP_ROOT"])
VECTOR = json.loads((ROOT / "tests/fixtures/verification-v1.json").read_text())


def bindings(att):
    s = att.statement
    return {
        **{k: getattr(s, k) for k in ("subject", "statement_type", "audience", "content_digest")},
        "statement_digest": statement_digest(s),
    }


class BitRepBindings(unittest.TestCase):
    def setUp(self):
        self.v = deepcopy(VECTOR)
        self.att = Envelope.model_validate(self.v["attestation"])
        self.raw = json.dumps(self.v["attestation"]).encode()
        self.registry = Registry.model_validate(self.v["trust"])
        self.expected = bindings(self.att)
        self.content = self.v["content_utf8"].encode()
        self.now = self.v["evaluated_at"]

    def check(self, **changes):
        args = {
            "raw": self.raw,
            "content": self.content,
            "expected": self.expected,
            "registry": self.registry,
            "trusted_snapshot_digest": self.registry.fingerprint(),
            "now": self.now,
        }
        args.update(changes)
        return evaluate(**args)

    def test_exact_upstream_vector(self):
        self.assertEqual(canonical_bytes(self.att.statement).decode(), self.v["canonical_ascii"])
        self.assertEqual(self.check(), self.v["verification"])

    def test_altered_and_missing_content(self):
        for content in (None, b"altered"):
            with self.assertRaises(ValueError):
                self.check(content=content)

    def test_all_expected_bindings(self):
        for field in self.expected:
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.check(expected={**self.expected, field: "wrong"})

    def test_chain_and_deployment_replay(self):
        for aud in ("index:eip155:1:0xabc:v1", "index:eip155:2:0xdef:v1"):
            with self.assertRaises(ValueError):
                self.check(expected={**self.expected, "audience": aud})

    def test_expired_and_future(self):
        self.assertEqual(self.check(now=1800000100)["reason"], "attestation_expired")
        self.assertEqual(self.check(now=1799999989)["reason"], "not_yet_valid")

    def test_revoked(self):
        trust = deepcopy(self.v["trust"])
        trust["keys"][0]["revoked_at"] = self.now
        reg = Registry.model_validate(trust)
        self.assertEqual(
            self.check(registry=reg, trusted_snapshot_digest=reg.fingerprint())["reason"],
            "key_revoked",
        )

    def test_wrong_signature(self):
        obj = deepcopy(self.v["attestation"])
        obj["signature"] = base64.b64encode(bytes(64)).decode()
        self.assertEqual(self.check(raw=json.dumps(obj).encode())["reason"], "invalid_signature")

    def test_snapshot_pinning(self):
        with self.assertRaises(ValueError):
            self.check(trusted_snapshot_digest="sha256:" + "0" * 64)

    def test_unsigned_result_is_not_proof(self):
        with self.assertRaises(ValueError):
            self.check(raw=json.dumps(self.v["verification"]).encode())

    def test_duplicate_members_rejected(self):
        with self.assertRaises(ValueError):
            self.check(raw=b'{"statement":{},"statement":{}}')

    def test_unavailable_trust(self):
        with self.assertRaises(TrustUnavailable):
            self.check(now=1800001000)

    def test_signed_tampering_even_with_updated_digest(self):
        obj = deepcopy(self.v["attestation"])
        obj["statement"]["attestation_id"] = "tampered"
        att = Envelope.model_validate(obj)
        self.assertEqual(
            self.check(raw=json.dumps(obj).encode(), expected=bindings(att))["reason"],
            "invalid_signature",
        )


# Public synthetic key used only by local EVM end-to-end fixture generator.
def chain_fixture(context):
    now = int(__import__("time").time())
    obj = deepcopy(VECTOR["attestation"])
    obj["statement"].update(
        subject=context["subject"],
        audience=context["audience"],
        statement_type="index-support/1",
        content_digest=digest(context["content"].encode()),
        issued_at=now - 1,
        not_before=now - 1,
        expires_at=now + 60,
    )
    from models.verification import SignedStatement

    s = SignedStatement.model_validate(obj["statement"])
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    obj["signature"] = base64.b64encode(key.sign(canonical_bytes(s))).decode()
    att = Envelope.model_validate(obj)
    trust = deepcopy(VECTOR["trust"])
    trust.update(audience=context["audience"], published_at=now - 10, valid_until=now + 600)
    trust["keys"][0].update(valid_from=now - 10, valid_until=now + 600)
    reg = Registry.model_validate(trust)
    expected = bindings(att)
    result = evaluate(
        json.dumps(obj).encode(), context["content"].encode(), expected, reg, reg.fingerprint(), now
    )
    assert result["outcome"] == "verified"
    return {"attestation": obj, "trust": trust, "expected": expected, "verification": result}


if __name__ == "__main__":
    import sys

    if "--chain-fixture" in sys.argv:
        print(json.dumps(chain_fixture(json.load(sys.stdin))))
    elif "--chain-verify" in sys.argv:
        v = json.load(sys.stdin)
        print(
            json.dumps(
                evaluate(
                    json.dumps(v["attestation"]).encode(),
                    v["content"].encode(),
                    v["expected"],
                    Registry.model_validate(v["trust"]),
                    v["trusted_snapshot_digest"],
                    int(__import__("time").time()),
                )
            )
        )
    else:
        unittest.main()
