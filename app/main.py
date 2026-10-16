"""
The Index - A Protocol for Verifiable Scientific Knowledge

This is the main FastAPI application that provides REST API endpoints
for managing claims, evidence, links, and governance.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import claims, evidence, governance
from app.core.config import settings

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    The Index is a protocol for verifiable scientific knowledge built on BitRep.
    
    ## Features
    
    * **Claims**: Create and manage scientific claims with canonical text and semantic structure
    * **Evidence**: Submit evidence and link it to claims with relation types
    * **Epistemic Status**: Compute reputation-weighted status for claims based on evidence
    * **Governance**: Decentralized proposals and quadratic voting for schema evolution
    
    ## Authentication
    
    Authentication is placeholder-based in this version. Production systems should
    integrate with BitRep for cryptographic identity verification.
    """,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(claims.router, prefix=settings.api_prefix)
app.include_router(evidence.router, prefix=settings.api_prefix)
app.include_router(governance.router, prefix=settings.api_prefix)


@app.get("/")
def read_root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


# This legacy demo API is unauthenticated; the direct-run path binds to
# loopback only. Do not expose it on a network-reachable interface.
DEFAULT_HOST = "127.0.0.1"

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=DEFAULT_HOST, port=8000)
