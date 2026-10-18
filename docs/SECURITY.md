# Security Policy

> **Legacy demo API: unauthenticated, loopback-only.** The FastAPI application
> under `app/` and the in-memory stores under `api/` are non-authoritative
> legacy demonstrations. They have no authentication, no authorization and no
> rate limiting; the identity fields (`created_by`, `submitted_by`, `voter`,
> `attestor_id`) are caller-chosen and unverified. The one exception is link
> `attested_by`, which must match the issuer of a BitRep v1 signature verified
> against an operator trust snapshot (see BITREP_LINK_ATTESTATION.md). Run
> them only on a loopback interface (`127.0.0.1`) for local development. Do not
> bind them to `0.0.0.0` or expose them on any network-reachable listener. The
> authoritative bounded slice is the local chain profile in
> [chain/PROTOCOL.md](../chain/PROTOCOL.md). Nothing in this document is a
> security clearance, certification or production-readiness claim.

## Overview

The legacy API implements none of these as guarantees: it has no authentication, record identities are caller-chosen, and records are not signed or verified, apart from link `attested_by` (BitRep v1 link attestation). Integrity and attribution claims apply only to the chain profile (`chain/PROTOCOL.md`). The sections below describe design principles and what each helper does. This document outlines our security principles, implemented measures, and vulnerability reporting process.

## Security Principles

### 1. Verifiability
Design goal: claims, evidence and links should be backed by cryptographic attestations. The legacy API and stores do **not** implement this: they accept records without any signature. Signature verification exists only in the chain profile and its Cognous Evidence Attestation (BitRep) adapter; see [chain/PROTOCOL.md](../chain/PROTOCOL.md).

### 2. Immutability
Core data structures are designed to be immutable once created, with only computed fields (like status) being updateable.

### 3. Transparency
All security mechanisms are open and auditable. No security through obscurity.

### 4. Decentralization
Design goal. The legacy API has no consensus mechanism and no cryptographic guarantee of its own; the chain profile (`chain/PROTOCOL.md`) is the only part with chain-backed records.

### 5. Privacy
Support for selective disclosure and zero-knowledge proofs to protect sensitive information while maintaining verifiability.

## Implemented Security Measures

### 1. Cryptographic Signature Verification

**Status**: 🟡 Helper only — not wired into the legacy API. `SignatureVerifier` exists as a library helper, but no legacy route or store calls it; legacy records are accepted unsigned.

**Implementation**:
- RSA-based digital signatures for attestations
- PSS padding with SHA-256 hashing
- 2048-bit key size for production use

**Code Location**: `app/core/security.py::SignatureVerifier`

**Usage**:
```python
from app.core.security import signature_verifier

# Generate keypair (for testing)
private_key, public_key = signature_verifier.generate_keypair()

# Sign data
signature = signature_verifier.sign_data(private_key, data.encode())

# Verify signature
is_valid = signature_verifier.verify_signature(public_key, signature, data.encode())
```

**Future Integration**:
- Integration with BitRep identity system
- Hardware security module (HSM) support for key management
- Multi-signature support for critical operations

### 2. Input Validation

**Status**: 🟡 Partial — type validation only

**Implementation**:
- Pydantic models for all API inputs (type checking; most text and list fields have no length or count bounds, and request size is not limited)
- Type checking and validation at the API boundary
- No input sanitization: string values are stored and returned as submitted (no HTML/script escaping or content filtering)

**What this provides**:
- Malformed request bodies (invalid JSON, missing required fields, wrong field types, invalid enum values) are rejected by Pydantic with HTTP 422
- Numeric bounds where declared (for example `ge`/`le` on scores and link strength, finite non-negative vote reputation)

**What this does not provide**:
- No SQL injection surface exists because the legacy API has no database or SQL; this is an absence of SQL, not a protection, and any future database code needs its own parameterized queries
- No XSS protection: values are returned as submitted
- No size or count limits on request bodies, strings or lists
- Free-form fields such as `semantic_representation` (`Dict[str, Any]`) accept arbitrary JSON values without type checking

**Example** (illustrative target shape; the current `app/core/models.py` does not apply these bounds):
```python
class ClaimCreate(BaseModel):
    canonical_text: str = Field(..., min_length=1, max_length=10000)
    domains: List[str] = Field(default_factory=list, max_items=20)
    created_by: str = Field(..., regex=r'^[a-zA-Z0-9_-]+$')
```

