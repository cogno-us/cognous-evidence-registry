"""
Link Layer Implementation

This module enforces protocol invariants and provides storage/retrieval
functionality for links with immutability guarantees.

Protocol Invariants:
- Links MUST reference existing objects
- Links MUST be BitRep attestations
- Links MUST NOT be edited or deleted after creation
- Links MUST be append-only
"""

import hashlib
import json
import math
from copy import deepcopy
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class LinkStore:
    """
    In-memory storage abstraction for links between claims and evidence/claims.
    
    This provides storage with immutability enforcement and reference validation.
    """

    def __init__(self):
        """Initialize the in-memory link store."""
        self._links: Dict[str, Dict] = {}
        self._links_by_source: Dict[str, List[str]] = {}
        self._links_by_target: Dict[str, List[str]] = {}
        self._links_by_relation: Dict[str, List[str]] = {}
        self._links_by_attestor: Dict[str, List[str]] = {}

    def store(self, link: Dict, validate_references: callable = None) -> str:
        """
        Store a link in memory with validation.
        
        Args:
            link: Link dictionary with validated fields
            validate_references: Optional callback to validate object references
            
        Returns:
            The link ID
            
        Raises:
            ValueError: If link violates protocol invariants
        """
        # Create a deep copy so callers cannot mutate stored nested state
        link = deepcopy(link)
        
        # Validate protocol invariants
        self._validate_invariants(link, validate_references)
        
        # Generate ID if not present
        if "id" not in link:
            link["id"] = f"link_{uuid4().hex[:16]}"
        
        # Set timestamps
        now = datetime.utcnow().isoformat()
        if "created_at" not in link:
            link["created_at"] = now
        link["timestamp"] = link.get("timestamp", now)
        
        # Compute immutable hash; a supplied hash must match the computed value
        computed_hash = self._compute_immutable_hash(link)
        if "immutable_hash" in link and link["immutable_hash"] != computed_hash:
            raise ValueError(
                "Protocol invariant violation: supplied link immutable_hash does not "
                "match the computed hash"
            )
        link["immutable_hash"] = computed_hash
        
        # Check for existing link - immutability enforcement
        link_id = link["id"]
        if link_id in self._links:
            raise ValueError(
                f"Protocol invariant violation: Link {link_id} already exists. "
                "Links MUST be immutable and cannot be modified after creation."
            )
        
        # Store the link
        self._links[link_id] = link
        
        # Index by source
        source_id = link["source_id"]
        if source_id not in self._links_by_source:
            self._links_by_source[source_id] = []
        self._links_by_source[source_id].append(link_id)
        
        # Index by target
        target_id = link["target_id"]
        if target_id not in self._links_by_target:
            self._links_by_target[target_id] = []
        self._links_by_target[target_id].append(link_id)
        
        # Index by relation type
        relation_type = link["relation_type"]
        if relation_type not in self._links_by_relation:
            self._links_by_relation[relation_type] = []
        self._links_by_relation[relation_type].append(link_id)
        
        # Index by attestor
        attestor = link["attestor_id"]
        if attestor not in self._links_by_attestor:
            self._links_by_attestor[attestor] = []
        self._links_by_attestor[attestor].append(link_id)
        
        return link_id

    def retrieve(self, link_id: str) -> Optional[Dict]:
        """
        Retrieve a link by ID.
        
        Args:
            link_id: Unique link identifier
            
        Returns:
            Link dictionary if found, None otherwise
        """
        return deepcopy(self._links.get(link_id))

    def list_by_source(self, source_id: str) -> List[Dict]:
        """
        List all links from a specific source claim.
        
        Args:
            source_id: Source claim identifier
            
        Returns:
            List of link dictionaries
        """
        link_ids = self._links_by_source.get(source_id, [])
        return [deepcopy(self._links[lid]) for lid in link_ids if lid in self._links]

    def list_by_target(self, target_id: str) -> List[Dict]:
        """
        List all links to a specific target (evidence or claim).
        
        Args:
            target_id: Target identifier
            
        Returns:
            List of link dictionaries
        """
        link_ids = self._links_by_target.get(target_id, [])
        return [deepcopy(self._links[lid]) for lid in link_ids if lid in self._links]

    def list_by_relation(self, relation_type: str) -> List[Dict]:
        """
        List all links of a specific relation type.
        
        Args:
            relation_type: Relation type to filter by
            
        Returns:
            List of link dictionaries
        """
        link_ids = self._links_by_relation.get(relation_type, [])
        return [deepcopy(self._links[lid]) for lid in link_ids if lid in self._links]

    def list_by_attestor(self, attestor_id: str) -> List[Dict]:
        """
        List all links created by a specific attestor.
        
        Args:
            attestor_id: BitRep identity of attestor
            
        Returns:
            List of link dictionaries
        """
        link_ids = self._links_by_attestor.get(attestor_id, [])
        return [deepcopy(self._links[lid]) for lid in link_ids if lid in self._links]

    def get_supporting_links(self, claim_id: str) -> List[Dict]:
        """
        Get all supporting links for a claim (supports, weakly_supports).
        
        Args:
            claim_id: Claim identifier
            
        Returns:
            List of supporting link dictionaries
        """
        links = self.list_by_target(claim_id)
        return [
            link for link in links
            if link["relation_type"] in ["supports", "weakly_supports"]
        ]

    def get_contradicting_links(self, claim_id: str) -> List[Dict]:
        """
        Get all contradicting links for a claim (contradicts, conflicts_with).
        
        Args:
            claim_id: Claim identifier
            
        Returns:
            List of contradicting link dictionaries
        """
        links = self.list_by_target(claim_id)
        return [
            link for link in links
            if link["relation_type"] in ["contradicts", "conflicts_with"]
        ]

    def _validate_invariants(self, link: Dict, validate_references: callable = None) -> None:
        """
        Validate protocol invariants for a link.
        
        Args:
            link: Link dictionary to validate
            validate_references: Optional callback to validate object references
            
        Raises:
            ValueError: If any invariant is violated
        """
        # MUST have required fields
        required_fields = ["source_id", "target_id", "relation_type", "weight", "attestor_id"]
        for field in required_fields:
            if field not in link or link[field] is None:
                raise ValueError(
                    f"Protocol invariant violation: Link MUST have '{field}'"
                )
        
        # Source MUST be a claim
        if not link["source_id"].startswith("claim_"):
            raise ValueError(
                "Protocol invariant violation: Link source_id MUST reference a claim"
            )
        
        # Target MUST be evidence or claim
        target_id = link["target_id"]
        if not (target_id.startswith("evidence_") or target_id.startswith("claim_")):
            raise ValueError(
                "Protocol invariant violation: Link target_id MUST reference evidence or claim"
            )
        
        # Relation type MUST be valid
        valid_relations = [
            "supports", "contradicts", "weakly_supports",
            "refines", "generalizes", "depends_on", "conflicts_with"
        ]
        if link["relation_type"] not in valid_relations:
            raise ValueError(
                f"Protocol invariant violation: Link relation_type must be one of {valid_relations}"
            )
        
        # Weight MUST be in valid range
        weight = link["weight"]
        if (
            isinstance(weight, bool)
            or not isinstance(weight, (int, float))
            or not math.isfinite(weight)
            or weight < 0.0
            or weight > 1.0
        ):
            raise ValueError(
                "Protocol invariant violation: Link weight MUST be a number between 0.0 and 1.0"
            )
        
        # Attestor MUST be non-empty
        if not isinstance(link["attestor_id"], str) or len(link["attestor_id"]) == 0:
            raise ValueError(
                "Protocol invariant violation: Link attestor_id MUST be a non-empty string"
            )
        
        # Validate references if callback provided
        if validate_references is not None:
            if not validate_references(link["source_id"], link["target_id"]):
                raise ValueError(
                    f"Protocol invariant violation: Links MUST reference existing objects. "
                    f"Source: {link['source_id']}, Target: {link['target_id']}"
                )

    def _compute_immutable_hash(self, link: Dict) -> str:
        """
        Compute SHA-256 hash of immutable link fields.
        
        Args:
            link: Link dictionary
            
        Returns:
            Hex string of SHA-256 hash
        """
        # Create a stable representation for hashing.
        # Covered fields are listed below; target_type and metadata are NOT
        # covered by this hash (see chain/PROTOCOL.md legacy-store limits).
        stable_fields = {
            "id": link.get("id"),
            "source_id": link["source_id"],
            "target_id": link["target_id"],
            "relation_type": link["relation_type"],
            "weight": link["weight"],
            "attestor_id": link["attestor_id"],
            "timestamp": link.get("timestamp", link.get("created_at"))
        }
        
        # Convert to canonical JSON (sorted keys)
        canonical_json = json.dumps(stable_fields, sort_keys=True, separators=(',', ':'))
        
        # Compute SHA-256
        return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()


