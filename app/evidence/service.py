"""
Evidence service layer.

This module provides business logic for managing evidence, parsing metadata,
and linking evidence to claims.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.core.models import (
    ClaimStatus,
    EpistemicStatus,
    Evidence,
    EvidenceCreate,
    Link,
    LinkCreate,
    RelationType,
)

# Quality score calculation constants
QUALITY_BASE_SCORE = 0.5  # Base quality score for all evidence
QUALITY_METHODOLOGY_BONUS = 0.1  # Bonus for having methodology
QUALITY_SAMPLE_SIZE_BONUS = 0.1  # Bonus for sample size > 100
QUALITY_SAMPLE_SIZE_THRESHOLD = 100  # Minimum sample size for bonus
QUALITY_UNCERTAINTY_BONUS = 0.1  # Bonus for reporting uncertainty
QUALITY_REPLICATION_BONUS = 0.2  # Bonus for replication history


class EvidenceService:
    """
    Service for managing evidence and evidence-claim links.

    This service handles evidence submission, quality scoring, and linkage
    to claims. In production, this would interact with a database.
    """

    def __init__(self):
        """Initialize the evidence service with in-memory storage."""
        # In-memory storage (replace with database in production)
        self._evidence: Dict[str, Evidence] = {}
        self._links: Dict[str, Link] = {}
        # (issuer, attestation_id) -> (statement_digest, link_id): replay/idempotency index
        self._attestations: Dict[Tuple[str, str], Tuple[str, str]] = {}

    def submit_evidence(self, evidence_data: EvidenceCreate) -> Evidence:
        """
        Submit new evidence to the system.

        Args:
            evidence_data: Evidence data to submit

        Returns:
            The created evidence object
        """
        evidence_id = f"evidence_{uuid.uuid4().hex[:12]}"

        # Calculate initial quality score based on metadata
        quality_score = self._calculate_quality_score(evidence_data)

        evidence = Evidence(
            id=evidence_id,
            type=evidence_data.type,
            source_identifier=evidence_data.source_identifier,
            metadata=evidence_data.metadata,
            submitted_by=evidence_data.submitted_by,
            quality_score=quality_score,
            created_at=datetime.utcnow(),
        )

        self._evidence[evidence_id] = evidence.model_copy(deep=True)
        return evidence

    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """
        Retrieve evidence by ID.

        Args:
            evidence_id: The evidence identifier

        Returns:
            The evidence if found, None otherwise
        """
        evidence = self._evidence.get(evidence_id)
        return evidence.model_copy(deep=True) if evidence else None

    def list_evidence(self, limit: int = 100, offset: int = 0) -> List[Evidence]:
        """
        List all evidence with pagination.

        Args:
            limit: Maximum number of evidence items to return
            offset: Offset for pagination

        Returns:
            List of evidence items
        """
        evidence_list = [e.model_copy(deep=True) for e in self._evidence.values()]
        return evidence_list[offset : offset + limit]

    def find_link_by_attestation(self, issuer: str, attestation_id: str) -> Optional[Tuple[str, Link]]:
        """Return (statement_digest, link) previously stored for this issuer/attestation id."""
        hit = self._attestations.get((issuer, attestation_id))
        if not hit:
            return None
        return hit[0], self._links[hit[1]].model_copy(deep=True)

    def create_link(
        self,
        link_data: LinkCreate,
        attestation_id: Optional[str] = None,
        attestation_statement_digest: Optional[str] = None,
    ) -> Link:
        """
        Create a link between a claim and evidence or another claim.

        This method does NOT verify identity. The HTTP route verifies the BitRep
        attestation first (app.evidence.link_attestation) and passes its identifiers here.

        Args:
            link_data: Link data including claim_id, evidence_id/claim_id_2, and relation type
            attestation_id: Verified attestation id, if any
            attestation_statement_digest: Verified signed-statement digest, if any

        Returns:
            The created link
        """
        link_id = f"link_{uuid.uuid4().hex[:12]}"

        link = Link(
            id=link_id,
            claim_id=link_data.claim_id,
            evidence_id=link_data.evidence_id,
            claim_id_2=link_data.claim_id_2,
            relation_type=link_data.relation_type,
            strength=link_data.strength,
            attested_by=link_data.attested_by,
            attestation_id=attestation_id,
            attestation_statement_digest=attestation_statement_digest,
            timestamp=datetime.utcnow(),
        )

        self._links[link_id] = link.model_copy(deep=True)
        if attestation_id and attestation_statement_digest:
            self._attestations[(link.attested_by, attestation_id)] = (
                attestation_statement_digest,
                link_id,
            )
        return link

    def get_links_for_claim(self, claim_id: str) -> List[Link]:
        """
        Get all links associated with a claim.

        Args:
            claim_id: The claim identifier

        Returns:
            List of links for the claim
        """
        return [
            link.model_copy(deep=True)
            for link in self._links.values()
            if link.claim_id == claim_id or link.claim_id_2 == claim_id
        ]

    def get_links_for_evidence(self, evidence_id: str) -> List[Link]:
        """
        Get all links associated with evidence.

        Args:
            evidence_id: The evidence identifier

        Returns:
            List of links for the evidence
        """
        return [
            link.model_copy(deep=True)
            for link in self._links.values()
            if link.evidence_id == evidence_id
        ]

    def compute_epistemic_status(self, claim_id: str) -> EpistemicStatus:
        """
        Compute the epistemic status for a claim based on linked evidence.

        Args:
            claim_id: The claim identifier

        Returns:
            Computed epistemic status
        """
        links = self.get_links_for_claim(claim_id)

        # Calculate supporting and contradicting weights
        supporting_weight = 0.0
        contradicting_weight = 0.0
        # Independence counts distinct source identity (source_identifier), never evidence ids:
        # many records citing one source are one source (issue #24).
        evidence_sources = set()

        # One evidence record linked repeatedly with the same relation counts once, at the strongest link.
        strongest: Dict[Tuple[str, RelationType], float] = {}
        for link in links:
            if link.evidence_id:
                key = (link.evidence_id, link.relation_type)
                strongest[key] = max(strongest.get(key, link.strength), link.strength)

        for (evidence_id, relation_type), strength in strongest.items():
            evidence = self._evidence.get(evidence_id)
            if evidence:
                # Weight by evidence quality and link strength
                weight = evidence.quality_score * strength

                if relation_type in [RelationType.SUPPORTS, RelationType.WEAKLY_SUPPORTS]:
                    supporting_weight += weight
                elif relation_type == RelationType.CONTRADICTS:
                    contradicting_weight += weight

                evidence_sources.add(self._source_key(evidence.source_identifier))

        # Calculate independence score based on diversity of sources
        independence_score = min(len(evidence_sources) / 5.0, 1.0)

        # Calculate robustness score (simplified)
        total_weight = supporting_weight + contradicting_weight
        robustness_score = min(total_weight / 10.0, 1.0) if total_weight > 0 else 0.0

        # Determine status category
        if contradicting_weight > supporting_weight:
            if contradicting_weight > 3.0:
                status = ClaimStatus.REFUTED
            else:
                status = ClaimStatus.CONTESTED
        elif supporting_weight > 2.0:
            status = ClaimStatus.SUPPORTED
        else:
            status = ClaimStatus.PROPOSED

        return EpistemicStatus(
            claim_id=claim_id,
            status=status,
            supporting_weight=supporting_weight,
            contradicting_weight=contradicting_weight,
            independence_score=independence_score,
            robustness_score=robustness_score,
            last_computed_at=datetime.utcnow(),
        )

    @staticmethod
    def _source_key(source_identifier: str) -> str:
        """Normalise a source identifier so trivially different spellings are one source."""
        return " ".join(source_identifier.split()).casefold()

    def _calculate_quality_score(self, evidence_data: EvidenceCreate) -> float:
        """
        Calculate an initial quality score for evidence based on metadata.

        Quality score components:
        - Base score: 0.5 (all evidence starts here)
        - Methodology: +0.1 if described
        - Sample size: +0.1 if > 100
        - Uncertainty: +0.1 if reported
        - Replication: +0.2 if available

        Args:
            evidence_data: Evidence data

        Returns:
            Quality score between 0.0 and 1.0
        """
        score = QUALITY_BASE_SCORE

        metadata = evidence_data.metadata

        # Adjust based on metadata completeness
        if metadata.methodology:
            score += QUALITY_METHODOLOGY_BONUS
        if metadata.sample_size and metadata.sample_size > QUALITY_SAMPLE_SIZE_THRESHOLD:
            score += QUALITY_SAMPLE_SIZE_BONUS
        if metadata.uncertainty is not None:
            score += QUALITY_UNCERTAINTY_BONUS
        if metadata.replication_history:
            score += QUALITY_REPLICATION_BONUS

        return min(score, 1.0)


# Global service instance
evidence_service = EvidenceService()
