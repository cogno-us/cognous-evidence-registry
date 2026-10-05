import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { performance } from 'node:perf_hooks';
import ganache from 'ganache';
import solc from 'solc';
import { ContractFactory, JsonRpcProvider, Wallet, ZeroHash, id } from 'ethers';
import { audience, subject, commitment, requireContent, utf8 } from '../client.mjs';
import { reconstruct } from '../reconstruct.mjs';

const source = readFileSync(new URL('../contracts/IndexProtocol.sol', import.meta.url), 'utf8');
const compiled = JSON.parse(solc.compile(JSON.stringify({language:'Solidity', sources:{'IndexProtocol.sol':{content:source}},
  settings:{optimizer:{enabled:true,runs:200},evmVersion:'shanghai',outputSelection:{'*':{'*':['abi','evm.bytecode.object']}}}})));
assert.equal((compiled.errors ?? []).filter(e=>e.severity==='error').length,0,JSON.stringify(compiled.errors));
const artifact = compiled.contracts['IndexProtocol.sol'].IndexProtocol;
const bytes = s => commitment(utf8(s));
const metrics=[];
async function transact(name, send) {
  const start=performance.now();
  const receipt=await (await send()).wait();
  metrics.push({operation:name,gas:receipt.gasUsed.toString(),fee_wei:receipt.fee.toString(),receipt_ms:Number((performance.now()-start).toFixed(2))});
  assert.equal(receipt.status,1);
  return receipt;
}
async function rejected(send) { await assert.rejects(async()=>{ const tx=await send(); if(tx.wait) await tx.wait(); }); }
function python(flag, input) {
  const r=spawnSync(process.env.PYTHON ?? 'python', ['python/test_bitrep.py',flag], {input:JSON.stringify(input),encoding:'utf8',env:process.env});
  assert.equal(r.status,0,r.stderr);
  return JSON.parse(r.stdout);
}

