# Changelog

## Unreleased — decentralized reference slice

- Add a non-upgradeable local EVM protocol for permissionless claim registration,
  evidence assertions/challenges, revision lineage and author lifecycle events.
- Add independent log reconstruction, direct-chain end-to-end tests and measured
  local transaction costs/receipt latency; no public chain deployment.
- Integrate pinned BitRep v1 via independent off-chain verification; explicitly
  leave contract-enforced issuer verification blocked, with no success stub.
- Disable destructive legacy claim PUT/DELETE (409), prevent returned object aliases
  mutating stored claims, and preserve alternate-store local status history.
- Correct implementation/assurance labels and document authority, privacy,
  availability, trust, chain-selection, migration and Governor decisions.
- Retain original MIT license and history. No adjacent repository modifications.
