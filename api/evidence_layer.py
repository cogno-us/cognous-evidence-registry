"""
Evidence Layer Implementation

This module enforces protocol invariants and provides storage/retrieval
functionality for evidence in an in-memory store (defensive copies and a checksum, not an immutable audit trail).

Protocol Invariants:
- Evidence MUST be referenced by at least one claim (design target: this store does not check claim references; only the link layer takes an optional `validate_references` callback)
- Evidence MUST include a provenance chain
- Evidence MUST be immutable after creation
- Evidence MUST have valid checksum for integrity
"""

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class EvidenceStore:
    """
    In-memory storage abstraction for evidence objects.
    
    This provides storage with immutability enforcement and reference tracking.
    """

    def __init__(self):
        """Initialize the in-memory evidence store."""
        self._evidence: Dict[str, Dict] = {}
        self._evidence_by_type: Dict[str, List[str]] = {}
        self._evidence_by_submitter: Dict[str, List[str]] = {}
        # Track which claims reference each evidence
        self._claim_references: Dict[str, List[str]] = {}

    def store(self, evidence: Dict) -> str:
        """
        Store evidence in memory with validation.
        
        Args:
            evidence: Evidence dictionary with validated fields
            
        Returns:
            The evidence ID
            
        Raises:
            ValueError: If evidence violates protocol invariants
        """
        # Create a deep copy so callers cannot mutate stored nested state
        evidence = deepcopy(evidence)
        
        # Validate protocol invariants
        self._validate_invariants(evidence)
        
        # Generate ID if not present
        if "id" not in evidence:
            evidence["id"] = f"evidence_{uuid4().hex[:16]}"
        
        # Set timestamps
        now = datetime.utcnow().isoformat()
        if "created_at" not in evidence:
            evidence["created_at"] = now
        evidence["updated_at"] = now
        
        # Compute checksum; a supplied checksum must match the computed value
        computed_checksum = self._compute_checksum(evidence)
        if "checksum" in evidence and evidence["checksum"] != computed_checksum:
            raise ValueError(
                "Protocol invariant violation: supplied evidence checksum does not "
                "match the computed checksum"
            )
        evidence["checksum"] = computed_checksum
        
        # Check for existing evidence - immutability enforcement
        evidence_id = evidence["id"]
        if evidence_id in self._evidence:
            raise ValueError(
                f"Protocol invariant violation: Evidence {evidence_id} already exists. "
                "Evidence MUST be immutable and cannot be modified after creation."
            )
        
        # Store the evidence
        self._evidence[evidence_id] = evidence
        
        # Index by type
        evidence_type = evidence["type"]
        if evidence_type not in self._evidence_by_type:
            self._evidence_by_type[evidence_type] = []
        self._evidence_by_type[evidence_type].append(evidence_id)
        
        # Index by submitter
        submitter = evidence["submitted_by"]
        if submitter not in self._evidence_by_submitter:
            self._evidence_by_submitter[submitter] = []
        self._evidence_by_submitter[submitter].append(evidence_id)
        
        return evidence_id

    def retrieve(self, evidence_id: str) -> Optional[Dict]:
        """
        Retrieve evidence by ID.
        
        Args:
            evidence_id: Unique evidence identifier
            
        Returns:
            Evidence dictionary if found, None otherwise
        """
        return deepcopy(self._evidence.get(evidence_id))

    def register_claim_reference(self, evidence_id: str, claim_id: str) -> bool:
        """
        Register that a claim references this evidence.
        
        Args:
            evidence_id: Evidence identifier
            claim_id: Claim identifier that references this evidence
            
        Returns:
            True if registered successfully, False if evidence not found
        """
        if evidence_id not in self._evidence:
            return False
        
        if evidence_id not in self._claim_references:
            self._claim_references[evidence_id] = []
        
        if claim_id not in self._claim_references[evidence_id]:
            self._claim_references[evidence_id].append(claim_id)
        
        return True

    def get_claim_references(self, evidence_id: str) -> List[str]:
        """
        Get all claims that reference this evidence.
        
        Args:
            evidence_id: Evidence identifier
            
        Returns:
            List of claim IDs that reference this evidence
        """
        return self._claim_references.get(evidence_id, [])

    def is_referenced(self, evidence_id: str) -> bool:
        """
        Check if evidence is referenced by at least one claim.
        
        Args:
            evidence_id: Evidence identifier
            
        Returns:
            True if referenced, False otherwise
        """
        return len(self._claim_references.get(evidence_id, [])) > 0

    def list_by_type(self, evidence_type: str) -> List[Dict]:
        """
        List all evidence of a specific type.
        
        Args:
            evidence_type: Evidence type to filter by
            
        Returns:
            List of evidence dictionaries
        """
        evidence_ids = self._evidence_by_type.get(evidence_type, [])
        return [deepcopy(self._evidence[eid]) for eid in evidence_ids if eid in self._evidence]

    def list_by_submitter(self, submitter: str) -> List[Dict]:
        """
        List all evidence submitted by a specific contributor.
        
        Args:
            submitter: BitRep identity of submitter
            
        Returns:
            List of evidence dictionaries
        """
        evidence_ids = self._evidence_by_submitter.get(submitter, [])
        return [deepcopy(self._evidence[eid]) for eid in evidence_ids if eid in self._evidence]

    def _validate_invariants(self, evidence: Dict) -> None:
        """
        Validate protocol invariants for evidence.
        
        Args:
            evidence: Evidence dictionary to validate
            
        Raises:
            ValueError: If any invariant is violated
        """
        # MUST have required fields
        required_fields = ["type", "source", "timestamp", "provenance_chain", "submitted_by"]
        for field in required_fields:
            if field not in evidence or not evidence[field]:
                raise ValueError(
                    f"Protocol invariant violation: Evidence MUST have '{field}'"
                )
        
        # Type MUST be valid
        valid_types = ["experiment", "observation", "dataset", "simulation", "theorem", "meta_analysis"]
        if evidence["type"] not in valid_types:
            raise ValueError(
                f"Protocol invariant violation: Evidence type must be one of {valid_types}"
            )
        
        # MUST have provenance chain with at least one entry
        if not isinstance(evidence["provenance_chain"], list) or len(evidence["provenance_chain"]) == 0:
            raise ValueError(
                "Protocol invariant violation: Evidence MUST include a provenance chain with at least one entry"
            )
        
        # Validate provenance chain entries
        for i, entry in enumerate(evidence["provenance_chain"]):
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Protocol invariant violation: Provenance chain entry {i} must be an object"
                )
            required_prov_fields = ["actor", "action", "timestamp"]
            for field in required_prov_fields:
                if field not in entry or not entry[field]:
                    raise ValueError(
                        f"Protocol invariant violation: Provenance chain entry {i} MUST have '{field}'"
                    )
        
        # Timestamp MUST be valid ISO 8601
        try:
            datetime.fromisoformat(evidence["timestamp"].replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            raise ValueError(
                "Protocol invariant violation: Evidence timestamp MUST be valid ISO 8601 format"
            )

    def _compute_checksum(self, evidence: Dict) -> str:
        """
        Compute SHA-256 checksum of evidence content.
        
        Args:
            evidence: Evidence dictionary
            
        Returns:
            Hex string of SHA-256 checksum
        """
        # Create a stable representation for checksumming
        # Exclude computed/mutable fields
        stable_fields = {
            "id": evidence.get("id"),
            "type": evidence["type"],
            "source": evidence["source"],
            "timestamp": evidence["timestamp"],
            "submitted_by": evidence["submitted_by"],
            "provenance_chain": evidence["provenance_chain"],
            "metadata": evidence.get("metadata", {})
        }
        
        # Convert to canonical JSON (sorted keys)
        canonical_json = json.dumps(stable_fields, sort_keys=True, separators=(',', ':'))
        
        # Compute SHA-256
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


# Global evidence store instance
_evidence_store = EvidenceStore()


def get_evidence_store() -> EvidenceStore:
    """Get the global evidence store instance."""
    return _evidence_store


def create_evidence(
    evidence_type: str,
    source: str,
    timestamp: str,
    provenance_chain: List[Dict],
    submitted_by: str,
    checksum: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """
    Create and store new evidence.
    
    Args:
        evidence_type: Type of evidence (experiment, observation, etc.)
        source: External identifier or source reference
        timestamp: ISO 8601 timestamp of evidence creation
        provenance_chain: Chain of provenance entries
        submitted_by: BitRep identity of submitter
        checksum: Optional pre-computed checksum
        metadata: Optional domain-specific metadata
        
    Returns:
        The created evidence ID
        
    Raises:
        ValueError: If protocol invariants are violated
    """
    evidence = {
        "type": evidence_type,
        "source": source,
        "timestamp": timestamp,
        "provenance_chain": provenance_chain,
        "submitted_by": submitted_by,
    }
    
    if checksum is not None:
        evidence["checksum"] = checksum
    if metadata is not None:
        evidence["metadata"] = metadata
    
    return _evidence_store.store(evidence)


def get_evidence(evidence_id: str) -> Optional[Dict]:
    """
    Retrieve evidence by ID.
    
    Args:
        evidence_id: Unique evidence identifier
        
    Returns:
        Evidence dictionary if found, None otherwise
    """
    return _evidence_store.retrieve(evidence_id)


def register_claim_reference(evidence_id: str, claim_id: str) -> bool:
    """
    Register that a claim references this evidence.
    
    Args:
        evidence_id: Evidence identifier
        claim_id: Claim identifier
        
    Returns:
        True if registered successfully
        
    Raises:
        ValueError: If evidence does not exist
    """
    success = _evidence_store.register_claim_reference(evidence_id, claim_id)
    if not success:
        raise ValueError(f"Evidence {evidence_id} does not exist")
    return success
