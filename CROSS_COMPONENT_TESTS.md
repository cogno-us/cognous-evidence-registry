# Cross component test ownership

The executable chain/BitRep test drivers are maintained in [cognous-stack-qualification](https://github.com/cogno-us/cognous-stack-qualification/tree/43fb81dc3ec0da17402bef274dcec1831cc5e160/suites/cognous-evidence-registry). Run the Chain and BitRep workflow in this repository. It delegates at an immutable suite commit, passes the exact registry source revision and preserves the BitRep pin and npm dependency lock. Source baseline: `650903fd6db1d68810dd377ba09e801a76682935`.

The adapter, client, contract and application unit tests stay here. Original file hashes, license and source references are in the testing repository migration manifest.

| Original path | Canonical path |
|---|---|
| `chain/python/test_bitrep.py` | [suites/cognous-evidence-registry/chain/python/test_bitrep.py](https://github.com/cogno-us/cognous-stack-qualification/blob/43fb81dc3ec0da17402bef274dcec1831cc5e160/suites/cognous-evidence-registry/chain/python/test_bitrep.py) |
| `chain/test/protocol.test.mjs` | [suites/cognous-evidence-registry/chain/test/protocol.test.mjs](https://github.com/cogno-us/cognous-stack-qualification/blob/43fb81dc3ec0da17402bef274dcec1831cc5e160/suites/cognous-evidence-registry/chain/test/protocol.test.mjs) |
