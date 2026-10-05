# Local blockchain protocol prototype

Read [PROTOCOL.md](PROTOCOL.md) for the authority model, audit, ADR, migration and
blocked BitRep boundary. **No public deployment or production assurance.**

The contract itself owns graph registration and lifecycle transitions; no application
API is needed. BitRep verification remains independent and off-chain. The contract
never accepts a `verified` boolean or verification-result JSON as proof.

## Reproduce

From repository root, using Python 3.12+ and Node 24 (Node 22 should also be suitable,
but was not tested in this run):

```bash
python -m pip install -r requirements-dev.txt
# Outside this repository; read-only dependency checkout, never production keys.
git clone https://github.com/cogno-us/bitrep.git ../bitrep
git -C ../bitrep checkout --detach 5b5077dafde232a7801cb425c4efddcffb468723
export BITREP_ROOT="$(cd ../bitrep && pwd)"
cd chain
npm ci
npm run test:bitrep
npm test
cd ..
python -m pytest -o addopts='' -q
```

`BITREP_ROOT` must identify a clean checkout at the pinned commit. Use a trusted
checkout, interpreter and dependencies. The test signs only with an explicitly
public synthetic key and starts disposable loopback Ganache servers on random
ports. No funds or public RPC are used. It compiles the contract from source, writes
through one chain client, independently reconstructs through another, then stops
the servers. No deployment automation for a public chain is supplied.

`npm test` includes the independent BitRep binding check against actual registered
claim/evidence commitments and prints local gas/receipt latency measurements.
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
- `test/protocol.test.mjs`, `python/test_bitrep.py`: executable synthetic scenarios.
- `VALIDATION.md`: actual results, environment, measurements and untested cases.
