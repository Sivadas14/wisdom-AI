import jwt
from jwt import PyJWKClient
from typing import Optional, Any
from src.llm_shim import tu
from src.settings import get_settings

class SupabaseJWKS:
    """
    Wrapper for PyJWKClient to handle Supabase JWKS.
    """
    def __init__(self):
        self._client: Optional[PyJWKClient] = None
        self._jwks_url: Optional[str] = None

    @property
    def jwks_url(self) -> str:
        if not self._jwks_url:
            settings = get_settings()
            base_url = settings.supabase_url.rstrip('/')
            self._jwks_url = f"{base_url}/auth/v1/.well-known/jwks.json"
        return self._jwks_url

    @property
    def client(self) -> PyJWKClient:
        if not self._client:
            tu.logger.info(f"Initializing JWKS Client for {self.jwks_url}")
            self._client = PyJWKClient(self.jwks_url)
        return self._client

    def get_signing_key(self, token: str) -> Any:
        """Get the signing key for a specific token."""
        return self.client.get_signing_key_from_jwt(token)

# Global instance
_supabase_jwks = SupabaseJWKS()

def verify_supabase_jwt(token: str) -> dict:
    """
    Verify a Supabase JWT locally using JWKS.
    """
    try:
        signing_key = _supabase_jwks.get_signing_key(token)
        # Use ES256 as found in the user's token header
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated"
        )
        return payload
    except Exception as e:
        tu.logger.error(f"JWKS Verification failed: {str(e)}")
        raise
