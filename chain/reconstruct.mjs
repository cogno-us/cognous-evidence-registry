import { Interface } from 'ethers';

// Separate read-only JSON-RPC client. No access to application state or writer receipts.
// Rebuild from genesis each time: intentionally bounded; no stale orphan cache.
// RPC alone is not a consensus proof: use an independently validated node in production.
export async function reconstruct(provider, address, abi, { confirmations = 0 } = {}) {
  if (!Number.isSafeInteger(confirmations) || confirmations < 0) throw new Error('bad confirmations');
  const head = Number(await provider.send('eth_blockNumber', []));
  const toBlock = head - confirmations;
  if (toBlock < 0) throw new Error('insufficient depth');
  const before = await provider.getBlock(toBlock);
  const logs = await provider.getLogs({ address, fromBlock: 0, toBlock });
  const iface = new Interface(abi);
  const claims = {}, evidence = {}, history = [];
  logs.sort((a,b) => a.blockNumber-b.blockNumber || a.transactionIndex-b.transactionIndex || a.index-b.index);
  for (const log of logs) {
    if (log.removed) throw new Error('removed log');
    const event = iface.parseLog(log);
    const a = event.args;
    if (event.name === 'Registered') {
      claims[a.id] = { author: a.author, content: a.content, parent: a.parent, lifecycle: 1, successor: '0x'+'00'.repeat(32) };
    } else if (event.name === 'EvidenceSubmitted') {
      evidence[a.id] = { submitter: a.submitter, claim: a.claim, content: a.content,
        manifest: a.manifest, statement: a.statement, relation: Number(a.relation) };
    } else if (event.name === 'LifecycleChanged') {
      if (!claims[a.id]) throw new Error('incomplete history');
      Object.assign(claims[a.id], { lifecycle: Number(a.lifecycle), successor: a.successor });
    } else throw new Error('unknown event');
    history.push({ event: event.name, id: a.id, blockHash: log.blockHash,
      blockNumber: log.blockNumber, transactionHash: log.transactionHash, logIndex: log.index,
      ...(event.name === 'LifecycleChanged' ? {reason: a.reason, lifecycle: Number(a.lifecycle), successor:a.successor} : {}) });
  }
  const after = await provider.getBlock(toBlock);
  if (!before || !after || before.hash !== after.hash) throw new Error('reorg during reconstruction; retry');
  return { claims, evidence, history, blockNumber: toBlock, blockHash: after.hash,
    finality: confirmations ? `depth:${confirmations};not-consensus-finality` : 'provisional' };
}
