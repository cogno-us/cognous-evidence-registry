// G1b DEVELOPMENT-ONLY registration profile `cognous-registry-verifier-artifact-profile/1-dev`.
// Uses the existing IndexProtocol contract, client.mjs and reconstruct.mjs unchanged. It never writes outside a
// disposable loopback chain it is given, never retries a write, and never reports an aggregate "success":
// artifact identity, signature validity (under a supplied synthetic snapshot) and provisional inclusion are
// separate facts. A disposable chain gives no durable custody, no consensus finality and no authority.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { AbiCoder, Contract, ContractFactory, JsonRpcProvider, ZeroHash, keccak256, sha256 } from 'ethers';
import ganache from 'ganache';
import solc from 'solc';
import { commitment, requireContent, utf8 } from '../client.mjs';
import { reconstruct } from '../reconstruct.mjs';

export const PROFILE = 'cognous-registry-verifier-artifact-profile/1-dev';
export const OUTCOMES = ['PRESENT_PROVISIONAL', 'MISMATCH', 'UNKNOWN', 'REFUSED'];
// Output-only note (deliberately NOT part of NONCLAIMS, which are committed into the manifest bytes).
export const SIGNATURE_FACTS_NOTE = 'signature facts are caller-supplied to assess(); trusted only when produced by run() via the native G1 verification; '
  + 'they are not an independent trust root';
export const NONCLAIMS = [
  'signature is NOT chain/domain-bound and was not verified on-chain; the statement field is an unverified commitment',
  'snapshot fingerprint is submitter-supplied, not authenticated; signature assurance is observer-relative',
  'relation=1 supports only the narrow claim about what the supplied bytes contain',
  'no claim that execution occurred, was independently verified, or that the Evidence Pack is genuine',
  'no claim that the Verifier report is correct, that the producer is authentic, or that the signer holds authority',
  'disposable loopback chain: no durable custody, no consensus finality, no institutional authority',
];

const sourcePath = new URL('../contracts/IndexProtocol.sol', import.meta.url);

export function canonicalJson(value) {
  const sort = v => Array.isArray(v) ? v.map(sort)
    : (v && typeof v === 'object') ? Object.fromEntries(Object.keys(v).sort().map(k => [k, sort(v[k])])) : v;
  return utf8(JSON.stringify(sort(value)));
}

export function claimText(reportSha256, packSubjectDigest) {
  return `The supplied artifact bytes with SHA-256 digest ${reportSha256} contain a developer-format Verifier report `
    + `whose declared overall outcome is ABSTAIN and whose declared Pack subject digest is ${packSubjectDigest}.`;
}

export function compileContract() {
  const source = readFileSync(sourcePath, 'utf8');
  const out = JSON.parse(solc.compile(JSON.stringify({ language: 'Solidity', sources: { 'IndexProtocol.sol': { content: source } },
    settings: { optimizer: { enabled: true, runs: 200 }, evmVersion: 'shanghai', outputSelection: { '*': { '*': ['abi', 'evm.bytecode.object'] } } } })));
  const errors = (out.errors ?? []).filter(e => e.severity === 'error');
  if (errors.length) throw new Error('contract compile failed: ' + JSON.stringify(errors));
  const artifact = out.contracts['IndexProtocol.sol'].IndexProtocol;
  return { abi: artifact.abi, bytecode: artifact.evm.bytecode.object, sourceSha256: sha256(utf8(source)) };
}

/** Disposable loopback Ganache, deterministic PUBLIC test wallets; nothing funded for real, nothing persisted. */
export async function startChain({ chainId = 31337 } = {}) {
  const server = ganache.server({ logging: { quiet: true }, chain: { chainId, hardfork: 'shanghai' }, wallet: { deterministic: true } });
  await server.listen(0, '127.0.0.1');
  const url = `http://127.0.0.1:${server.address().port}`;
  return { server, url, chainId, close: () => server.close() };
}

export async function deploy(url, compiled) {
  const writer = new JsonRpcProvider(url, undefined, { cacheTimeout: -1 });
  const submitter = await writer.getSigner(1);
  const factory = new ContractFactory(compiled.abi, compiled.bytecode, submitter);
  const contract = await factory.deploy();
  const receipt = await contract.deploymentTransaction().wait();
  const address = await contract.getAddress();
  return { writer, submitter, contract, address, domain: await contract.DOMAIN(), deployBlock: receipt.blockNumber,
    deployBlockHash: receipt.blockHash, codeSha256: sha256(await writer.getCode(address)),
    chainId: Number((await writer.getNetwork()).chainId), submitterAddress: await submitter.getAddress() };
}

