"""
Claims service layer.

This module provides business logic for creating, updating, and querying claims.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from app.core.models import Claim, ClaimCreate, ClaimStatus, ClaimUpdate


class ClaimsService:
    """
    Service for managing scientific claims.

    This service handles CRUD operations for claims and their lifecycle management.
    In a production system, this would interact with a database.
    """

    def __init__(self):
        """Initialize the claims service with in-memory storage."""
        # In-memory storage (replace with database in production)
        self._claims: Dict[str, Claim] = {}

    def create_claim(self, claim_data: ClaimCreate) -> Claim:
        """
        Create a new claim.

        Args:
            claim_data: Data for the new claim

        Returns:
            The created claim
        """
        claim_id = f"claim_{uuid.uuid4().hex[:12]}"

        claim = Claim(
            id=claim_id,
            canonical_text=claim_data.canonical_text,
            semantic_representation=claim_data.semantic_representation,
            domains=claim_data.domains,
            status=ClaimStatus.PROPOSED,
            created_by=claim_data.created_by,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self._claims[claim_id] = claim.model_copy(deep=True)
        return claim

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        """
        Retrieve a claim by ID.

        Args:
            claim_id: The claim identifier

        Returns:
            The claim if found, None otherwise
        """
        claim = self._claims.get(claim_id)
        return claim.model_copy(deep=True) if claim else None

    def list_claims(
        self,
        status: Optional[ClaimStatus] = None,
        domain: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Claim]:
        """
        List claims with optional filtering.

        Args:
            status: Filter by claim status
            domain: Filter by domain tag
            limit: Maximum number of claims to return
            offset: Offset for pagination

        Returns:
            List of claims matching the filters
        """
        claims = list(self._claims.values())

        # Apply filters
        if status:
            claims = [c for c in claims if c.status == status]
        if domain:
            claims = [c for c in claims if domain in c.domains]

        # Apply pagination
        return [c.model_copy(deep=True) for c in claims[offset : offset + limit]]

    def update_claim(self, claim_id: str, update_data: ClaimUpdate) -> Optional[Claim]:
        """
        Update a claim.

        Args:
            claim_id: The claim identifier
            update_data: Updated claim data

        Returns:
            The updated claim if found, None otherwise
        """
        claim = self._claims.get(claim_id)
        if not claim:
            return None

        raise ValueError("Accepted claim history is immutable; use an explicit protocol revision")

    def delete_claim(self, claim_id: str) -> bool:
        """Deletion is disabled; blockchain lifecycle events preserve history."""
        if claim_id not in self._claims:
            return False
        raise ValueError("Accepted claim history cannot be deleted; use protocol withdrawal")

    def search_claims(self, query: str, limit: int = 100) -> List[Claim]:
        """
        Search claims by text query.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching claims
        """
        query_lower = query.lower()
        results = [
            claim for claim in self._claims.values() if query_lower in claim.canonical_text.lower()
        ]
        return [c.model_copy(deep=True) for c in results[:limit]]


# Global service instance
claims_service = ClaimsService()
