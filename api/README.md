# API

This directory contains the protocol layer for The Index.

## Files

- `claim_layer.py` - Claim storage with protocol invariant enforcement
- `evidence_layer.py` - Evidence storage with integrity checks, defensive copies and a checksum (process-local memory, not an immutable audit trail; evidence-to-claim references are not checked by the evidence store)
- `link_layer.py` - Link storage with immutability and reference validation
