# The Index

[![Tests](https://img.shields.io/badge/tests-60%20passing-brightgreen)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-86%25-brightgreen)](htmlcov/)
[![Python](https://img.shields.io/badge/python-3.9+-blue)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green)](requirements.txt)

**A Protocol for Verifiable Scientific Knowledge Built on BitRep**

The Index is a modular, decentralized protocol for representing and evaluating scientific claims through reputation-weighted evidence and community governance.

## Overview

The Index provides a structured, transparent system for:

- **Claims Management**: Creating and tracking scientific statements with canonical text and semantic structure
- **Evidence Linking**: Submitting empirical or theoretical evidence and linking it to claims
- **Epistemic Status**: Computing reputation-weighted assessments of claim validity
- **Decentralized Governance**: Community-driven schema evolution through quadratic voting

## Key Features

### 🔬 Scientific Claims
- Canonical text representation
- Machine-readable semantic structure
- Domain tagging and categorization
- Status lifecycle (proposed → supported/contested/refuted)

### 📊 Evidence Management
- Multiple evidence types (experiments, observations, datasets, simulations, theorems)
- Quality scoring based on methodology, sample size, and replication
- Direct linking to claims with relation types (supports, contradicts, refines, etc.)

### 🤝 Decentralized Governance
- Community proposals for schema changes, ontology updates, and rule modifications
- Reputation-weighted voting with quadratic scaling
- Transparent proposal lifecycle (draft → active → passed/rejected)

### 🔒 Security & Trust
- Cryptographic signature verification
- Placeholder zero-knowledge proofs for claim evidence
- Input validation with Pydantic
- BitRep integration for identity and reputation (planned)

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/cogno-us/cognous-evidence-registry.git
cd cognous-evidence-registry

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

### Running the API Server

```bash
# Start the FastAPI development server
uvicorn app.main:app --reload

# The API will be available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

### Basic Usage

```python
import requests

# Create a scientific claim
claim_data = {
    "canonical_text": "Quantum entanglement persists over macroscopic distances",
    "semantic_representation": {
        "subject": "quantum_entanglement",
        "predicate": "persists"
    },
    "domains": ["quantum_physics", "experimental_physics"],
    "created_by": "researcher_id_123"
}

response = requests.post(
    "http://localhost:8000/api/v1/claims/",
    json=claim_data
)
claim = response.json()
print(f"Created claim: {claim['id']}")

# Submit supporting evidence
evidence_data = {
    "type": "experiment",
    "source_identifier": "doi:10.1234/example",
    "metadata": {
        "methodology": "double-blind RCT",
        "sample_size": 1000,
        "uncertainty": 0.05
    },
    "submitted_by": "researcher_id_456"
}

response = requests.post(
    "http://localhost:8000/api/v1/evidence/",
    json=evidence_data
)
evidence = response.json()

# Link evidence to claim
link_data = {
    "claim_id": claim["id"],
    "evidence_id": evidence["id"],
    "relation_type": "supports",
    "strength": 0.9,
    "attested_by": "researcher_id_789"
}

requests.post(
    "http://localhost:8000/api/v1/evidence/links",
    json=link_data
)

# Get epistemic status
response = requests.get(
    f"http://localhost:8000/api/v1/evidence/epistemic-status/{claim['id']}"
)
status = response.json()
print(f"Epistemic status: {status['status']}")
print(f"Supporting weight: {status['supporting_weight']}")
```

## Architecture

### Directory Structure

```
the-index/
├── app/
│   ├── api/              # FastAPI routers
│   │   ├── claims.py     # Claims endpoints
│   │   ├── evidence.py   # Evidence and links endpoints
│   │   └── governance.py # Governance endpoints
│   ├── claims/           # Claims business logic
│   ├── evidence/         # Evidence and linking logic
│   ├── governance/       # Governance and voting logic
│   ├── core/             # Shared utilities
│   │   ├── config.py     # Configuration management
│   │   ├── models.py     # Pydantic data models
│   │   └── security.py   # Security utilities
│   └── main.py           # FastAPI application
├── docs/                 # Documentation
├── tests/                # Test suite
└── pyproject.toml        # Project configuration
```

### Core Concepts

#### Claims
Atomic scientific statements with:
- Canonical text (human-readable)
- Semantic representation (machine-readable)
- Domain tags
- Epistemic status
- Provenance tracking

#### Evidence
Empirical or theoretical support with:
- Type classification
- Source identifiers (DOI, arXiv ID, etc.)
- Quality scoring
- Metadata (methodology, sample size, uncertainty)

#### Links
Relationships between claims and evidence:
- Relation types (supports, contradicts, refines, etc.)
- Strength weighting (0.0 to 1.0)
- Attestation provenance

#### Epistemic Status
Computed assessment based on:
- Supporting evidence weight
- Contradicting evidence weight
- Independence score (diversity of sources)
- Robustness score (replication and quality)

## API Documentation

Full API documentation is available at:
- Interactive docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for detailed reference

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_claims.py -v
```

### Code Quality

```bash
# Lint with ruff
ruff check app/ tests/

# Type check with mypy
mypy app/

# Format code
ruff format app/ tests/
```

### Developer Setup

See [DEVELOPER_SETUP.md](DEVELOPER_SETUP.md) for detailed development environment setup.

## Security

The Index implements multiple security layers:
- Cryptographic signature verification for attestations
- Input validation with Pydantic
- Placeholder zero-knowledge proofs
- BitRep integration for identity and reputation (planned)

See [SECURITY.md](SECURITY.md) for security principles and vulnerability reporting.

## Governance

The Index uses decentralized governance for:
- Schema evolution
- Ontology updates
- Relation type changes
- Rule modifications

Voting is reputation-weighted with quadratic scaling to promote democratic decision-making.

## Roadmap

- **Phase 1**: Core models and API ✅
- **Phase 2**: Epistemic engine ✅
- **Phase 3**: BitRep integration (in progress)
- **Phase 4**: External integrations (arXiv, CrossRef, PubMed)
- **Phase 5**: Public release and community onboarding

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## Documentation

- [Index Map](INDEX_MAP.md)
- [API Documentation](API_DOCUMENTATION.md)
- [Developer Setup](DEVELOPER_SETUP.md)
- [Security Policy](SECURITY.md)
- [Architecture](roadmap-internal-notes.md)
- [Whitepaper](The_Index_Whitepaper.md)
- [Index Operations](operations/README.md)

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

## Citation

If you use The Index in your research, please cite:

```bibtex
@software{the_index,
  title = {The Index: A Protocol for Verifiable Scientific Knowledge},
  author = {The Index Contributors},
  year = {2024},
  url = {https://github.com/cogno-us/cognous-evidence-registry}
}
```

## Contact

- GitHub Issues: [https://github.com/cogno-us/cognous-evidence-registry/issues](https://github.com/cogno-us/cognous-evidence-registry/issues)
- Discussions: [https://github.com/cogno-us/cognous-evidence-registry/discussions](https://github.com/cogno-us/cognous-evidence-registry/discussions)

## Acknowledgments

Built on the BitRep trust substrate for identity, attestations, and reputation.
