from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, status
from jose import JWTError, jwt
from jose.utils import base64url_decode

from app.config import settings
from app.utils.exceptions import handle_exceptions


class Auth0Service:
    """Service for handling Auth0 JWT token verification and user management."""

    def __init__(self):
        self.domain = settings.auth0_domain
        self.audience = settings.auth0_audience
        self.issuer = settings.auth0_issuer_url
        self.algorithms = settings.auth0_algorithms
        self._jwks_cache: dict[str, Any] | None = None
        self.name = "auth"

    @handle_exceptions
    async def _get_jwks(self) -> dict[str, Any]:
        """Fetch and cache JWKS (JSON Web Key Set) from Auth0."""
        if self._jwks_cache is None:
            jwks_url = f"https://{self.domain}/.well-known/jwks.json"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(jwks_url)
                response.raise_for_status()
                self._jwks_cache = response.json()
      
                if "keys" not in self._jwks_cache:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Invalid JWKS response: missing 'keys'"
                    )
        return self._jwks_cache

    def _get_signing_key(self, token: str, jwks: dict[str, Any]) -> str:
        """Extract the signing key from JWKS based on token header."""
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            
            if not kid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing 'kid' in header"
                )
            
            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    # Validate RSA key structure - JWKS requires 'n' (modulus) and 'e' (exponent)
                    if "n" not in key or "e" not in key:
                        continue
                    
                    try:
                        # Decode RSA public key components
                        # n = modulus (product of two large primes)
                        # e = exponent (usually 65537)
                        modulus = base64url_decode(key['n'].encode('utf-8'))
                        exponent = base64url_decode(key['e'].encode('utf-8'))
                        
                        public_key = rsa.RSAPublicNumbers(
                            int.from_bytes(exponent, 'big'),
                            int.from_bytes(modulus, 'big')
                        ).public_key()
                        
                        pem_key = public_key.public_bytes(
                            encoding=serialization.Encoding.PEM,
                            format=serialization.PublicFormat.PKCS1
                        )
                        
                        return pem_key.decode('utf-8')
                    except (ValueError, OverflowError) as e:
                        # Skip invalid key and try next one
                        continue

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find appropriate key"
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token header: {str(e)}"
            )

    @handle_exceptions
    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify JWT token and return payload."""
        if not token or not token.strip():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is required"
            )
        
        jwks = await self._get_jwks()
        signing_key = self._get_signing_key(token, jwks)
        
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=self.algorithms,
            audience=self.audience,
            issuer=self.issuer,
        )
        
        return payload

    def get_user_id(self, payload: dict[str, Any]) -> str:
        """Extract user ID from token payload."""
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid payload"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not contain user ID"
            )
        return user_id

    def get_user_email(self, token: str) -> str | None:
        userinfo_url = f"https://{self.domain}/userinfo"
        headers = {"Authorization": f"Bearer {token}"}
        response = httpx.get(userinfo_url, headers=headers)
        response.raise_for_status()
        userinfo = response.json()
        return userinfo.get("email")

    def get_user_permissions(self, payload: dict[str, Any]) -> list[str]:
        """Extract user permissions from token payload."""
        if not payload:
            return []
        
        permissions = payload.get("permissions", [])
        if not isinstance(permissions, list):
            return []
        return permissions


auth0_service = Auth0Service()