### 3. Zero-Knowledge Proofs

**Status**: 🟡 Placeholder Implementation

**Current Implementation**:
- Placeholder ZK proof generation and verification
- Framework for future integration with ZK libraries (zk-SNARKs, zk-STARKs)

**Code Location**: `app/core/security.py::ZKProofPlaceholder`

**Planned Features**:
- Private evidence submission without revealing sensitive data
- Verifiable computation of epistemic status
- Selective disclosure of claim metadata
- Privacy-preserving reputation proofs

### 4. Authentication & Authorization

**Status**: 🟡 Placeholder (BitRep integration pending)

**Current State**:
- Placeholder authentication headers
- All operations require identity specification
- No actual cryptographic verification yet

**Future Implementation**:
- BitRep identity verification
- Challenge-response authentication
- Token-based session management
- Role-based access control (RBAC)

**Planned Token Flow**:
```
1. Client requests challenge
2. Server provides challenge
3. Client signs challenge with private key
4. Server verifies signature against public key
5. Server issues JWT token
6. Client includes token in subsequent requests
```

### 5. Rate Limiting

**Status**: ❌ Not Yet Implemented

**Planned Implementation**:
- IP-based rate limiting
- Identity-based rate limiting
- Reputation-weighted limits (higher reputation = higher limits)
- Adaptive rate limiting based on system load

**Proposed Limits**:
- Standard users: 100 requests/minute
- High-reputation users: 1000 requests/minute
- Proposal creation: 10 per day
- Vote casting: 100 per hour

### 6. Sybil Resistance

**Status**: 🟡 Partial (via BitRep integration)

**Mechanisms**:
- Reputation-weighted voting (quadratic scaling)
- Identity verification through BitRep
- Quality scoring for evidence based on submitter reputation
- Cost of creation for claims and proposals

**Quadratic Voting Formula**:
```
Weighted Vote = sqrt(Reputation Score)
```

This reduces the impact of high-reputation voters. It does **not** provide Sybil resistance in the legacy demo: the `voter` identity and `reputation` value are both caller-supplied and unverified, so one client can vote under many invented identities. Reputation must be finite and non-negative (infinite/NaN values are rejected), but caller-chosen voter identity remains a residual of the legacy demo.

### 7. Data Integrity

**Status**: 🟡 Partial (legacy stores) — not an authoritative audit trail

**Measures**:
- Timestamping of create operations
- Duplicate-ID rejection and copy-in/copy-out isolation in the in-memory stores
- Store-computed SHA-256 `checksum` (evidence) and `immutable_hash` (link); a caller-supplied value that differs from the computed one is rejected. The link hash does **not** cover `target_type` or `metadata`.
- IDs are random, not content-derived; storage is process-local memory, not an immutable audit trail; attestations are not signed or verified

**Data Flow**:
```
Claim → Evidence → Link → Attestation → Signature → Verification
```

## Security Best Practices

### For Developers

1. **Always Validate Input**: Use Pydantic models for all user input
2. **Avoid SQL Injection**: Use parameterized queries (when database is added)
3. **Secure Secret Keys**: Never commit secrets to version control
4. **Use HTTPS**: Always use TLS in production
5. **Regular Updates**: Keep dependencies up to date
6. **Code Review**: All security-related code requires review
7. **Security Testing**: Run security tests before deployment

### For API Consumers

1. **Protect Private Keys**: Never share or expose private keys
2. **Verify Responses**: Always verify signatures on critical data
3. **Use Secure Connections**: Only connect via HTTPS
4. **Implement Timeouts**: Prevent hanging connections
5. **Handle Errors**: Don't expose error details to end users
6. **Monitor Usage**: Watch for unusual patterns

### For Node Operators

1. **Secure Environment**: Run in isolated environment
2. **Regular Backups**: Backup data regularly
3. **Monitor Logs**: Watch for suspicious activity
4. **Update Regularly**: Apply security patches promptly
5. **Restrict Access**: Limit who can access the server
6. **Use Firewalls**: Configure proper firewall rules

## Known Security Considerations

### 1. In-Memory Storage
**Risk**: Data loss on restart, no persistence

**Mitigation** (Planned):
- PostgreSQL database for production
- Regular automated backups
- Replication for high availability

### 2. Placeholder Authentication
**Risk**: No actual identity verification

**Mitigation**:
- BitRep integration for cryptographic identity (in progress)
- Short-term use of placeholder for development only

