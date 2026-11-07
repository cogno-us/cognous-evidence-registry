// Three frozen development spot checks for the G1b profile (Hub #273 contract freeze). Not qualification.
// Env: PYTHON (with pydantic+cryptography), BITREP_ROOT (BitRep git checkout holding the adapter PIN),
// G1_ROOT (Attestation checkout at the merged G1 revision), G1B_EVIDENCE_DIR (optional raw-evidence dir).
import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { assess, render, run, verifySignature } from './profile.mjs';

const REVISION = '2ffe37c5ea1255e9699972980f0cb33c06a080e2';
const reportPath = join(process.env.G1_ROOT ?? '.', 'tests/fixtures/verifier-result/complete.report.json');
const evidence = name => process.env.G1B_EVIDENCE_DIR ? join(process.env.G1B_EVIDENCE_DIR, name) : null;
const work = () => mkdtempSync(join(tmpdir(), 'g1b-'));

test('G1b development spot checks', async t => {
  let positive;
  t.after(async () => { if (positive) await positive.close(); });

  await t.test('1 positive: register, submit, independent reconstruct, exact commitment match', async () => {
    positive = await run({ reportPath, workDir: work(), revision: REVISION, evidenceDir: evidence('spot1_positive') });
    const x = positive.result;
    console.log(render(x));
    assert.equal(x.outcome, 'PRESENT_PROVISIONAL');
    assert.deepEqual(x.mismatches, []);
    assert.equal(x.facts.artifact_identity_matched, true);
    assert.equal(x.facts.signature_valid_under_supplied_dev_snapshot, true);
    assert.equal(x.assurance, 'issuer_signature_only');
    assert.equal(x.facts.registry_record_observed_provisional, true);
    assert.equal(x.finality, 'provisional');
    assert.equal(x.report_declared_overall, 'abstain');
    assert.deepEqual(x.write_attempts, { register: 1, submitEvidence: 1 });
    const ev = positive.observation.state.evidence[positive.written.evidenceId];
    assert.equal(ev.relation, 1);
    assert.equal(ev.statement, '0x' + positive.signature.statement_digest.slice(7));
    assert.notEqual(ev.statement, ev.content); // statement digest and report digest are different identities
  });

  await t.test('2 negative: one altered retained report byte is not the registered artifact', async () => {
    assert.ok(positive, 'check 1 must have produced a registered record');
    const altered = new Uint8Array(positive.retained.report);
    altered[altered.length - 2] ^= 0x01;
    const alteredPath = join(positive.workDir, 'altered.report.json');
    writeFileSync(alteredPath, altered);
    const signature = verifySignature({ workDir: positive.workDir, reportPath: alteredPath });
    const x = assess({ retained: { ...positive.retained, report: altered }, written: positive.written,
      observation: positive.observation, signature, dep: positive.dep });
    console.log(render(x));
    assert.equal(x.outcome, 'MISMATCH');
    assert.equal(x.facts.artifact_identity_matched, false);
    assert.ok(x.mismatches.includes('evidence_content'));
    assert.equal(x.facts.signature_valid_under_supplied_dev_snapshot, false);
    assert.equal(x.facts.registry_record_observed_provisional, true); // the record exists; the altered bytes are not it
  });

  await t.test('3 unknown: failed submit acknowledgement is UNKNOWN, one attempt, no retry, no custody claim', async () => {
    const r = await run({ reportPath, workDir: work(), revision: REVISION, evidenceDir: evidence('spot3_unknown'),
      hooks: { beforeSubmit: () => { throw new Error('RPC timeout (injected before broadcast)'); } } });
    try {
      const x = r.result;
      console.log(render(x));
      assert.equal(x.outcome, 'UNKNOWN');
      assert.equal(x.write_attempts.submitEvidence, 1); // never automatically retried
      assert.equal(x.facts.registry_record_observed_provisional, false);
      assert.equal(x.facts.artifact_identity_matched, null);
      assert.ok(x.reasons.includes('evidence_absent_from_reconstruction'));
      assert.ok(x.reasons.includes('write_acknowledgement_not_confirmed'));
      assert.equal(x.write_errors.length, 1);
      assert.ok(x.nonclaims.some(n => n.includes('no durable custody')));
    } finally { await r.close(); }
  });
});
