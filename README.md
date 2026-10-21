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

**Status:** selected, as lock entry `the_index` (interface: local blockchain reference 0.1.0). Public reference work with no public deployment. **Stack group:** 01 Knowledge & Provenance, beside [Evidence Attestation (BitRep)](https://github.com/cogno-us/cognous-evidence-attestation). See the [stack map](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/stack-map.md) and [where it fits](#cognous-stack-components). Display name "Evidence Registry (The Index)"; Python package `the-index` (see [naming](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/naming.md)).

Status labels used on this page: **merged**, **selected**, **known limit**, **proposed** (defined in the hub [stack map](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/stack-map.md#status-labels)).

## What it is, who it is for, what it does not do

- **What it is.** A protocol and reference implementation for registering scientific claims, linking evidence commitments and preserving revision and lifecycle history. The accepted bounded slice makes the local blockchain contract authoritative for those records and uses Evidence Attestation verification independently off-chain.
- **Who it is for.** Engineers who want to inspect the reference contract, client, reconstruction and adapter; architecture, security and governance reviewers who want to examine the boundary and evidence. Evaluate it for its named responsibility, not as a complete governance platform.
- **What it does not do.** Inclusion in the chain does not show that a claim is true, that evidence is independent, or that an institution permits an action. It has no public-chain deployment, audited production contract, remote consensus finality, authenticated RPC proof or on-chain attestation verification bridge. A valid signature, chain inclusion, message receipt, reasoning instruction or evidence-package digest does not authorize execution; institutional authority must be supplied and evaluated through the appropriate trusted boundary.

## Quick start

**Reproduction of the accepted local-chain slice runs in GitHub Actions only.** Run **Actions, Chain and BitRep cross-component qualification** in this repository. The workflow delegates to the qualification repository at an immutable suite commit, uses the exact source revision, the pinned Evidence Attestation (BitRep) revision `5b5077dafde232a7801cb425c4efddcffb468723`, the existing npm lock, Python 3.12 and Node 24, and runs only synthetic keys and disposable loopback servers (no funds, no public RPC). `npm test` and `npm run test:bitrep` inside `chain/` deliberately exit 1 with a pointer to that workflow; they do not report success. Details: [chain/README.md](chain/README.md) and [CROSS_COMPONENT_TESTS.md](CROSS_COMPONENT_TESTS.md).

**What you can run locally** is the legacy application test suite (known limit: a non-authoritative demonstration surface, not the chain slice). It needs Python 3.10 or later:

```bash
git clone https://github.com/cogno-us/cognous-evidence-registry
cd cognous-evidence-registry
python -m venv .venv && . .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q --no-cov
```

Expected output ends with a pass line and deprecation warnings (no failures; the elapsed time varies):

```text
124 passed, 384 warnings in 15.05s
```

<!-- pin-round: refresh the test count above if the tests change -->

This does not exercise the blockchain contract, the reconstruction client or the attestation adapter. To read the authoritative boundary locally, start with [chain/PROTOCOL.md](chain/PROTOCOL.md) and [chain/VALIDATION.md](chain/VALIDATION.md). The legacy API is unauthenticated and must be run on loopback (`127.0.0.1`) only (see [docs/SECURITY.md](docs/SECURITY.md)); setup is in [docs/DEVELOPER_SETUP.md](docs/DEVELOPER_SETUP.md).

## What ships

| Surface | Path | Purpose | Label |
|---|---|---|---|
| Local protocol contract | [chain/contracts/IndexProtocol.sol](chain/contracts/IndexProtocol.sol) | Non-upgradeable shared graph and lifecycle state machine for claims, evidence assertions and challenges, revisions and author lifecycle events. | selected (local blockchain reference 0.1.0) |
| Chain client | [chain/client.mjs](chain/client.mjs) | Exact-byte commitments and deployment-scoped identifiers. | selected |
| Reconstruction | [chain/reconstruct.mjs](chain/reconstruct.mjs) | Separate read-only log reconstruction with provisional-depth handling. | selected |
| Attestation adapter | [chain/python/bitrep_adapter.py](chain/python/bitrep_adapter.py) | Binding checks that use upstream BitRep verification off-chain; the CLI takes files and a locally trusted snapshot digest (see [chain/README.md](chain/README.md)). | selected |
| Chain documents | [chain/PROTOCOL.md](chain/PROTOCOL.md), [chain/VALIDATION.md](chain/VALIDATION.md) | Normative boundary for the slice; executed cases, environment and untested behavior. | selected |
| Test drivers | [qualification repository suite](https://github.com/cogno-us/cognous-stack-qualification/tree/39f038435afdd71ba162860faa5718d90d7bde64/suites/cognous-evidence-registry) | Chain and attestation drivers; they moved out of this repository. | selected |
| Legacy application (FastAPI) | [app/](app/), [api/](api/README.md), [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md) | Process-local claim, evidence, link and governance services. Unauthenticated, loopback-only, non-authoritative for chain state. | known limit |
| Link attestation | [app/evidence/link_attestation.py](app/evidence/link_attestation.py), [app/bitrep_verify/](app/bitrep_verify/), [docs/BITREP_LINK_ATTESTATION.md](docs/BITREP_LINK_ATTESTATION.md) | The legacy link endpoint requires an attestation envelope verified against an operator trust snapshot. Merged after the lock pin; cross-component adoption is proposed. | merged (legacy surface) |
| Source independence and link weight | [app/evidence/service.py](app/evidence/service.py) | Independence and weight count distinct normalised source identifiers (NFKC, zero-width and combining characters removed, casefolded, DOIs in their doi:, info:doi/, urn:doi: and doi.org/www.doi.org/dx.doi.org URL spellings, case-insensitive and percent-decoded, and arXiv ids with or without version or abs/pdf URL, unified; a DOI against a publisher URL is not), not evidence ids: five records of one source weigh as the strongest one. Repeated identical links (same evidence record and relation) count once, at their strongest link. Merged after the lock pin. | merged (legacy surface) |
| Schemas | [schema/](schema/README.md) | JSON Schema for legacy claim, evidence and link records. They describe record shape only and do not authenticate a record. | known limit |
| Ontology | [ontology/](ontology/README.md) | Core vocabularies (relation, evidence and status types) and a registry module for the legacy surface. | known limit |
| Examples | [examples/](examples/README.md) | Five example claim records (placeholder signatures and attestation ids). | known limit |
| Index operations | [docs/operations/](docs/operations/README.md) | Six named operation documents: IIO-CANON, IIO-DRIFT, IIO-LINEAGE, IIO-PARITY, IIO-REBIND, IIO-TRAVERSE. | proposed (specification text) |
| Protocol directory | [protocol/](protocol/README.md) | A README stating that protocol specifications are still to come, plus an epistemic-engine module for the legacy surface. | proposed |
| Whitepaper and design notes | [docs/The_Index_Whitepaper.md](docs/The_Index_Whitepaper.md), [docs/roadmap-internal-notes.md](docs/roadmap-internal-notes.md) | Historical design intent. They do not add guarantees. | proposed |

The legacy surface also computes reputation-weighted epistemic status; reputation weighting and epistemic scoring are not implemented blockchain guarantees.

## Documentation index

The chain slice and the legacy surface have separate documents. Start with the first group.

Accepted chain slice:

- [chain/README.md](chain/README.md): reproduction, adapter CLI and file list.
- [chain/PROTOCOL.md](chain/PROTOCOL.md): authority model, audit, migration and the blocked attestation boundary.
- [chain/VALIDATION.md](chain/VALIDATION.md): executed results, environment, measurements and untested cases.
- [CROSS_COMPONENT_TESTS.md](CROSS_COMPONENT_TESTS.md): where the moved test drivers live.

Legacy API, glossary and design documents (non-authoritative; each page says which surface it describes):

- [docs/README.md](docs/README.md): legacy project page.
- [docs/DEVELOPER_SETUP.md](docs/DEVELOPER_SETUP.md) and [docs/API_DOCUMENTATION.md](docs/API_DOCUMENTATION.md): setup and API reference.
- [docs/SECURITY.md](docs/SECURITY.md): what the legacy API does and does not provide.
- [docs/BITREP_LINK_ATTESTATION.md](docs/BITREP_LINK_ATTESTATION.md): link attestation and source independence.
- [docs/INDEX.md](docs/INDEX.md) and [docs/INDEX_MAP.md](docs/INDEX_MAP.md): glossary entry format and table of contents.
- [docs/operations/README.md](docs/operations/README.md): the six Index operation documents ([CANON](docs/operations/IIO-CANON.md), [DRIFT](docs/operations/IIO-DRIFT.md), [LINEAGE](docs/operations/IIO-LINEAGE.md), [PARITY](docs/operations/IIO-PARITY.md), [REBIND](docs/operations/IIO-REBIND.md), [TRAVERSE](docs/operations/IIO-TRAVERSE.md)).
- [docs/The_Index_Whitepaper.md](docs/The_Index_Whitepaper.md) and [docs/roadmap-internal-notes.md](docs/roadmap-internal-notes.md): historical design documents.
- Directory READMEs: [api](api/README.md), [ontology](ontology/README.md), [schema](schema/README.md), [examples](examples/README.md), [protocol](protocol/README.md).

Other: [CHANGELOG.md](CHANGELOG.md), [CONTRIBUTING.md](CONTRIBUTING.md), [business overview](collateral/business-collateral.md) and [one-page overview](collateral/one-page-overview.md) (role and evidence limits, not additional features).

## Compatibility and selection

The [hub component lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json) defines the selected revision (`the_index`, local blockchain reference 0.1.0); a component merge does not change that selection or approve deployment. Changes merged after the lock pin (link attestation and the consistency fixes above) are labelled merged, not selected, until the pin round. <!-- pin-round: refresh when the lock pin for the_index moves -->

Test results, run commentary and historical qualification records are in the [central test hub](https://github.com/cogno-us/cognous-stack-qualification/blob/main/results/readme-commentary/index.md). Read them against their recorded source revisions; source selection and deployment approval are separate decisions.

## Limits

- **Known limit:** no public-chain deployment, audited production contract, remote consensus finality, authenticated RPC proof or on-chain attestation verification bridge is established. A passing reference case is not a certification of an enterprise deployment.
- **Known limit:** the legacy FastAPI and store surfaces are non-authoritative demonstrations, unauthenticated and loopback-only. Other legacy API records are accepted unsigned; link attestation applies to the link endpoint only.
- **Known limit:** the standard local reproduction is Actions-only; the local test run above covers the legacy surface.
- **Proposed:** legacy intended specifications, reputation weighting and epistemic scoring do not silently add guarantees. The normative boundary for the slice is [chain/PROTOCOL.md](chain/PROTOCOL.md).
- New dependencies, authority sources, destinations or enforcement mechanisms need their own compatibility and qualification. Shared stack-level claims are in the hub [guarantees and limits](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/guarantees-and-limits.md).

## Contributing and attribution

[Contribution guidance](CONTRIBUTING.md) describes review and validation expectations (the glossary-entry rules there apply to the legacy glossary surface). Keep evidence-linked claims, preserve historical records and separate proposed features from accepted implementation.

See [LICENSE](LICENSE) and [attribution](NOTICE) for the existing terms and third-party scope. Developed by [Cognous](https://cogno.us); no licensing change is part of this documentation update.

---

## Bibliography

Selected external sources from the October 2026 research review. These inform evaluation questions; they do not establish Cognous implementation, adoption, conformance or production qualification.

- [Alexander Barrett. *Boundary Blindness Under Artificial Intelligence: Early Cross-Industry Findings on the Missing Decision-Evidence Layer* (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7210798). Working paper on carrying the basis for reliance across organizational boundaries; proposed architecture, not a validated interoperability guarantee.
- [Mick Yang et al. *AI Epistemic Risks: Emerging Mechanisms & Evidence* (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6873005). Research synthesis on persuasion, cognitive offloading and feedback loops; context for evidence quality and independent judgment.
- [John W. Creswell and J. David Creswell. *Research Design: Qualitative, Quantitative, and Mixed Methods Approaches*, fifth edition. SAGE (2018)](https://edge.sagepub.com/creswellrd5e). Research-methods reference for explicit questions, comparison designs and interpretation limits.

See the [research bibliography](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/research-bibliography.md) for review scope and source-verification limits.

## Cognous stack components

<!-- stack-map:start -->
<!-- Canonical block: identical text in every component README. Source: docs/stack-map.md in the hub. Refresh at the pin round. -->
The Open Control Stack groups its repositories by responsibility. The groups are a navigation map, not an execution sequence and not a requirement to install every component. The hub [component lock](https://github.com/cogno-us/cognous-open-control-stack/blob/main/component-lock.json) is the only source of selected revisions; [release status](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/release-status.md) states their evidence and limits. Last checked against `component-lock.json` at hub commit `dcc9bd7533ef`.

| Group | Members |
| --- | --- |
| **01 Knowledge & Provenance** | [Evidence Registry (The Index)](https://github.com/cogno-us/cognous-evidence-registry) · [Evidence Attestation (BitRep)](https://github.com/cogno-us/cognous-evidence-attestation) |
| **02 Institutional Governance** | [Institutional Governance (Alvorada)](https://github.com/cogno-us/cognous-institutional-governance) |
| **03 Declaration & Policy Control** | [Action Manifest](https://github.com/cogno-us/cognous-action-manifest) · [Control Plane](https://github.com/cogno-us/cognous-control-plane) |
| **04 Constrained Execution** | [Execution Runtime](https://github.com/cogno-us/cognous-execution-runtime) |
| **05 Replay & Evidence** | [Replay Bundle](https://github.com/cogno-us/cognous-replay-bundle) · [Governance Evidence Pack](https://github.com/cogno-us/cognous-governance-evidence-pack) · [ODES](https://github.com/cogno-us/open-decision-evidence-standard) |
| **Cross-cutting exchange** | [Governed Exchange (GAX/IMX)](https://github.com/cogno-us/cognous-governed-exchange) |
| **Tooling and qualification** (side group) | [Ergonomics (`cognous-ocs`)](https://github.com/cogno-us/cognous-open-control-stack-ergonomics) · [Verifier](https://github.com/cogno-us/cognous-open-control-stack-verifier) · [Orchestrator](https://github.com/cogno-us/cognous-stack-orchestrator) · [Qualification](https://github.com/cogno-us/cognous-stack-qualification) |

Status labels used in this README: **merged** (reviewed and merged in the owning repository; not by itself selected), **selected** (pinned in the hub lock), **known limit** (a limitation that is stated and kept visible) and **proposed** (draft or planned work, not a supported interface). Full map, names and commands: [stack map](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/stack-map.md), [naming](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/naming.md), [profiles and tools](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/profiles-and-tools.md). A signature, registry entry, message receipt or evidence summary does not grant execution authority.
<!-- stack-map:end -->

The hub itself is [cognous-open-control-stack](https://github.com/cogno-us/cognous-open-control-stack). Governed Exchange is separate from Institutional Governance's authority framework.

## Repository locations

See the [repository rename map and compatibility notes](https://github.com/cogno-us/cognous-open-control-stack/blob/main/docs/repository-renames.md) for current component URLs. Existing package names, schema identifiers and retained producer identities are unchanged.

## Cross component qualification

The BitRep and local EVM test drivers moved to the [qualification repository](https://github.com/cogno-us/cognous-stack-qualification/tree/39f038435afdd71ba162860faa5718d90d7bde64/suites/cognous-evidence-registry). Use the source-side Chain and BitRep workflow or [the migration map](CROSS_COMPONENT_TESTS.md). The registry application tests and chain adapter implementation remain here.

<!-- Retained anchors for existing documentation links. -->
<a id="evidence-and-supported-scope"></a>
