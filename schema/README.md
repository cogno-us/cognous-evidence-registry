# Schema

This directory contains JSON Schema definitions for legacy Index records:

- `claim.schema.json`
- `evidence.schema.json`
- `link.schema.json`

## What schema validation does and does not establish

These schemas describe record **shape** only: required fields, types and string
patterns. A record that validates against them is well-formed; it is **not**
authenticated. Identity fields such as `contributor_id`, `submitted_by` and
`attestor_id` are plain strings, and provenance, signature and attestation
fields are optional or unchecked. Schema validity therefore does not prove who
created a record, that any signature is valid, or that referenced objects exist.

Do not use these schemas as an admission or authenticity gate. Signature
verification is performed only by the local chain profile and its Cognous
Evidence Attestation (BitRep) adapter (`chain/python/bitrep_adapter.py`); see
[chain/PROTOCOL.md](../chain/PROTOCOL.md).
