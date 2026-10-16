<!-- cognous-banner:start -->
```text
──────────────────────────────────────────────────
   __________  _______   ______  __  _______
  / ____/ __ \/ ____/ | / / __ \/ / / / ___/
 / /   / / / / / __/  |/ / / / / / / /\__ \
/ /___/ /_/ / /_/ / /|  / /_/ / /_/ /___/ /
\____/\____/\____/_/ |_/\____/\____//____/
            COGNOUS EVIDENCE REGISTRY
       g o v e r n e d   b y   d e s i g n
  github.com/cogno-us/cognous-open-control-stack
──────────────────────────────────────────────────
```
<!-- cognous-banner:end -->

# Cognous Evidence Registry

**A local blockchain reference for claims, evidence commitments and lifecycle history.**

**Stack group: 01 · Knowledge & Provenance.** See the [component map](#cognous-stack-components).

## Overview

A protocol and reference implementation for registering scientific claims, linking evidence commitments and preserving revision/lifecycle history. The accepted bounded slice makes the local blockchain contract authoritative for those records and uses Cognous Evidence Attestation verification independently off-chain.

**Implementation status:** public reference work. The [current component lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json) defines the selected integration; a component merge does not automatically change that selection or approve deployment.

## Purpose and intended users

A claim registry should distinguish who registered a record, what exact evidence bytes were committed and what has changed over time. Blockchain inclusion alone cannot answer whether a scientific statement is true, whether evidence is independent or whether an institution permits an action.

Engineers can inspect the reference contracts and examples; enterprise architecture, security and governance reviewers can examine the boundary and evidence. Evaluate this component for its named responsibility rather than as a complete governance platform.

## Key features

| Capability | Implemented or specified responsibility |
|---|---|
| **Claim registration** | Record content commitments and wallet attribution directly through the local contract. |
| **Evidence relationships** | Link supporting and contradicting evidence commitments without converting a vote or duplicate content into truth. |
| **Revision and lifecycle** | Preserve prior content through revisions, withdrawal and supersession with explicit ownership rules. |
| **Read-only reconstruction** | Rebuild visible state and event history through an indexer with documented provisional/reorganization handling. |
| **Cognous Evidence Attestation binding** | Recompute content bindings and verify issuer signatures off-chain with the exact accepted verifier revision. |

## How it works

A researcher registers a claim commitment on the local chain and attaches an evidence commitment. An independent reader reconstructs the record, retrieves the expected evidence bytes and checks the signed statement with Cognous Evidence Attestation. Wallet attribution, chain inclusion, issuer-signature assurance and the scientific interpretation remain separately labeled. Withdrawal or supersession preserves history instead of silently replacing it.

A valid signature, chain inclusion, message receipt, reasoning instruction or evidence-package digest does not authorize execution. Institutional authority must be supplied and evaluated through the appropriate trusted boundary.

## Getting started

The accepted local-chain reproduction requires Node/npm, Python and a clean Cognous Evidence Attestation checkout at the documented exact SHA. Follow the complete [chain reproduction guide](chain/README.md), which installs dependencies, binds Cognous Evidence Attestation and runs disposable local-chain tests. It uses synthetic keys and local servers, not funds or a public RPC. The legacy API setup in [DEVELOPER_SETUP](docs/DEVELOPER_SETUP.md) serves a different, non-authoritative demo surface.

## Scope and compatibility

Use the [current component lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json) for the selected revision. The [local validation record](chain/VALIDATION.md) distinguishes executed protocol/Cognous Evidence Attestation cases, legacy regressions and untested production behavior. The normative boundary for this slice is [chain/PROTOCOL.md](chain/PROTOCOL.md); legacy intended specifications do not silently add guarantees.

Test results, run commentary and historical qualification records are maintained in the [central test hub](https://github.com/cogno-us/cognous-stack-qualification/blob/main/results/readme-commentary/index.md). Read them against their recorded source revisions; source selection and deployment approval are separate decisions.

## Limitations and deployment decisions

No public-chain deployment, audited production contract, remote consensus finality, authenticated RPC proof or on-chain Cognous Evidence Attestation verification bridge is established. The legacy FastAPI/store surfaces are non-authoritative demonstrations; the legacy API is unauthenticated and must be run on loopback (`127.0.0.1`) only (see [docs/SECURITY.md](docs/SECURITY.md)). Legacy reputation-weighting and epistemic-scoring goals are not implemented blockchain guarantees.

Review original artifacts and their exact source revisions before extending a claim to a new environment. New dependencies, authority sources, destinations or enforcement mechanisms need their own compatibility and qualification. A passing reference case is not a certification of an enterprise deployment.

## Repository guide

Use these sources for details; their historical checkpoints retain the status and scope of the work they recorded:

- [chain/README.md](chain/README.md)
- [chain/PROTOCOL.md](chain/PROTOCOL.md)
- [chain/VALIDATION.md](chain/VALIDATION.md)
- [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md)

For a nontechnical introduction, read the [business overview](collateral/business-collateral.md) and [one-page overview](collateral/one-page-overview.md). Both describe this component's role and evidence limits, not additional runtime features.

## Contributing and attribution

[Contribution guidance](CONTRIBUTING.md) describes review and validation expectations. Keep evidence-linked claims, preserve historical records and separate proposed features from accepted implementation.

See [LICENSE](LICENSE) and [attribution](NOTICE) for the existing terms and third-party scope. Developed by [Cognous](https://cogno.us); no licensing change is part of this documentation update.

---

## Bibliography

Selected external sources from the October 2026 research review. These inform evaluation questions; they do not establish Cognous implementation, adoption, conformance or production qualification.

- [Alexander Barrett. *Boundary Blindness Under Artificial Intelligence: Early Cross-Industry Findings on the Missing Decision-Evidence Layer* (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7210798). Working paper on carrying the basis for reliance across organizational boundaries; proposed architecture, not a validated interoperability guarantee.
- [Mick Yang et al. *AI Epistemic Risks: Emerging Mechanisms & Evidence* (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6873005). Research synthesis on persuasion, cognitive offloading and feedback loops; context for evidence quality and independent judgment.
- [John W. Creswell and J. David Creswell. *Research Design: Qualitative, Quantitative, and Mixed Methods Approaches*, fifth edition. SAGE (2018)](https://edge.sagepub.com/creswellrd5e). Research-methods reference for explicit questions, comparison designs and interpretation limits.

See the [research bibliography](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/research-bibliography.md) for review scope and source-verification limits.

## Cognous stack components

The five groups organize component responsibilities. They are not an execution
sequence or a requirement to install every component. The [hub lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json)
defines the selected integration; [release status](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/release-status.md)
defines its evidence and limits.

| Group | Components |
| --- | --- |
| **01 · Knowledge & Provenance** | [The Index (Evidence Registry)](https://github.com/cogno-us/cognous-evidence-registry) · [BitRep (Evidence Attestation)](https://github.com/cogno-us/cognous-evidence-attestation) |
| **02 · Institutional Governance** | [Alvorada (Institutional Governance)](https://github.com/cogno-us/cognous-institutional-governance) · authority contracts |
| **03 · Declaration & Policy Control** | [Action Manifest](https://github.com/cogno-us/cognous-action-manifest) · [Control Plane](https://github.com/cogno-us/cognous-control-plane) |
| **04 · Constrained Execution** | [Execution Runtime](https://github.com/cogno-us/cognous-execution-runtime) |
| **05 · Replay & Evidence** | [Replay Bundle](https://github.com/cogno-us/cognous-replay-bundle) · [Governance Evidence Pack](https://github.com/cogno-us/cognous-governance-evidence-pack) · [ODES](https://github.com/cogno-us/open-decision-evidence-standard) |

**Cross-cutting exchange:** [Governed Exchange (GAX/IMX)](https://github.com/cogno-us/cognous-governed-exchange) connects
governed messages, recipient assessment and continuity across the groups. It is
separate from Alvorada's institutional authority framework.

The supported Execution Runtime boundary is the Cognous Python layer under
`engine/`. The upstream application is outside this boundary. Human oversight
requires an actual review process and accountable people.
A signature, registry entry, message receipt or evidence summary does not grant
execution authority.


## Repository locations

See the [repository rename map and compatibility notes](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/repository-renames.md) for current component URLs. Existing package names, schema identifiers and retained producer identities are unchanged.

## Cross component qualification

The BitRep and local EVM test drivers moved to the [qualification repository](https://github.com/cogno-us/cognous-stack-qualification/tree/39f038435afdd71ba162860faa5718d90d7bde64/suites/cognous-evidence-registry). Use the source-side Chain and BitRep workflow or [the migration map](CROSS_COMPONENT_TESTS.md). The registry application tests and chain adapter implementation remain here.

<!-- Retained anchors for existing documentation links. -->
<a id="evidence-and-supported-scope"></a>
