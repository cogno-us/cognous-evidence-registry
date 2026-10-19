"""
Ontology Registry

This module provides an interface for managing and resolving ontology terms
used throughout The Index protocol.

Functions:
- resolve(term_id): Resolve a term to its full definition
- list_versions(term_id): List all versions of a term
- validate_term(term_id): Check if a term exists and is valid
- get_term(term_id, ontology_id): Get a specific term from an ontology
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class OntologyRegistry:
    """
    Registry for managing ontology definitions and term resolution.
    
    This provides a centralized interface for validating terms, resolving
    definitions, and managing ontology versions.
    """

    def __init__(self, ontology_dir: Optional[str] = None):
        """
        Initialize the ontology registry.
        
        Args:
            ontology_dir: Directory containing ontology JSON files
        """
        if ontology_dir is None:
            # Default to ontology directory relative to this file
            ontology_dir = Path(__file__).parent.parent / "ontology"
        
        self.ontology_dir = Path(ontology_dir)
        self._ontologies: Dict[str, Dict] = {}
        self._term_index: Dict[str, List[Tuple[str, str]]] = {}  # term_id -> [(ontology_id, version)]
        self._deprecated_terms: Dict[str, Dict] = {}  # term_id -> term definition
        
        # Load ontologies at initialization
        self._load_ontologies()

    def _load_ontologies(self) -> None:
        """
        Load all ontology JSON files from the ontology directory.
        """
        if not self.ontology_dir.exists():
            return
        
        # Load all JSON files in the ontology directory
        for json_file in self.ontology_dir.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    ontology = json.load(f)
                    self._register_ontology(ontology)
            except (json.JSONDecodeError, IOError) as e:
                # Log error but continue loading other ontologies
                print(f"Warning: Failed to load ontology from {json_file}: {e}")

    def _register_ontology(self, ontology: Dict) -> None:
        """
        Register an ontology and index its terms.
        
        Args:
            ontology: Ontology dictionary from JSON file
        """
        ontology_id = ontology.get("id")
        version = ontology.get("version", "1.0.0")
        
        if not ontology_id:
            return
        
        # Store the ontology
        key = f"{ontology_id}:{version}"
        self._ontologies[key] = ontology
        
        # Index all terms
        for term in ontology.get("terms", []):
            term_id = term.get("id")
            if term_id:
                if term_id not in self._term_index:
                    self._term_index[term_id] = []
                self._term_index[term_id].append((ontology_id, version))
                
                # Track deprecated terms separately
                if term.get("status") == "deprecated":
                    self._deprecated_terms[term_id] = term

    def resolve(self, term_id: str, ontology_id: Optional[str] = None) -> Optional[Dict]:
        """
        Resolve a term ID to its full definition.
        
        Args:
            term_id: The term identifier to resolve
            ontology_id: Optional specific ontology to search in
            
        Returns:
            Term definition dictionary if found, None otherwise
        """
        # If specific ontology requested, search there first
        if ontology_id:
            term = self._get_term_from_ontology(term_id, ontology_id)
            if term:
                return term
        
        # Search in term index
        if term_id not in self._term_index:
            return None
        
        # Get the most recent version of the term
        # Assuming version strings can be sorted (e.g., "1.0.0", "1.1.0")
        ontologies = self._term_index[term_id]
        if not ontologies:
            return None
        
        # Try to get from the first registered ontology (typically core)
        first_ontology_id, first_version = ontologies[0]
        return self._get_term_from_ontology(term_id, first_ontology_id, first_version)

    def list_versions(self, term_id: str) -> List[Dict]:
        """
        List all versions of a term across ontologies.
        
        Args:
            term_id: The term identifier
            
        Returns:
            List of dictionaries with version information:
            [{"ontology_id": str, "version": str, "term": dict}, ...]
        """
        if term_id not in self._term_index:
            return []
        
        versions = []
        for ontology_id, version in self._term_index[term_id]:
            term = self._get_term_from_ontology(term_id, ontology_id, version)
            if term:
                versions.append({
                    "ontology_id": ontology_id,
                    "version": version,
                    "term": term
                })
        
        return versions

    def validate_term(
        self,
        term_id: str,
        term_type: Optional[str] = None,
        allow_deprecated: bool = False
    ) -> bool:
        """
        Validate that a term exists and optionally check its type.
        
        Args:
            term_id: The term identifier to validate
            term_type: Optional type to validate (relation, evidence_type, status, etc.)
            allow_deprecated: Whether to allow deprecated terms
            
        Returns:
            True if term is valid, False otherwise
        """
        term = self.resolve(term_id)
        
        if term is None:
            return False
        
        # Check if deprecated
        if not allow_deprecated and term_id in self._deprecated_terms:
            return False
        
        # Check type if specified
        if term_type is not None:
            if term.get("type") != term_type:
                return False
        
        return True

    def get_term(
        self,
        term_id: str,
        ontology_id: str,
        version: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Get a specific term from a specific ontology.
        
        Args:
            term_id: The term identifier
            ontology_id: The ontology identifier
            version: Optional version, defaults to latest
            
        Returns:
            Term definition dictionary if found, None otherwise
        """
        return self._get_term_from_ontology(term_id, ontology_id, version)

    def list_ontologies(self) -> List[Dict]:
        """
        List all registered ontologies with metadata.
        
        Returns:
            List of ontology metadata dictionaries
        """
        ontologies = []
        for key, ontology in self._ontologies.items():
            ontologies.append({
                "id": ontology.get("id"),
                "version": ontology.get("version"),
                "name": ontology.get("name"),
                "description": ontology.get("description"),
                "namespace": ontology.get("namespace"),
                "term_count": len(ontology.get("terms", []))
            })
        return ontologies

    def get_relation_types(self) -> List[str]:
        """
        Get all valid relation types from registered ontologies.
        
        Returns:
            List of relation type identifiers
        """
        relation_types = []
        for ontology in self._ontologies.values():
            for term in ontology.get("terms", []):
                if term.get("type") == "relation":
                    relation_types.append(term.get("id"))
        return list(set(relation_types))  # Remove duplicates

    def get_evidence_types(self) -> List[str]:
        """
        Get all valid evidence types from registered ontologies.
        
        Returns:
            List of evidence type identifiers
        """
        evidence_types = []
        for ontology in self._ontologies.values():
            for term in ontology.get("terms", []):
                if term.get("type") == "evidence_type":
                    evidence_types.append(term.get("id"))
        return list(set(evidence_types))

    def is_deprecated(self, term_id: str) -> bool:
        """
        Check if a term is deprecated.
        
        Args:
            term_id: The term identifier
            
        Returns:
            True if deprecated, False otherwise
        """
        return term_id in self._deprecated_terms

    def _get_term_from_ontology(
        self,
        term_id: str,
        ontology_id: str,
        version: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Internal method to get a term from a specific ontology.
        
        Args:
            term_id: The term identifier
            ontology_id: The ontology identifier
            version: Optional version
            
        Returns:
            Term definition dictionary if found, None otherwise
        """
        # If version not specified, try to find any version
        if version is None:
            for key in self._ontologies.keys():
                if key.startswith(f"{ontology_id}:"):
                    ontology = self._ontologies[key]
                    for term in ontology.get("terms", []):
                        if term.get("id") == term_id:
                            return term
            return None
        
        # Specific version requested
        key = f"{ontology_id}:{version}"
        if key not in self._ontologies:
            return None
        
        ontology = self._ontologies[key]
        for term in ontology.get("terms", []):
            if term.get("id") == term_id:
                return term
        
        return None


# Global registry instance
_registry = OntologyRegistry()


def resolve(term_id: str, ontology_id: Optional[str] = None) -> Optional[Dict]:
    """
    Resolve a term ID to its full definition.
    
    Args:
        term_id: The term identifier to resolve
        ontology_id: Optional specific ontology to search in
        
    Returns:
        Term definition dictionary if found, None otherwise
    """
    return _registry.resolve(term_id, ontology_id)


def list_versions(term_id: str) -> List[Dict]:
    """
    List all versions of a term across ontologies.
    
    Args:
        term_id: The term identifier
        
    Returns:
        List of dictionaries with version information
    """
    return _registry.list_versions(term_id)


def validate_term(
    term_id: str,
    term_type: Optional[str] = None,
    allow_deprecated: bool = False
) -> bool:
    """
    Validate that a term exists and optionally check its type.
    
    Args:
        term_id: The term identifier to validate
        term_type: Optional type to validate
        allow_deprecated: Whether to allow deprecated terms
        
    Returns:
        True if term is valid, False otherwise
    """
    return _registry.validate_term(term_id, term_type, allow_deprecated)


def get_ontology_registry() -> OntologyRegistry:
    """Get the global ontology registry instance."""
    return _registry
