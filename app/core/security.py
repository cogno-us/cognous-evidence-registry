"""
Security utilities for cryptographic operations and authentication.

This module provides:
- Cryptographic signature verification
- Password hashing and verification
- Token generation and validation
- Placeholder zero-knowledge proofs
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate a password hash."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        expires_delta: Optional expiration time delta

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token to verify

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


class SignatureVerifier:
    """
    Cryptographic signature verification for claims and attestations.

    This class provides methods for generating and verifying digital signatures
    using RSA cryptography.
    """

    def __init__(self):
        """Initialize the signature verifier."""
        self.backend = default_backend()

    def generate_keypair(self) -> tuple:
        """
        Generate an RSA keypair for testing.

        Returns:
            Tuple of (private_key, public_key)
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=self.backend
        )
        public_key = private_key.public_key()
        return private_key, public_key

    def sign_data(self, private_key: rsa.RSAPrivateKey, data: bytes) -> bytes:
        """
        Sign data with a private key.

        Args:
            private_key: RSA private key
            data: Data to sign

        Returns:
            Digital signature
        """
        signature = private_key.sign(
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        return signature

    def verify_signature(self, public_key: rsa.RSAPublicKey, signature: bytes, data: bytes) -> bool:
        """
        Verify a signature against data.

        Args:
            public_key: RSA public key
            signature: Digital signature to verify
            data: Original data

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            public_key.verify(
                signature,
                data,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False


class ZKProofPlaceholder:
    """
    Placeholder for zero-knowledge proof functionality.

    This class provides a placeholder implementation for ZK proofs
    that will be expanded in future versions.
    """

    @staticmethod
    def generate_proof(claim_data: Dict[str, Any]) -> str:
        """
        Generate a placeholder ZK proof for claim evidence.

        Args:
            claim_data: Claim data to generate proof for

        Returns:
            Placeholder proof string
        """
        # Placeholder implementation
        # In production, this would use actual ZK proof libraries
        return f"zk_proof_placeholder_{hash(str(claim_data))}"

    @staticmethod
    def verify_proof(proof: str, public_inputs: Dict[str, Any]) -> bool:
        """
        Fail-closed placeholder: no zero-knowledge proof can be verified here.

        A placeholder string is not a proof, so this never reports validity.

        Args:
            proof: ZK proof to verify (ignored)
            public_inputs: Public inputs for verification (ignored)

        Returns:
            Always False
        """
        return False


# Initialize global instances
signature_verifier = SignatureVerifier()
zk_proof = ZKProofPlaceholder()
