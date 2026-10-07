# The Index — One-Page Overview

## Purpose

A protocol and reference implementation for registering scientific claims, linking evidence commitments and preserving revision/lifecycle history. The accepted bounded slice makes the local blockchain contract authoritative for those records and uses BitRep verification independently off-chain.

## Problem

A claim registry should distinguish who registered a record, what exact evidence bytes were committed and what has changed over time. Blockchain inclusion alone cannot answer whether a scientific statement is true, whether evidence is independent or whether an institution permits an action.

## What It Provides

- **Claim registration:** Record content commitments and wallet attribution directly through the local contract.
- **Evidence relationships:** Link supporting and contradicting evidence commitments without converting a vote or duplicate content into truth.
- **Revision and lifecycle:** Preserve prior content through revisions, withdrawal and supersession with explicit ownership rules.
- **Read-only reconstruction:** Rebuild visible state and event history through an indexer with documented provisional/reorganization handling.

## Where It Fits

A researcher registers a claim commitment on the local chain and attaches an evidence commitment. An independent reader reconstructs the record, retrieves the expected evidence bytes and checks the signed statement with BitRep. Wallet attribution, chain inclusion, issuer-signature assurance and the scientific interpretation remain separately labeled. Withdrawal or supersession preserves history instead of silently replacing it.

A valid signature, chain inclusion, message receipt, reasoning instruction or evidence-package digest does not authorize execution. Institutional authority must be supplied and evaluated through the appropriate trusted boundary.

## Evidence and Limits

The [accepted hub lock](https://github.com/cogno-us/cognous-open-control-stack/blob/5737267d94d2b445735c95e8480a31de73a2abe8/component-lock.json) selects this component at `d5e45d275cb301d9684b543e93b05997991d1cf2`. Read the component's [README](../README.md) for version-specific acceptance and the [hub support ledger](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/release-status.md) for the executed scope. Component acceptance is not automatic adoption of newer revisions or production qualification.

No public-chain deployment, audited production contract, remote consensus finality, authenticated RPC proof or on-chain BitRep verification bridge is established. The legacy FastAPI/store surfaces are non-authoritative demonstrations. Legacy reputation-weighting and epistemic-scoring goals are not implemented blockchain guarantees.

## Practical Next Step

Choose one bounded example and follow the [README](../README.md). Compare expected and observed results and retain uncertainty. The [business collateral](business-collateral.md) supplies evaluation questions and the component's wider context.

[Cognous](https://cogno.us) · [Source](https://github.com/cogno-us/cognous-evidence-registry) · [All stack components](https://github.com/cogno-us/cognous-open-control-stack). Existing licenses and notices apply.
