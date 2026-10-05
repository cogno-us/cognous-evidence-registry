"""
Claims API endpoints.

This module provides REST API endpoints for managing claims.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.claims.service import claims_service
from app.core.models import Claim, ClaimCreate, ClaimStatus, ClaimUpdate

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("/", response_model=Claim, status_code=201)
def create_claim(claim: ClaimCreate):
    """
    Create a new scientific claim.

    Args:
        claim: Claim data including canonical text, semantic representation, and domains

    Returns:
        The created claim with assigned ID and metadata
    """
    return claims_service.create_claim(claim)


@router.get("/{claim_id}", response_model=Claim)
def get_claim(claim_id: str):
    """
    Retrieve a specific claim by ID.

    Args:
        claim_id: Unique claim identifier

    Returns:
        The claim if found

    Raises:
        HTTPException: 404 if claim not found
    """
    claim = claims_service.get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.get("/", response_model=List[Claim])
def list_claims(
    status: Optional[ClaimStatus] = Query(None, description="Filter by status"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List claims with optional filtering and pagination.

    Args:
        status: Optional status filter
        domain: Optional domain filter
        limit: Maximum number of results (1-1000)
        offset: Pagination offset

    Returns:
        List of claims matching the filters
    """
    return claims_service.list_claims(status=status, domain=domain, limit=limit, offset=offset)


@router.put("/{claim_id}", response_model=Claim)
def update_claim(claim_id: str, update: ClaimUpdate):
    """
    Update an existing claim.

    Args:
        claim_id: Unique claim identifier
        update: Fields to update

    Returns:
        The updated claim

    Raises:
        HTTPException: 404 if claim not found
    """
    try:
        claim = claims_service.update_claim(claim_id, update)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.delete("/{claim_id}", status_code=204)
def delete_claim(claim_id: str):
    """
    Delete a claim.

    Args:
        claim_id: Unique claim identifier

    Raises:
        HTTPException: 404 if claim not found
    """
    try:
        success = claims_service.delete_claim(claim_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not success:
        raise HTTPException(status_code=404, detail="Claim not found")


@router.get("/search/", response_model=List[Claim])
def search_claims(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
):
    """
    Search claims by text query.

    Args:
        q: Search query string
        limit: Maximum number of results

    Returns:
        List of matching claims
    """
    return claims_service.search_claims(q, limit=limit)
