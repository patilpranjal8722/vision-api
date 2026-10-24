"""Security, cryptographic hashing, and JWT token utilities.

Beginner-friendly explanation:
1. Argon2id Password Hashing:
   Passlib is avoided in modern Python in favor of `argon2-cffi`, the winner of
   the Password Hashing Competition. Argon2id protects against GPU-based brute-force
   attacks by requiring both significant memory and CPU time.
2. Timing Attack Mitigation:
   When an unknown user attempts to log in, checking the password usually exits
   immediately if the user is not found. An attacker can measure the response time
   to discover whether a username exists. By hashing a dummy password when the user
   is absent, response times remain indistinguishable.
3. JSON Web Tokens (JWT):
   Tokens are signed with HMAC-SHA256. Access tokens are short-lived (15 minutes)
   and grant API access. Refresh tokens are longer-lived (7 days) and are only
   used to obtain fresh token pairs.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import HTTPException, status

from app.core.config import get_settings

# Initialize the Argon2 password hasher
password_hasher = PasswordHasher()

# Pre-computed dummy hash used to equalize verification latency when a user does not exist
DUMMY_PASSWORD_HASH: str = password_hasher.hash("timing-mitigation-dummy-password")


class TokenError(HTTPException):
    """Exception raised when token decoding or validation fails."""

    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id.

    Args:
        password: Plaintext password string.

    Returns:
        Securely hashed Argon2 string.
    """
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Args:
        plain_password: User-provided plaintext password.
        hashed_password: Stored Argon2 hash.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    try:
        return password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT access token for API authorization.

    Args:
        subject: Subject identifier (typically the integer or string user ID).
        expires_delta: Optional custom lifetime. Defaults to Settings.ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT token string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(
    subject: Union[str, int],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT refresh token for renewing access tokens.

    Args:
        subject: Subject identifier (typically the user ID).
        expires_delta: Optional custom lifetime. Defaults to Settings.REFRESH_TOKEN_EXPIRE_DAYS.

    Returns:
        Encoded JWT refresh token string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    """Decode and validate a JWT token's signature, expiry, and claim type.

    Args:
        token: Raw JWT string.
        expected_type: Expected 'type' claim ('access' or 'refresh').

    Raises:
        TokenError: If the token is expired, invalid, has the wrong type, or lacks a subject.

    Returns:
        Decoded payload dictionary.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise TokenError(detail="Token has expired")
    except jwt.PyJWTError:
        raise TokenError(detail="Invalid token")

    token_type = payload.get("type")
    if token_type != expected_type:
        raise TokenError(detail=f"Invalid token type: expected '{expected_type}', got '{token_type}'")

    if not payload.get("sub"):
        raise TokenError(detail="Token is missing subject claim")

    return payload
