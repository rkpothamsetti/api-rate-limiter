import hashlib
import hmac
import secrets

from app.core.config import get_settings


def generate_api_key():
    return "rk_" + secrets.token_urlsafe(32)


def hash_api_key(api_key: str):
    pepper = get_settings().api_key_pepper.encode()
    return hmac.new(
        pepper,
        api_key.encode(),
        hashlib.sha256,
    ).hexdigest()
    