"""
Claim Layer Implementation

This module enforces protocol invariants and provides storage/retrieval
functionality for claims with in-memory abstractions.

Protocol Invariants:
- Claims MUST have either evidence_refs or explicit justification
- Claims MUST be attributed to a BitRep identity
- Claims MUST have subject-predicate-object semantic structure
"""

from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class ClaimStore:
    """
    In-memory storage abstraction for claims.
    
    This provides a simple storage interface that can be replaced with
    persistent storage implementations (database, file system, etc.).
    """

    def __init__(self):
        """Initialize the in-memory claim store."""
        self._claims: Dict[str, Dict] = {}
        self._status_events: List[Dict] = []
        self._claims_by_contributor: Dict[str, List[str]] = {}
        self._claims_by_domain: Dict[str, List[str]] = {}

    def store(self, claim: Dict) -> str:
        """
        Store a claim in memory.
        
        Args:
            claim: Claim dictionary with validated fields (will be copied and modified)
            
        Returns:
            The claim ID
            
        Raises:
            ValueError: If claim violates protocol invariants
        """
        # Create a copy to avoid mutating the input
        claim = deepcopy(claim)
        
        # Validate protocol invariants
        self._validate_invariants(claim)
        
        # Generate ID if not present
        if "id" not in claim:
            claim["id"] = f"claim_{uuid4().hex[:16]}"
        
        # Check for existing claim - immutability enforcement
        claim_id = claim["id"]
        if claim_id in self._claims:
            raise ValueError(
                f"Protocol invariant violation: Claim {claim_id} already exists. "
                "Claims MUST be immutable and cannot be modified after creation."
            )
        
        # Set timestamps
        now = datetime.utcnow().isoformat()
        if "created_at" not in claim:
            claim["created_at"] = now
        claim["updated_at"] = now
        
        # Set default status
        if "status" not in claim:
            claim["status"] = "proposed"
        
        # Store the claim
        self._claims[claim_id] = claim
        
        # Index by contributor
        contributor_id = claim["contributor_id"]
        if contributor_id not in self._claims_by_contributor:
            self._claims_by_contributor[contributor_id] = []
        self._claims_by_contributor[contributor_id].append(claim_id)
        
        # Index by domains
        if "domains" in claim and claim["domains"]:
            for domain in claim["domains"]:
                if domain not in self._claims_by_domain:
                    self._claims_by_domain[domain] = []
                self._claims_by_domain[domain].append(claim_id)
        
        return claim_id

    def retrieve(self, claim_id: str) -> Optional[Dict]:
        """
        Retrieve a claim by ID.
        
        Args:
            claim_id: Unique claim identifier
            
        Returns:
            Claim dictionary if found, None otherwise
        """
        return deepcopy(self._claims.get(claim_id))

    def list_by_contributor(self, contributor_id: str) -> List[Dict]:
        """
        List all claims by a specific contributor.
        
        Args:
            contributor_id: BitRep identity of contributor
            
        Returns:
            List of claim dictionaries
        """
        claim_ids = self._claims_by_contributor.get(contributor_id, [])
        return [deepcopy(self._claims[cid]) for cid in claim_ids if cid in self._claims]

    def list_by_domain(self, domain: str) -> List[Dict]:
        """
        List all claims in a specific domain.
        
        Args:
            domain: Domain tag to filter by
            
        Returns:
            List of claim dictionaries
        """
        claim_ids = self._claims_by_domain.get(domain, [])
        return [deepcopy(self._claims[cid]) for cid in claim_ids if cid in self._claims]

    def list_by_status(self, status: str) -> List[Dict]:
        """
        List all claims with a specific status.
        
        Args:
            status: Epistemic status to filter by
            
        Returns:
            List of claim dictionaries
        """
        return [deepcopy(claim) for claim in self._claims.values() if claim.get("status") == status]

    def update_status(self, claim_id: str, new_status: str) -> bool:
        """
        Update the epistemic status of a claim.
        
        Args:
            claim_id: Unique claim identifier
            new_status: New status value
            
        Returns:
            True if updated, False if claim not found
        """
        if claim_id not in self._claims:
            return False
        
        valid_statuses = ["proposed", "supported", "contested", "refuted", "deprecated"]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}")
        
        self._status_events.append({"claim_id": claim_id, "previous": deepcopy(self._claims[claim_id]),
                                    "status": new_status, "policy": "legacy-unverified-status/1"})
        self._claims[claim_id]["status"] = new_status
        self._claims[claim_id]["updated_at"] = datetime.utcnow().isoformat()
        return True

    def status_history(self, claim_id: str) -> List[Dict]:
        """Legacy local events; not authenticated protocol outcomes."""
        return deepcopy([e for e in self._status_events if e["claim_id"] == claim_id])

    def _validate_invariants(self, claim: Dict) -> None:
        """
        Validate protocol invariants for a claim.
        
        Args:
            claim: Claim dictionary to validate
            
        Raises:
            ValueError: If any invariant is violated
        """
        # MUST have subject, predicate, object
        required_fields = ["subject", "predicate", "object", "contributor_id"]
        for field in required_fields:
            if field not in claim or not claim[field]:
                raise ValueError(f"Protocol invariant violation: Claim MUST have '{field}'")
        
        # MUST have either evidence_refs OR justification
        has_evidence = (
            "evidence_refs" in claim 
            and claim["evidence_refs"] is not None 
            and len(claim["evidence_refs"]) > 0
        )
        has_justification = (
            "justification" in claim 
            and claim["justification"] is not None 
            and len(str(claim["justification"]).strip()) > 0
        )
        
        if not has_evidence and not has_justification:
            raise ValueError(
                "Protocol invariant violation: Claim MUST have either evidence_refs or justification"
            )
        
        # Validate timestamp if present
        if "timestamp" in claim:
            try:
                datetime.fromisoformat(claim["timestamp"].replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                raise ValueError(
                    "Protocol invariant violation: Claim timestamp MUST be valid ISO 8601 format"
                )
        
        # Validate ID pattern if present
        if "id" in claim:
            import re
            if not re.match(r'^claim_[a-zA-Z0-9_-]+$', claim["id"]):
                raise ValueError(
                    "Protocol invariant violation: Claim ID MUST match pattern 'claim_[a-zA-Z0-9_-]+'"
                )
        
        # Validate status if present
        if "status" in claim:
            valid_statuses = ["proposed", "supported", "contested", "refuted", "deprecated"]
            if claim["status"] not in valid_statuses:
                raise ValueError(
                    f"Protocol invariant violation: Claim status must be one of {valid_statuses}"
                )


# Global claim store instance
_claim_store = ClaimStore()


def get_claim_store() -> ClaimStore:
    """Get the global claim store instance."""
    return _claim_store


def create_claim(
    subject: str,
    predicate: str,
    object_value: str,
    contributor_id: str,
    evidence_refs: Optional[List[str]] = None,
    justification: Optional[str] = None,
    canonical_text: Optional[str] = None,
    semantic_representation: Optional[Dict] = None,
    domains: Optional[List[str]] = None,
) -> str:
    """
    Create and store a new claim.
    
    Args:
        subject: Subject of the claim
        predicate: Predicate of the claim
        object_value: Object of the claim
        contributor_id: BitRep identity of contributor
        evidence_refs: Optional list of evidence identifiers
        justification: Optional textual justification
        canonical_text: Optional human-readable text
        semantic_representation: Optional machine-readable structure
        domains: Optional domain tags
        
    Returns:
        The created claim ID
        
    Raises:
        ValueError: If protocol invariants are violated
    """
    claim = {
        "subject": subject,
        "predicate": predicate,
        "object": object_value,
        "contributor_id": contributor_id,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if evidence_refs is not None:
        claim["evidence_refs"] = evidence_refs
    if justification is not None:
        claim["justification"] = justification
    if canonical_text is not None:
        claim["canonical_text"] = canonical_text
    if semantic_representation is not None:
        claim["semantic_representation"] = semantic_representation
    if domains is not None:
        claim["domains"] = domains
    
    return _claim_store.store(claim)


def get_claim(claim_id: str) -> Optional[Dict]:
    """
    Retrieve a claim by ID.
    
    Args:
        claim_id: Unique claim identifier
        
    Returns:
        Claim dictionary if found, None otherwise
    """
    return _claim_store.retrieve(claim_id)