### 3. No Rate Limiting
**Risk**: Potential for abuse/DoS

**Mitigation** (Planned):
- Implement rate limiting before public release
- Progressive throttling based on behavior

### 4. Hard-Coded Default Secret Key
**Risk**: `app/core/config.py` ships a default `secret_key` (`dev-secret-key-change-in-production`). The legacy API does not currently use it for any route (no token issuance or verification is wired in), but any future use would be forgeable unless the value is overridden.

**Mitigation**: Residual of the legacy demo; behavior is unchanged. Do not rely on it; set a real secret via environment if token code is ever wired in.

### 5. Unbounded Input and Untrusted RPC
**Risk**: Legacy routes and stores retain every accepted object in memory without size or count limits. The chain reconstruction indexer loads the full `getLogs` response from its JSON-RPC provider before any bound applies, so an untrusted or very large provider response can exhaust memory.

**Mitigation**: Run the legacy API on loopback only and use a trusted local RPC for reconstruction.

### 6. Centralized Deployment
**Risk**: Single point of failure

**Mitigation** (Planned):
- Distributed deployment across multiple nodes
- Peer-to-peer synchronization
- Byzantine fault tolerance

## Vulnerability Reporting

### Responsible Disclosure

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

### Reporting Process

1. **Do NOT** open a public GitHub issue
2. Email security reports to: andredelima@cogno.us (the shared Cognous stack reporting route; see the [stack security policy](https://github.com/cogno-us/cognous-open-control-stack/blob/main/SECURITY.md))
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

### Response Timeline

No response-time guarantee is made; see the [stack security policy](https://github.com/cogno-us/cognous-open-control-stack/blob/main/SECURITY.md) for intake status.

### Hall of Fame

We recognize security researchers who responsibly disclose vulnerabilities:
- [List of contributors] (Coming soon)

## Security Roadmap

### Phase 1: Foundation (Current)
- [x] Input validation with Pydantic
- [x] Cryptographic signature framework
- [x] Placeholder ZK proofs
- [x] Basic security documentation

### Phase 2: BitRep Integration (Q1 2024)
- [ ] Identity verification
- [ ] Signature verification for all operations
- [ ] Reputation-based access control
- [ ] Challenge-response authentication

### Phase 3: Production Hardening (Q2 2024)
- [ ] Rate limiting
- [ ] DDoS protection
- [ ] Security audit
- [ ] Penetration testing

### Phase 4: Advanced Features (Q3 2024)
- [ ] Full ZK proof implementation
- [ ] Privacy-preserving evidence
- [ ] Selective disclosure
- [ ] Multi-party computation

### Phase 5: Decentralization (Q4 2024)
- [ ] Distributed deployment
- [ ] Peer-to-peer synchronization
- [ ] Byzantine fault tolerance
- [ ] Governance over security parameters

## Compliance & Standards

### Standards Followed

- **OWASP Top 10**: Protection against common web vulnerabilities
- **CWE/SANS Top 25**: Mitigation of most dangerous software errors
- **NIST Cybersecurity Framework**: Adherence to security best practices

### Future Certifications

- SOC 2 Type II (planned)
- ISO 27001 (planned)
- GDPR compliance (in progress)

## Security Testing

### Automated Testing

```bash
# Run security-focused tests
pytest tests/ -v -k security

# Check dependencies for known vulnerabilities
pip-audit

# Static analysis
bandit -r app/
```

### Manual Testing

- Regular code reviews
- Penetration testing (before production release)
- Security audits by third parties

## Incident Response

### In Case of Security Incident

1. **Contain**: Isolate affected systems
2. **Assess**: Determine scope and impact
3. **Notify**: Inform affected users within 72 hours
4. **Remediate**: Fix the vulnerability
5. **Document**: Post-mortem analysis
6. **Improve**: Update security measures

### Contact

For security concerns:
- Email: andredelima@cogno.us (see the [stack security policy](https://github.com/cogno-us/cognous-open-control-stack/blob/main/SECURITY.md))

## Acknowledgments

Security researchers who have contributed to The Index's security:
- [List to be populated]

## References

- [OWASP Security Guidelines](https://owasp.org/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Framework](https://www.nist.gov/cyberframework)
- [Cognous Evidence Attestation Security Model](https://bitrep.example.com/security) (TBD)

---

**Last Updated**: 2024-01-23

**Version**: 1.0

**Next Review**: 2024-04-23
