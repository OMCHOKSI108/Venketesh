import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional


def generate_api_key() -> str:
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str, hashed_key: str) -> bool:
    return hash_api_key(api_key) == hashed_key


def generate_token(payload: dict, secret: str, expires_minutes: int = 30) -> str:
    import base64
    import json

    expiry = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    data = {**payload, "exp": expiry.isoformat()}

    encoded = base64.b64encode(json.dumps(data).encode()).decode()
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()

    return f"{encoded}.{signature}"


def validate_token(token: str, secret: str) -> Optional[dict]:
    import base64
    import json

    try:
        encoded, signature = token.split(".")
        expected_signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()

        if signature != expected_signature:
            return None

        data = json.loads(base64.b64decode(encoded))
        exp = datetime.fromisoformat(data.get("exp", ""))

        if exp < datetime.now(timezone.utc):
            return None

        return data
    except Exception:
        return None