const childEnv = () => ({ PATH: process.env.PATH ?? '', HOME: process.env.HOME ?? '', PYTHONDONTWRITEBYTECODE: '1',
  BITREP_ROOT: process.env.BITREP_ROOT ?? '', G1_ROOT: process.env.G1_ROOT ?? '' });

export function pythonVerify({ python = process.env.PYTHON ?? 'python3', report, envelope, trust, now, bridge }) {
  const args = [bridge, 'verify', '--envelope', envelope, '--trust', trust, '--now', String(now)];
  if (report) args.push('--report', report);
  const r = spawnSync(python, ['-B', ...args], { encoding: 'utf8', env: childEnv() });
  if (r.status !== 0) throw new Error('bridge failed: ' + r.stderr.slice(0, 400));
  return JSON.parse(r.stdout);
}

export function buildClaim(reportBytes, signature) {
  const text = claimText(commitment(reportBytes).replace(/^0x/, 'sha256:'), signature.report_subject_digest);
  return utf8(text);
}

export function buildManifest({ reportBytes, envelopeBytes, signature, claimBytes, claimId, dep }) {
  return canonicalJson({
    profile: PROFILE,
    report_sha256: 'sha256:' + commitment(reportBytes).slice(2),
    envelope_sha256: 'sha256:' + commitment(envelopeBytes).slice(2),
    statement_digest: signature.statement_digest,
    statement_type: signature.statement_type,
    audience: signature.audience,
    asserted_verifier_revision: signature.verifier_revision_asserted,
    claim_text: new TextDecoder().decode(claimBytes),
    claim_sha256: 'sha256:' + commitment(claimBytes).slice(2),
    claim_id: claimId,
    pack_subject_digest: signature.report_subject_digest,
    chain: { chain_id: dep.chainId, contract_address: dep.address.toLowerCase(), domain: dep.domain, deployed_code_sha256: dep.codeSha256 },
    submitter: dep.submitterAddress.toLowerCase(),
    dev_trust_snapshot_fingerprint: signature.snapshot_fingerprint,
    dev_trust_snapshot_note: 'submitter-supplied synthetic snapshot; fingerprint is not authenticated',
    relation: { value: 1, interpretation: 'the submitted report bytes support the assertion about their own content only' },
    nonclaims: NONCLAIMS,
  });
}

export function evidenceId(dep, claimId, content, manifest, statement, relation) {
  return keccak256(AbiCoder.defaultAbiCoder().encode(['bytes32', 'string', 'address', 'bytes32', 'bytes32', 'bytes32', 'bytes32', 'uint8'],
    [dep.domain, 'evidence', dep.submitterAddress, claimId, content, manifest, statement, relation]));
}

const hex32 = digest => '0x' + digest.replace(/^sha256:/, '');

/** Refuse before any write; returns {refused, reasons} or the artifacts to commit. */
export function preflight({ reportBytes, envelopeBytes, signature }) {
  const reasons = [];
  if (!reportBytes || !envelopeBytes) reasons.push('missing_input_bytes');
  if (!signature) reasons.push('signature_check_unavailable');
  else {
    if (!signature.accepted) reasons.push('signature_or_binding_not_valid:' + signature.reason);
    if (signature.report_overall !== 'abstain') reasons.push('report_overall_not_abstain:' + signature.report_overall);
  }
  return reasons;
}

/**
 * Native register + submitEvidence. Each write is attempted exactly once: no retry, ever. Errors (including
 * timeouts) are recorded, and the outcome is decided later by independent reconstruction.
 */
