from pydantic_settings import BaseSettings, SettingsConfigDict
from supabase import create_client, Client
from fastapi import Depends, Query, HTTPException
print("[TRACE] settings.py import start")
from typing import Optional
from tuneapi import tt, ta, tu
from polar_sdk import Polar


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=".env",
        env_prefix="ASAM_",
        env_file_encoding="utf-8",
    )

    # database settings
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    # server settings
    host: str = "0.0.0.0"
    port: int = 8000
    prod: bool = False

    backend_url: str = "https://www.arunachalasamudra.co.in"
    frontend_url: str = "https://www.arunachalasamudra.co.in"

    # auth settings
    jwt_secret: str = "placeholder_secret_replace_this_in_production"
    jwt_algorithm: str = "HS256"

    # admin settings
    admin_default_password_length: int = 12
    max_upload_file_size: int = 25
    allowed_upload_extensions: str = "pdf/txt/docx"
    generated_content_retention_days: int = 30
    # Secret used by the /api/admin/make-admin bootstrap endpoint.
    # Set ASAM_ADMIN_SECRET in App Runner environment variables.
    admin_secret: str = "change-me-in-production"

    # model settings
    openai_token: str = "dummy_token"
    # supabase settings
    supabase_url: str = "https://placeholder.supabase.co"
    supabase_key: str = "placeholder_key"
    supabase_service_role_key: str | None = None  # Service role key bypasses RLS

    polar_access_token: str | None = None
    polar_webhook_secret: str | None = None
    polar_base_api: str | None = None
    polar_organization_id: str | None = None

    # Razorpay (Indian payment gateway)
    razorpay_key_id: str | None = "rzp_live_ScxX3vi78mStf5"
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

    # Loops email marketing (newsletter subscriptions)
    loops_api_key: str = "f0e4c2cda1a893524bc7a54c0a10229c"

    # performance settings
    echo_db: bool = False
    content_generation_timeout: int = 300
    audio_compression_timeout: int = 60
    video_encoding_timeout: int = 120
    cache_ttl: int = 3600
    max_parallel_tasks: int = 4
    enable_hardware_acceleration: bool = True
    use_caching: bool = True
    optimize_for_speed: bool = True

    def is_valid_upload_extension(self, extension: str) -> bool:
        return extension.lower() in self.allowed_upload_extensions.split("/")


# ⚠️ DO NOT USE THIS DIRECTLY
# ✅ Correct way to handle global settings
_settings = None

def get_settings() -> Settings:
    global _settings  # Important: declare as global
    if _settings is None:
        print("[TRACE] Loading Settings...")
        try:
            _settings = Settings()
            print("[TRACE] Settings loaded successfully.")
        except Exception as e:
            # Fallback to defaults and log error
            print(f"[TRACE] CRITICAL ERROR loading settings: {e}")
            import traceback
            traceback.print_exc() # Print full stack trace for better debugging
            print("[TRACE] Fallback to construct model...")
            # Create settings with default values (validation will still trigger so we use model_construct)
            _settings = Settings.model_construct()
            # Manually inject some essential defaults if they are not set
            if not hasattr(_settings, "prod"): _settings.prod = False
            if not hasattr(_settings, "db_url"): _settings.db_url = "postgresql+asyncpg://invalid"
    return _settings

# ---------- LLM Helper ----------

def get_llm(model_name: str = "gpt-4o"):
    """Create a TuneAPI model instance with the configured OpenAI token."""
   
    settings_instance = get_settings()
    return  ta.Openai(id="gpt-4o", api_token=settings_instance.openai_token)



# ---------- Supabase Client Helpers ----------

def get_supabase_client(
   settings_instance: Settings = Depends(get_settings)
) -> Client:
    """Create a Supabase client WITHOUT a user JWT."""
    try:
        # Use local variable instead of parameter
    
        actual_settings = settings_instance
        
        if not actual_settings.supabase_url:
            raise ValueError("Supabase URL is empty")
        if not actual_settings.supabase_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid Supabase URL format: {actual_settings.supabase_url}")

        client = create_client(
            actual_settings.supabase_url,
            actual_settings.supabase_key
        )
        return client

    except Exception as e:
        # logger.error("Error creating Supabase client: %s", e)
        raise HTTPException(
            status_code=500,
            detail=e  )



def get_supabase_jwt_client(jwt_token: str,
                            settings_instance: Settings = Depends(get_settings)
                             ) -> Client:

    supabase = create_client(settings_instance.supabase_url, settings_instance.supabase_key)
    supabase.auth._session = {
        "access_token": jwt_token,
        "token_type": "bearer"
    }
    return supabase


def get_supabase_admin_client(
   settings_instance: Settings = Depends(get_settings)
) -> Client:
    """Create a Supabase client with SERVICE ROLE key (bypasses RLS)."""
    try:
        actual_settings = settings_instance
        
        if not actual_settings.supabase_url:
            raise ValueError("Supabase URL is empty")
        if not actual_settings.supabase_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid Supabase URL format: {actual_settings.supabase_url}")
        
        # Use service role key if available, otherwise fall back to regular key
        key = actual_settings.supabase_service_role_key or actual_settings.supabase_key
        
        client = create_client(
            actual_settings.supabase_url,
            key
        )
        return client

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e))




__all__ = ['settings', 'get_settings', 'get_llm', 'get_supabase_client', 'get_supabase_admin_client', 'get_supabase_jwt_client', 'Settings']