# Global link store instance
_link_store = LinkStore()


def get_link_store() -> LinkStore:
    """Get the global link store instance."""
    return _link_store


def create_link(
    source_id: str,
    target_id: str,
    relation_type: str,
    attestor_id: str,
    weight: float = 1.0,
    target_type: Optional[str] = None,
    metadata: Optional[Dict] = None,
    validate_references: callable = None,
) -> str:
    """
    Create and store a new link.
    
    Args:
        source_id: ID of source claim
        target_id: ID of target (evidence or claim)
        relation_type: Type of relationship
        attestor_id: BitRep identity creating the link
        weight: Strength of relationship (0.0-1.0)
        target_type: Type of target ('evidence' or 'claim')
        metadata: Optional additional metadata
        validate_references: Optional callback to validate references exist
        
    Returns:
        The created link ID
        
    Raises:
        ValueError: If protocol invariants are violated
    """
    link = {
        "source_id": source_id,
        "target_id": target_id,
        "relation_type": relation_type,
        "attestor_id": attestor_id,
        "weight": weight,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Infer target_type if not provided
    if target_type is None:
        if target_id.startswith("evidence_"):
            target_type = "evidence"
        elif target_id.startswith("claim_"):
            target_type = "claim"
    
    if target_type is not None:
        link["target_type"] = target_type
    
    if metadata is not None:
        link["metadata"] = metadata
    
    return _link_store.store(link, validate_references)


def get_link(link_id: str) -> Optional[Dict]:
    """
    Retrieve a link by ID.
    
    Args:
        link_id: Unique link identifier
        
    Returns:
        Link dictionary if found, None otherwise
    """
    return _link_store.retrieve(link_id)


def get_supporting_links(claim_id: str) -> List[Dict]:
    """
    Get all supporting links for a claim.
    
    Args:
        claim_id: Claim identifier
        
    Returns:
        List of supporting link dictionaries
    """
    return _link_store.get_supporting_links(claim_id)


def get_contradicting_links(claim_id: str) -> List[Dict]:
    """
    Get all contradicting links for a claim.
    
    Args:
        claim_id: Claim identifier
        
    Returns:
        List of contradicting link dictionaries
    """
    return _link_store.get_contradicting_links(claim_id)