export async function write({ dep, claimBytes, reportBytes, manifestBytes, signature, hooks = {} }) {
  const claimContent = commitment(claimBytes);
  const attempts = { register: 0, submitEvidence: 0 };
  const errors = [];
  const claimId = await dep.contract.claimId(dep.submitterAddress, claimContent, ZeroHash);
  const content = commitment(reportBytes), manifest = commitment(manifestBytes), statement = hex32(signature.statement_digest);
  const evId = evidenceId(dep, claimId, content, manifest, statement, 1);
  const receipts = {};
  try {
    attempts.register++;
    receipts.register = await (await dep.contract.register(dep.domain, claimContent, ZeroHash)).wait();
  } catch (e) { errors.push({ op: 'register', error: String(e.message ?? e) }); }
  if (!receipts.register) {
    errors.push({ op: 'submitEvidence', error: 'skipped: claim registration not confirmed; no write is retried' });
  } else {
    try {
      attempts.submitEvidence++;
      if (hooks.beforeSubmit) await hooks.beforeSubmit();
      receipts.submitEvidence = await (await dep.contract.submitEvidence(dep.domain, claimId, content, manifest, statement, 1)).wait();
    } catch (e) { errors.push({ op: 'submitEvidence', error: String(e.message ?? e) }); }
  }
  return { claimId, evidenceId: evId, attempts, errors, receipts };
}

export async function observe(url, dep, abi) {
  try {
    const reader = new JsonRpcProvider(url, undefined, { cacheTimeout: -1 }); // separate read-only client
    const state = await reconstruct(reader, dep.address, abi);
    const identity = { chainId: Number((await reader.getNetwork()).chainId), codeSha256: sha256(await reader.getCode(dep.address)),
      domain: await new Contract(dep.address, abi, reader).DOMAIN() };
    return { state, identity };
  } catch (e) { return { error: String(e.message ?? e) }; }
}

/**
 * INTERNAL composition/evaluation helper, not an independent verification interface.
 *
 * `signature` must be the verifier result produced by the trusted development invocation
 * `run() -> pythonVerify() -> native G1 verification` against the supplied synthetic snapshot. It is a plain,
 * caller-supplied object: comparing its `report_sha256`/`envelope_sha256` with the retained bytes binds the
 * subject it CLAIMS to describe but does not authenticate the object itself. A direct caller can supply any
 * facts, so those facts are NOT an independent trust root and `signature_valid_under_supplied_dev_snapshot`
 * is only as trustworthy as the invocation that produced `signature`. Do not rely on `assess()` outside
 * `run()` (or the frozen development spot checks); doing so, or exposing it as an authoritative interface,
 * requires a separate interface decision.
 *
 * No aggregate success; facts are separate. Evidence is located by the originally registered IDs.
 */