// Real local EVM execution, two independent JSON-RPC clients, no FastAPI process.
test('local protocol end to end', async t=>{
  const server=ganache.server({logging:{quiet:true},chain:{chainId:31337,hardfork:'shanghai'},wallet:{deterministic:true}});
  await server.listen(0,'127.0.0.1');
  const url=`http://127.0.0.1:${server.address().port}`;
  const writer=new JsonRpcProvider(url,undefined,{cacheTimeout:-1});
  const reader=new JsonRpcProvider(url,undefined,{cacheTimeout:-1});
  writer.pollingInterval=10; reader.pollingInterval=10;
  try {
    const alice=await writer.getSigner(0), bob=await writer.getSigner(1);
    const factory=new ContractFactory(artifact.abi,artifact.evm.bytecode.object,alice);
    const started=performance.now();
    const contract=await factory.deploy();
    const deploy=await contract.deploymentTransaction().wait();
    metrics.push({operation:'deploy',gas:deploy.gasUsed.toString(),fee_wei:deploy.fee.toString(),receipt_ms:Number((performance.now()-started).toFixed(2))});
    const address=await contract.getAddress(), domain=await contract.DOMAIN();
    const content=bytes('Synthetic claim v1');
    const claim=await contract.claimId(await alice.getAddress(),content,ZeroHash);
    await t.test('register claim through chain without application API', async()=>{
      await transact('register',()=>contract.register(domain,content,ZeroHash));
      const stored=await contract.claims(claim);
      assert.equal(stored.author,await alice.getAddress()); assert.equal(stored.content,content);
    });
    await t.test('duplicate claim rejected',()=>rejected(()=>contract.register(domain,content,ZeroHash)));
    await t.test('empty commitment and missing parent rejected',async()=>{
      await rejected(()=>contract.register(domain,ZeroHash,ZeroHash));
      await rejected(()=>contract.register(domain,bytes('orphan'),id('absent')));
    });
    const support='synthetic supporting evidence';
    const fixture=python('--chain-fixture',{subject:subject(31337,address,claim),audience:audience(31337,address),content:support});
    const statement='0x'+fixture.expected.statement_digest.slice(7);
    const manifest=bytes(JSON.stringify({schema:'index-evidence-manifest/1',content_digest:fixture.expected.content_digest,
      sources:['synthetic:experiment:1'],replicas:[],availability:'local fixture only'}));
    await t.test('evidence commitment with independently verified BitRep binding',async()=>{
      await transact('support',()=>contract.submitEvidence(domain,claim,bytes(support),manifest,statement,1));
      const state=await reconstruct(reader,address,artifact.abi);
      const e=Object.values(state.evidence)[0];
      const current=python('--chain-verify',{...fixture,content:support,trusted_snapshot_digest:fixture.verification.trust_snapshot,
        expected:{subject:subject(31337,address,e.claim),audience:audience(31337,address),statement_type:'index-support/1',
          content_digest:'sha256:'+e.content.slice(2),statement_digest:'sha256:'+e.statement.slice(2)}});
      assert.equal(current.outcome,'verified');
    });
    await t.test('duplicate evidence rejected',()=>rejected(()=>contract.submitEvidence(domain,claim,bytes(support),manifest,statement,1)));
    await t.test('invalid evidence references and relation rejected',async()=>{
      await rejected(()=>contract.submitEvidence(domain,id('absent'),bytes(support),manifest,statement,1));
      await rejected(()=>contract.submitEvidence(domain,claim,bytes(support),manifest,statement,3));
    });
    await t.test('any participant can challenge; no truth vote',async()=>{
      await transact('challenge',()=>contract.connect(bob).submitEvidence(domain,claim,bytes('counter-evidence'),bytes('counter manifest'),ZeroHash,2));
      assert.equal((await contract.claims(claim)).lifecycle,1n);
    });
    await t.test('copied evidence from another wallet is not independent corroboration',async()=>{
      await transact('copied-support',()=>contract.connect(bob).submitEvidence(domain,claim,bytes(support),manifest,statement,1));
      const state=await reconstruct(reader,address,artifact.abi);
      assert.equal(Object.values(state.evidence).filter(e=>e.content===bytes(support)).length,2);
      assert.equal(new Set(Object.values(state.evidence).filter(e=>e.relation===1).map(e=>e.content)).size,1);
    });
    await t.test('missing and altered evidence produces no content assurance',()=>{
      assert.throws(()=>requireContent(null,content),/unavailable/);
      assert.throws(()=>requireContent(utf8('altered'),content),/mismatch/);
      assert.deepEqual(requireContent(utf8('Synthetic claim v1'),content),utf8('Synthetic claim v1'));
    });
    const revised=bytes('Synthetic claim v2');
    const revision=await contract.claimId(await alice.getAddress(),revised,claim);
    await t.test('revision registered without rewriting original',async()=>{
      await transact('revision',()=>contract.register(domain,revised,claim));
      assert.equal((await contract.claims(claim)).content,content);
    });
    await t.test('unauthorized withdrawal and supersession rejected',async()=>{
      await rejected(()=>contract.connect(bob).withdraw(domain,claim,bytes('reason')));
      await rejected(()=>contract.connect(bob).supersede(domain,claim,revision,bytes('reason')));
    });
    await t.test('unrelated revision and empty lifecycle reason rejected',async()=>{
      await rejected(()=>contract.supersede(domain,claim,claim,bytes('reason')));
      await rejected(()=>contract.withdraw(domain,claim,ZeroHash));
    });
    await t.test('author supersession preserves content and events',async()=>{
      await transact('supersede',()=>contract.supersede(domain,claim,revision,bytes('correction')));
      const c=await contract.claims(claim);
      assert.equal(c.content,content);assert.equal(c.lifecycle,3n);assert.equal(c.successor,revision);
      await rejected(()=>contract.withdraw(domain,claim,bytes('reason')));
    });
    await t.test('withdrawal preserves revised record',async()=>{
      await transact('withdraw',()=>contract.withdraw(domain,revision,bytes('author withdrawal')));
      assert.equal((await contract.claims(revision)).content,revised);
      assert.equal((await contract.claims(revision)).lifecycle,2n);
    });
    await t.test('second indexer matches every on-chain claim and evidence field',async()=>{
      const state=await reconstruct(reader,address,artifact.abi);
      for (const [key,value] of Object.entries(state.claims)) {
        const actual=await contract.claims(key);
        for(const [field,v] of Object.entries(value)) assert.equal(String(actual[field]),String(v));
      }
      for (const [key,value] of Object.entries(state.evidence)) {
        const actual=await contract.evidence(key);
        for(const [field,v] of Object.entries(value)) assert.equal(String(actual[field]),String(v));
      }
      assert.equal(state.history.length,7);
      assert.equal(state.finality,'provisional');
    });
    await t.test('contract has no upgrade authority; upgrade selector reverts',async()=>{
      const before=await reader.getCode(address);
      await rejected(()=>bob.sendTransaction({to:address,data:id('upgradeTo(address)').slice(0,10)+'0'.repeat(64)}));
      assert.equal(await reader.getCode(address),before);
    });
    await t.test('replay across deployments rejected by contract domain',async()=>{
      const second=await factory.deploy();await second.waitForDeployment();
      assert.notEqual(await second.DOMAIN(),domain);
      await rejected(()=>second.register(domain,content,ZeroHash));
    });
    await t.test('wrong-chain signed transaction and cross-chain domain rejected',async()=>{
      const other=ganache.server({logging:{quiet:true},chain:{chainId:31338,hardfork:'shanghai'},wallet:{deterministic:true}});
      await other.listen(0,'127.0.0.1');
      const provider=new JsonRpcProvider(`http://127.0.0.1:${other.address().port}`,undefined,{cacheTimeout:-1});
      try {
        const otherContract=await new ContractFactory(artifact.abi,artifact.evm.bytecode.object,await provider.getSigner(0)).deploy();
        await otherContract.waitForDeployment();
        assert.equal(await otherContract.getAddress(),address); // identical deployment nonce; chain separates domain
        assert.notEqual(await otherContract.DOMAIN(),domain);
        await rejected(()=>otherContract.register(domain,content,ZeroHash));
        const key=Object.values(other.provider.getInitialAccounts())[0].secretKey;
        const raw=await new Wallet(key).signTransaction({chainId:31337,type:2,nonce:1,to:address,
          data:contract.interface.encodeFunctionData('register',[domain,content,ZeroHash]),gasLimit:300000,
          maxFeePerGas:3000000000n,maxPriorityFeePerGas:1000000000n});
        await assert.rejects(()=>provider.send('eth_sendRawTransaction',[raw]));
      } finally { provider.destroy();await other.close(); }
    });
    await t.test('snapshot rollback removes orphan history and depth filter delays visibility',async()=>{
      const baseline=await reconstruct(reader,address,artifact.abi);
      const snapshot=await writer.send('evm_snapshot',[]);
      const temp=bytes('orphaned claim');
      const tempId=await contract.claimId(await alice.getAddress(),temp,ZeroHash);
      await transact('orphan-register',()=>contract.register(domain,temp,ZeroHash));
      assert.ok((await reconstruct(reader,address,artifact.abi)).claims[tempId]);
      assert.equal((await reconstruct(reader,address,artifact.abi,{confirmations:1})).claims[tempId],undefined);
      assert.equal(await writer.send('evm_revert',[snapshot]),true);
      const restored=await reconstruct(reader,address,artifact.abi);
      assert.deepEqual(restored.claims,baseline.claims);assert.deepEqual(restored.evidence,baseline.evidence);
      assert.deepEqual(restored.history,baseline.history);
      await transact('replacement-register',()=>contract.register(domain,bytes('replacement fork claim'),ZeroHash));
      assert.equal((await reconstruct(reader,address,artifact.abi)).claims[tempId],undefined);
    });
    console.log('LOCAL_METRICS '+JSON.stringify({engine:'ganache 7.9.2',compiler:solc.version(),node:process.version,
      chainId:31337,hardfork:'shanghai',optimizerRuns:200,mode:'instant mining; loopback RPC; no consensus finality',measurements:metrics}));
  } finally { writer.destroy();reader.destroy();await server.close(); }
});
