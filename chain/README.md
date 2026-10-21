# Local blockchain protocol prototype

Read [PROTOCOL.md](PROTOCOL.md) for the authority model, audit, ADR, migration and
blocked BitRep boundary. **No public deployment or production assurance.**

The contract itself owns graph registration and lifecycle transitions; no application
API is needed. BitRep verification remains independent and off-chain. The contract
never accepts a `verified` boolean or verification-result JSON as proof.

## Reproduce

Run **Actions → Chain and BitRep cross-component qualification** in GitHub. The workflow uses the canonical testing repository, the exact owning source commit, pinned BitRep `981036c315856c71207984797b0c4e48d3b3921d`, the existing npm lock, Python 3.12 and Node 24. It runs only synthetic signing and disposable loopback EVM targets. No funds or public RPC are used.

The test drivers moved to [cognous-stack-qualification](https://github.com/cogno-us/cognous-stack-qualification/tree/39f038435afdd71ba162860faa5718d90d7bde64/suites/cognous-evidence-registry). See [the source map](../CROSS_COMPONENT_TESTS.md). The old npm test entrypoints now fail with this relocation notice; they do not silently claim success. The adapter, contract and clients remain here. Historical commands and measurements in VALIDATION.md retain their recorded scope.

The standalone adapter CLI accepts files and a **locally trusted** snapshot digest:

```bash
python python/bitrep_adapter.py --attestation envelope.json --content evidence.bin \
  --expected independently-derived-bindings.json --trust trusted-snapshot.json \
  --trust-digest sha256:YOUR_AUTHENTICATED_SNAPSHOT_FINGERPRINT
```

These filenames are input placeholders, not supplied attestations. `--expected`
contains subject, statement_type, audience, content_digest and statement_digest
from the chain/policy view; do not copy those fields from untrusted evidence. Exit
0 requires a current verified result; rejected result exits 1, missing/malformed
inputs fail rather than returning success. JSON output is not a portable signed
receipt. The fixture driver is test-only and is not the production CLI.

## Files

- `contracts/IndexProtocol.sol`: non-upgradeable shared graph/lifecycle state machine.
- `client.mjs`: exact-byte commitments and deployment-scoped identifiers.
- `reconstruct.mjs`: separate read-only log reconstruction and provisional-depth handling.
- `python/bitrep_adapter.py`: binding checks using upstream verification, no copied crypto.
- Synthetic test drivers: maintained in the qualification repository linked above.
- `VALIDATION.md`: actual results, environment, measurements and untested cases.