export function assess({ retained, written, observation, signature, dep }) {
  const out = { profile: PROFILE, outcome: 'UNKNOWN', reasons: [], mismatches: [],
    facts: { artifact_identity_matched: null, signature_valid_under_supplied_dev_snapshot: Boolean(signature?.accepted),
      registry_record_observed_provisional: null },
    report_declared_overall: signature?.report_overall ?? null, assurance: signature?.assurance ?? 'none',
    signature_facts_note: SIGNATURE_FACTS_NOTE,
    finality: observation?.state?.finality ?? null, finality_note: 'disposable local chain; not consensus finality and not custody',
    observation: { chain_id: dep.chainId, contract: dep.address, domain: dep.domain, deployed_code_sha256: dep.codeSha256,
      claim_id: written?.claimId, evidence_id: written?.evidenceId, block_number: observation?.state?.blockNumber ?? null,
      block_hash: observation?.state?.blockHash ?? null, confirmations: 0 },
    write_attempts: written?.attempts ?? null, write_errors: written?.errors ?? [], nonclaims: NONCLAIMS };
  if (!retained?.report || !retained?.envelope || !retained?.manifest || !retained?.claim) { out.reasons.push('missing_retained_bytes'); return out; }
  if (!observation || observation.error) { out.reasons.push('reconstruction_unavailable:' + (observation?.error ?? 'none')); return out; }
  const claim = observation.state.claims[written.claimId], ev = observation.state.evidence[written.evidenceId];
  if (!claim || !ev) {
    out.facts.registry_record_observed_provisional = false;
    out.reasons.push(!claim ? 'claim_absent_from_reconstruction' : 'evidence_absent_from_reconstruction');
    if (written.errors.length) out.reasons.push('write_acknowledgement_not_confirmed');
    return out; // absence of a confirmed record is UNKNOWN, never proof that nothing was committed
  }
  out.facts.registry_record_observed_provisional = true;
  const m = out.mismatches;
  if (claim.content !== commitment(retained.claim)) m.push('claim_content');
  if (ev.claim !== written.claimId) m.push('evidence_claim_link');
  if (ev.content !== commitment(retained.report)) m.push('evidence_content');
  if (ev.manifest !== commitment(retained.manifest)) m.push('manifest_commitment');
  if (ev.relation !== 1) m.push('relation');
  if (!signature || ev.statement !== hex32(signature.statement_digest)) m.push('statement_commitment');
  const id = observation.identity;
  if (!id || id.chainId !== dep.chainId || id.codeSha256 !== dep.codeSha256 || id.domain !== dep.domain) m.push('chain_or_deployment_identity');
  if (claim.author.toLowerCase() !== dep.submitterAddress.toLowerCase()) m.push('claim_author');
  if (ev.submitter.toLowerCase() !== dep.submitterAddress.toLowerCase()) m.push('evidence_submitter');
  if (claim.lifecycle !== 1) m.push('claim_lifecycle_not_active');
  // the signature facts must be about THESE retained bytes, not a caller-supplied object
  if (!signature || signature.report_sha256 !== 'sha256:' + commitment(retained.report).slice(2)) m.push('signature_not_about_retained_report');
  if (!signature || signature.envelope_sha256 !== 'sha256:' + commitment(retained.envelope).slice(2)) m.push('signature_not_about_retained_envelope');
  if (!signature?.accepted) m.push('signature_not_valid_under_supplied_dev_snapshot');
  if (signature?.report_overall !== 'abstain') m.push('report_overall_not_abstain');
  try {
    const man = JSON.parse(new TextDecoder().decode(retained.manifest));
    const chain = man.chain ?? {};
    if (chain.chain_id !== dep.chainId || chain.contract_address !== dep.address.toLowerCase() || chain.domain !== dep.domain
      || chain.deployed_code_sha256 !== dep.codeSha256) m.push('manifest_chain_identity');
    if (man.claim_id !== written.claimId) m.push('manifest_claim_id');
    if (man.submitter !== dep.submitterAddress.toLowerCase()) m.push('manifest_submitter');
    if (man.relation?.value !== 1) m.push('manifest_relation');
    if (!signature || man.statement_type !== signature.statement_type || man.audience !== signature.audience
      || man.pack_subject_digest !== signature.report_subject_digest || man.asserted_verifier_revision !== signature.verifier_revision_asserted
      || man.dev_trust_snapshot_fingerprint !== signature.snapshot_fingerprint) m.push('manifest_signature_facts');
    if (man.report_sha256 !== 'sha256:' + commitment(retained.report).slice(2)) m.push('manifest_report_sha256');
    if (man.envelope_sha256 !== 'sha256:' + commitment(retained.envelope).slice(2)) m.push('manifest_envelope_sha256');
    if (!signature || man.statement_digest !== signature.statement_digest) m.push('manifest_statement_digest');
    if (man.claim_sha256 !== 'sha256:' + commitment(retained.claim).slice(2)) m.push('manifest_claim_sha256');
  } catch { m.push('manifest_unparseable'); }
  try { requireContent(retained.report, ev.content); } catch { if (!m.includes('evidence_content')) m.push('evidence_content'); }
  out.facts.artifact_identity_matched = m.length === 0;
  if (m.length) { out.outcome = 'MISMATCH'; out.reasons.push('retained_artifact_does_not_match_registered_commitments'); }
  else { out.outcome = 'PRESENT_PROVISIONAL'; if (written.errors.length) out.reasons.push('record_observed_despite_unconfirmed_acknowledgement'); }
  return out;
}

export function render(result) {
  const f = result.facts;
  return [
    `outcome: ${result.outcome}  (${PROFILE}; development only)`,
    `artifact_identity_matched: ${f.artifact_identity_matched}`,
    `signature_valid_under_supplied_dev_snapshot: ${f.signature_valid_under_supplied_dev_snapshot} (${result.assurance}; observer-relative)`,
    `registry_record_observed_provisional: ${f.registry_record_observed_provisional} (finality: ${result.finality}; ${result.finality_note ?? 'disposable chain; not custody'})`,
    `report_declared_overall: ${result.report_declared_overall} (unchanged; not a Registry-verified verdict)`,
    result.reasons.length ? `reasons: ${result.reasons.join(', ')}` : '',
    result.mismatches.length ? `mismatches: ${result.mismatches.join(', ')}` : '',
    `signature facts: ${result.signature_facts_note ?? SIGNATURE_FACTS_NOTE}`,
    'not established: durable custody, consensus finality, authority, execution, producer identity, correctness',
  ].filter(Boolean).join('\n');
}


