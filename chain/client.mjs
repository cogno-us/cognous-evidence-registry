import { sha256, toUtf8Bytes } from 'ethers';

// Byte arrays only: callers must explicitly choose serialization/encoding.
export function commitment(bytes) {
  if (!(bytes instanceof Uint8Array)) throw new TypeError('exact bytes required');
  return sha256(bytes);
}
export function requireContent(bytes, expected) {
  if (bytes == null) throw new Error('evidence unavailable');
  if (commitment(bytes) !== expected) throw new Error('content commitment mismatch');
  return bytes;
}
export function audience(chainId, address) {
  return `index:eip155:${chainId}:${address.toLowerCase()}:v1`;
}
export function subject(chainId, address, id) {
  return `${audience(chainId, address)}:claim:${id.slice(2)}`;
}
export const utf8 = toUtf8Bytes;
