# The Index — Business Collateral

## 1. Executive Summary

A protocol and reference implementation for registering scientific claims, linking evidence commitments and preserving revision/lifecycle history. The accepted bounded slice makes the local blockchain contract authoritative for those records and uses BitRep verification independently off-chain.

## 2. The Business Problem

A claim registry should distinguish who registered a record, what exact evidence bytes were committed and what has changed over time. Blockchain inclusion alone cannot answer whether a scientific statement is true, whether evidence is independent or whether an institution permits an action.

## 3. The Component in One View

| Capability | Practical role |
|---|---|
| Claim registration | Record content commitments and wallet attribution directly through the local contract. |
| Evidence relationships | Link supporting and contradicting evidence commitments without converting a vote or duplicate content into truth. |
| Revision and lifecycle | Preserve prior content through revisions, withdrawal and supersession with explicit ownership rules. |
| Read-only reconstruction | Rebuild visible state and event history through an indexer with documented provisional/reorganization handling. |
| BitRep binding | Recompute content bindings and verify issuer signatures off-chain with the exact accepted verifier revision. |

## 4. Who Should Evaluate It

Engineers can inspect the reference contracts and examples; enterprise architecture, security and governance reviewers can examine the boundary and evidence. Evaluate this component for its named responsibility rather than as a complete governance platform.

## 5. A Bounded Workflow

A researcher registers a claim commitment on the local chain and attaches an evidence commitment. An independent reader reconstructs the record, retrieves the expected evidence bytes and checks the signed statement with BitRep. Wallet attribution, chain inclusion, issuer-signature assurance and the scientific interpretation remain separately labeled. Withdrawal or supersession preserves history instead of silently replacing it.

This is a reference use case. Adopting the format or running the example does not establish a production deployment, institutional acceptance or measured business benefit.

## 6. Relationship to the Stack

This component contributes **a local blockchain reference for claims, evidence commitments and lifecycle history**. The [Cognous Open Control Stack](https://github.com/cogno-us/cognous-open-control-stack) connects declared proposals, independent authority, constrained execution and retained review evidence. Components remain separately owned and versioned; the [selected lock](https://github.com/cogno-us/cognous-open-control-stack/blob/5737267d94d2b445735c95e8480a31de73a2abe8/component-lock.json) determines which revisions participate in the supported integration.

A valid signature, chain inclusion, message receipt, reasoning instruction or evidence-package digest does not authorize execution. Institutional authority must be supplied and evaluated through the appropriate trusted boundary.

## 7. What the Evidence Supports

The hub selects local blockchain reference `d5e45d275cb301d9684b543e93b05997991d1cf2`. The [local validation record](../chain/VALIDATION.md) distinguishes executed protocol/BitRep cases, legacy regressions and untested production behavior. The normative boundary for this slice is [chain/PROTOCOL.md](../chain/PROTOCOL.md); legacy intended specifications do not silently add guarantees.

The [accepted hub evidence](https://github.com/cogno-us/cognous-open-control-stack/blob/5737267d94d2b445735c95e8480a31de73a2abe8/examples/control-plane-store-adoption/qualification-summary.json) supports bounded synthetic integration at its exact pins. Aggregate test totals do not establish deployment benefit, compliance or independent real-world verification. The [support ledger](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/release-status.md) distinguishes the standard reference, separate protected-worker campaign and unqualified production work.

## 8. What It Does Not Establish

No public-chain deployment, audited production contract, remote consensus finality, authenticated RPC proof or on-chain BitRep verification bridge is established. The legacy FastAPI/store surfaces are non-authoritative demonstrations. Legacy reputation-weighting and epistemic-scoring goals are not implemented blockchain guarantees.

## 9. Evaluation Questions

- Which exact input, output and source revision will the receiving system consume?
- Who supplies trusted authority or evidence, and which assumptions remain outside this component?
- Can a reviewer trace the result to retained sources, including rejected or missing information?
- Which documented checks were actually executed in the intended environment?
- What deployment-specific work is required before relying on the result?

## 10. Why Open Reference Material Matters

Public formats, source, examples and evidence allow reviewers to inspect the claimed boundary and reproduce its checks. They also expose what has not been tested. Openness supports review; it does not substitute for independent assurance or operating responsibility.

## 11. Practical Next Step

Follow the [README](../README.md) and select one bounded use case. Inspect its inputs and expected outputs, reproduce the documented checks where prerequisites are available, and record failures and unresolved assumptions alongside passes. Use the [one-page overview](one-page-overview.md) for initial stakeholder orientation.

## 12. Status and Attribution

This collateral summarizes merged public material at repository `bbde8a598c7502ca08a7126c093e1cdfaa28bca1` and the accepted hub baseline `5737267d94d2b445735c95e8480a31de73a2abe8`. It does not anticipate pending branches. The protected-worker result applies only to its recorded Linux/bubblewrap fixture; live OpenShell and logical-intent prevention are not hub-supported at this snapshot.

[Cognous](https://cogno.us) · [Source repository](https://github.com/cogno-us/cognous-evidence-registry) · [Stack responsibilities](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/architecture.md). Existing licenses and third-party notices remain controlling.