const bridge = fileURLToPath(new URL('./g1_bridge.py', import.meta.url));

function bridgeMakeEnvelope({ python = process.env.PYTHON ?? 'python3', report, out, revision }) {
  const r = spawnSync(python, ['-B', bridge, 'make-envelope', '--report', report, '--out', out, '--revision', revision], { encoding: 'utf8', env: childEnv() });
  if (r.status !== 0) throw new Error('bridge failed: ' + r.stderr.slice(0, 400));
  return JSON.parse(r.stdout);
}

export function verifySignature({ report, workDir, now = Math.floor(Date.now() / 1000), reportPath }) {
  return pythonVerify({ report: reportPath, envelope: join(workDir, 'envelope.json'), trust: join(workDir, 'trust.json'), now, bridge });
}

/** Full flow. Refusal happens before any chain is started. A single attempt per write; no retry. */
export async function run({ reportPath, workDir, revision, hooks = {}, evidenceDir = null }) {
  mkdirSync(workDir, { recursive: true });
  const reportBytes = new Uint8Array(readFileSync(reportPath));
  let envelopeBytes, signature, bridgeError = null;
  try {
    bridgeMakeEnvelope({ report: reportPath, out: workDir, revision });
    envelopeBytes = new Uint8Array(readFileSync(join(workDir, 'envelope.json')));
    signature = verifySignature({ workDir, reportPath });
  } catch (e) { bridgeError = String(e.message ?? e); }
  const refusal = bridgeError ? ['bridge_failure:' + bridgeError] : preflight({ reportBytes, envelopeBytes, signature });
  if (refusal.length) {
    return { result: { profile: PROFILE, outcome: 'REFUSED', reasons: refusal, mismatches: [], nonclaims: NONCLAIMS,
      facts: { artifact_identity_matched: null, signature_valid_under_supplied_dev_snapshot: Boolean(signature?.accepted), registry_record_observed_provisional: null },
      report_declared_overall: signature?.report_overall ?? null, assurance: signature?.assurance ?? 'none', write_attempts: { register: 0, submitEvidence: 0 } } };
  }
  const compiled = compileContract();
  const chain = await startChain();
  try {
    const dep = await deploy(chain.url, compiled);
    const claimBytes = buildClaim(reportBytes, signature);
    const claimId = await dep.contract.claimId(dep.submitterAddress, commitment(claimBytes), ZeroHash);
    const manifestBytes = buildManifest({ reportBytes, envelopeBytes, signature, claimBytes, claimId, dep });
    const written = await write({ dep, claimBytes, reportBytes, manifestBytes, signature, hooks });
    const observation = await observe(chain.url, dep, compiled.abi);
    const retained = { report: reportBytes, envelope: envelopeBytes, manifest: manifestBytes, claim: claimBytes };
    const result = assess({ retained, written, observation, signature, dep });
    if (evidenceDir) {
      mkdirSync(evidenceDir, { recursive: true });
      for (const [k, v] of Object.entries(retained)) writeFileSync(join(evidenceDir, `retained_${k}.bin`), v);
      writeFileSync(join(evidenceDir, 'result.json'), JSON.stringify(result, null, 1) + '\n');
      writeFileSync(join(evidenceDir, 'observation.json'), JSON.stringify({ written, reconstruction: observation, deployment:
        { chainId: dep.chainId, address: dep.address, domain: dep.domain, deployBlock: dep.deployBlock, deployBlockHash: dep.deployBlockHash,
          codeSha256: dep.codeSha256, contractSourceSha256: compiled.sourceSha256 }, signature }, (k, v) => typeof v === 'bigint' ? v.toString() : v, 1) + '\n');
    }
    return { result, retained, written, observation, signature, dep, compiled, workDir, url: chain.url, close: () => chain.close() };
  } catch (e) { await chain.close(); throw e; }
}
