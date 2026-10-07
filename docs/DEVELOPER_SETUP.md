# Developer Setup Guide

This guide will help you set up your development environment for contributing to The Index.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Quality](#code-quality)
- [Database Setup](#database-setup)
- [IDE Configuration](#ide-configuration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Python 3.9+**: [Download](https://www.python.org/downloads/)
- **Git**: [Download](https://git-scm.com/downloads/)
- **pip**: Usually comes with Python

### Recommended Tools

- **Poetry** (optional): For advanced dependency management
- **Docker** (optional): For containerized development
- **VS Code** or **PyCharm**: Recommended IDEs

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/cogno-us/cognous-evidence-registry.git
cd cognous-evidence-registry
```

### 2. Create Virtual Environment

**Using venv (recommended)**:
```bash
python -m venv venv
```

**Activate the virtual environment**:

On Linux/macOS:
```bash
source venv/bin/activate
```

On Windows:
```bash
venv\Scripts\activate
```

### 3. Install Dependencies

**Production dependencies**:
```bash
pip install -r requirements.txt
```

**Development dependencies** (includes testing, linting, type checking):
```bash
pip install -r requirements-dev.txt
```

**Install in editable mode** (recommended for development):
```bash
pip install -e .
```

### 4. Verify Installation

```bash
# Check Python version
python --version

# Check installed packages
pip list

# Run a quick test
python -c "from app.main import app; print('Installation successful!')"
```

## Development Workflow

### Running the Development Server

**Standard mode**:
```bash
uvicorn app.main:app --reload
```

**Custom host and port**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**With logging**:
```bash
uvicorn app.main:app --reload --log-level debug
```

The server will be available at:
- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Project Structure

```
the-index/
├── app/                    # Main application package
│   ├── api/               # API endpoints (FastAPI routers)
│   │   ├── claims.py      # Claims endpoints
│   │   ├── evidence.py    # Evidence endpoints
│   │   └── governance.py  # Governance endpoints
│   ├── claims/            # Claims business logic
│   │   └── service.py     # Claims service layer
│   ├── evidence/          # Evidence business logic
│   │   └── service.py     # Evidence service layer
│   ├── governance/        # Governance business logic
│   │   ├── models.py      # Governance data models
│   │   └── service.py     # Governance service layer
│   ├── core/              # Core utilities
│   │   ├── config.py      # Configuration management
│   │   ├── models.py      # Shared Pydantic models
│   │   └── security.py    # Security utilities
│   └── main.py            # FastAPI application entry point
├── tests/                 # Test suite
│   ├── conftest.py        # Test fixtures
│   ├── test_claims.py     # Claims unit tests
│   ├── test_evidence.py   # Evidence unit tests
│   ├── test_governance.py # Governance unit tests
│   └── test_api_*.py      # API integration tests
├── docs/                  # Documentation
├── pyproject.toml         # Project configuration
└── requirements.txt       # Production dependencies
```

### Making Changes

1. **Create a new branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Edit code in the `app/` directory
   - Add or update tests in `tests/`
   - Update documentation if needed

3. **Run tests**:
   ```bash
   pytest
   ```

4. **Check code quality**:
   ```bash
   ruff check app/ tests/
   mypy app/
   ```

5. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add your descriptive commit message"
   ```

6. **Push to GitHub**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Create a Pull Request** on GitHub

## Testing

### Running Tests

**All tests**:
```bash
pytest
```

**Specific test file**:
```bash
pytest tests/test_claims.py
```

**Specific test function**:
```bash
pytest tests/test_claims.py::test_create_claim
```

**With verbose output**:
```bash
pytest -v
```

**With coverage report**:
```bash
pytest --cov=app --cov-report=html
```

View coverage report:
```bash
# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

### Writing Tests

Tests are located in the `tests/` directory and use pytest.

**Unit test example**:
```python
def test_create_claim(claims_service, sample_claim_data):
    """Test creating a new claim."""
    claim_data = ClaimCreate(**sample_claim_data)
    claim = claims_service.create_claim(claim_data)
    
    assert claim.id.startswith("claim_")
    assert claim.canonical_text == sample_claim_data["canonical_text"]
```

**API integration test example**:
```python
def test_create_claim_endpoint(client, sample_claim_data):
    """Test POST /api/v1/claims/ endpoint."""
    response = client.post("/api/v1/claims/", json=sample_claim_data)
    
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
```

### Test Fixtures

Common test fixtures are defined in `tests/conftest.py`:
- `client`: TestClient for API testing
- `claims_service`: Fresh ClaimsService instance
- `evidence_service`: Fresh EvidenceService instance
- `governance_service`: Fresh GovernanceService instance
- `sample_claim_data`: Sample claim data
- `sample_evidence_data`: Sample evidence data
- `sample_proposal_data`: Sample proposal data

## Code Quality

### Linting with Ruff

**Check for issues**:
```bash
ruff check app/ tests/
```

**Auto-fix issues**:
```bash
ruff check --fix app/ tests/
```

**Format code**:
```bash
ruff format app/ tests/
```

### Type Checking with Mypy

```bash
mypy app/
```

Fix type errors by adding type hints:
```python
def compute_weight(reputation: float, use_quadratic: bool) -> float:
    """Calculate weighted vote from reputation."""
    if use_quadratic:
        return math.sqrt(reputation)
    return reputation
```

### Pre-commit Hooks

**Install pre-commit** (optional but recommended):
```bash
pip install pre-commit
pre-commit install
```

This will run linting and type checking before each commit.

## Database Setup

**Current Status**: In-memory storage

The current version uses in-memory storage for development. Production will use PostgreSQL.

### Future Database Setup

When database support is added:

1. **Install PostgreSQL**
2. **Create database**:
   ```sql
   CREATE DATABASE the_index;
   ```

3. **Update configuration**:
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost/the_index"
   ```

4. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

## IDE Configuration

### VS Code

**Recommended extensions**:
- Python (Microsoft)
- Pylance
- Python Test Explorer
- Ruff

**Settings** (`.vscode/settings.json`):
```json
{
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "python.formatting.provider": "none",
  "python.testing.pytestEnabled": true,
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  }
}
```

### PyCharm

1. **Set Python interpreter**: File → Settings → Project → Python Interpreter
2. **Enable pytest**: File → Settings → Tools → Python Integrated Tools → Testing
3. **Configure Ruff**: File → Settings → Tools → External Tools

## Environment Variables

Create a `.env` file in the project root:

```bash
# Application
APP_NAME="The Index"
DEBUG=true

# API
API_PREFIX="/api/v1"

# Security
SECRET_KEY="your-secret-key-change-in-production"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=30

# BitRep Integration (Future)
BITREP_ENDPOINT="https://bitrep.example.com"
BITREP_ENABLED=false

# Governance
GOVERNANCE_QUORUM_THRESHOLD=0.5
GOVERNANCE_QUADRATIC_SCALING=true
```

## Docker Setup (Optional)

**Dockerfile** (create if needed):
```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Run with Docker**:
```bash
docker build -t the-index .
docker run -p 8000:8000 the-index
```

## Troubleshooting

### Import Errors

**Problem**: `ModuleNotFoundError: No module named 'app'`

**Solution**:
```bash
# Install in editable mode
pip install -e .

# Or add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Test Failures

**Problem**: Tests failing with shared state

**Solution**: Tests use fresh service instances via fixtures. Ensure you're using the fixtures:
```python
def test_example(claims_service):  # Use fixture
    # Test code
```

### Port Already in Use

**Problem**: `OSError: [Errno 48] Address already in use`

**Solution**:
```bash
# Find and kill process
lsof -i :8000
kill -9 <PID>

# Or use a different port
uvicorn app.main:app --port 8001
```

### Dependency Conflicts

**Problem**: Package version conflicts

**Solution**:
```bash
# Create fresh virtual environment
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

## Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/cogno-us/cognous-evidence-registry/issues)
- **Discussions**: [Ask questions](https://github.com/cogno-us/cognous-evidence-registry/discussions)
- **Documentation**: [Read the docs](https://github.com/cogno-us/cognous-evidence-registry/docs)

## Next Steps

1. Read the [Architecture Documentation](roadmap-internal-notes.md)
2. Explore the [API Documentation](API_DOCUMENTATION.md)
3. Review [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines
4. Check the [Security Policy](SECURITY.md) for security considerations

Happy coding! 🚀
