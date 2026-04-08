"""
Razorpay client factory.
Returns a configured razorpay.Client using env-provided credentials.
"""

import razorpay
from src.settings import get_settings


def get_razorpay_client() -> razorpay.Client:
    """Create and return a Razorpay client with configured credentials."""
    settings = get_settings()
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        raise ValueError(
            "Razorpay credentials not configured. "
            "Set ASAM_RAZORPAY_KEY_ID and ASAM_RAZORPAY_KEY_SECRET environment variables."
        )
    return razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


def is_razorpay_enabled() -> bool:
    """Returns True if Razorpay credentials are present in settings."""
    settings = get_settings()
    return bool(settings.razorpay_key_id and settings.razorpay_key_secret)
