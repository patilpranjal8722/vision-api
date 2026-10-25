"""Comprehensive test suite for authentication, authorization, tokens, and rate limiting."""

from datetime import timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.user import User


# ==============================================================================
# 1. Registration Tests
# ==============================================================================

def test_register_success(client: TestClient) -> None:
    """Test successful user registration returns HTTP 201 and valid UserOut."""
    response = client.post(
        "/auth/register",
        json={
            "email": "alice@example.com",
            "username": "alice_vision",
            "password": "Str0ng!Pass",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "alice@example.com"
    assert data["username"] == "alice_vision"
    assert data["role"] == "user"
    assert data["is_active"] is True
    assert "hashed_password" not in data
    assert "id" in data


def test_register_duplicate_email(client: TestClient) -> None:
    """Test registering with an existing email returns HTTP 409 Conflict."""
    payload = {
        "email": "duplicate_email@example.com",
        "username": "user_alpha",
        "password": "Str0ng!Pass",
    }
    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    payload2 = {
        "email": "duplicate_email@example.com",
        "username": "user_beta",
        "password": "Str0ng!Pass",
    }
    res2 = client.post("/auth/register", json=payload2)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower()


def test_register_duplicate_username(client: TestClient) -> None:
    """Test registering with an existing username returns HTTP 409 Conflict."""
    payload = {
        "email": "user1@example.com",
        "username": "same_handle",
        "password": "Str0ng!Pass",
    }
    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    payload2 = {
        "email": "user2@example.com",
        "username": "same_handle",
        "password": "Str0ng!Pass",
    }
    res2 = client.post("/auth/register", json=payload2)
    assert res2.status_code == 409
    assert "already taken" in res2.json()["detail"].lower()


def test_register_weak_password(client: TestClient) -> None:
    """Test password shorter than 8 characters is rejected with HTTP 422 Unprocessable Entity."""
    response = client.post(
        "/auth/register",
        json={
            "email": "short_pw@example.com",
            "username": "short_pw",
            "password": "short",
        },
    )
    assert response.status_code == 422


def test_register_cannot_create_admin(client: TestClient, db_session: Session) -> None:
    """Test attempting to pass role='admin' in registration payload never creates an admin."""
    response = client.post(
        "/auth/register",
        json={
            "email": "hacker@example.com",
            "username": "wannabe_admin",
            "password": "Str0ng!Pass",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "user"

    # Verify directly in the database
    user = db_session.query(User).filter_by(username="wannabe_admin").first()
    assert user is not None
    assert user.role == "user"


# ==============================================================================
# 2. Login Tests
# ==============================================================================

def test_login_with_email_and_username(client: TestClient) -> None:
    """Test login works using either email or username in the form username field."""
    # Register user first
    reg_res = client.post(
        "/auth/register",
        json={
            "email": "bob@example.com",
            "username": "bob_vision",
            "password": "Str0ng!Pass",
        },
    )
    assert reg_res.status_code == 201

    # Login using email
    login_email = client.post(
        "/auth/login",
        data={"username": "bob@example.com", "password": "Str0ng!Pass"},
    )
    assert login_email.status_code == 200
    token_data = login_email.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Login using username
    login_user = client.post(
        "/auth/login",
        data={"username": "bob_vision", "password": "Str0ng!Pass"},
    )
    assert login_user.status_code == 200
    assert "access_token" in login_user.json()


def test_login_wrong_password_and_unknown_user_same_error(client: TestClient) -> None:
    """Test both wrong password and non-existent user return identical generic 401 messages."""
    client.post(
        "/auth/register",
        json={
            "email": "charlie@example.com",
            "username": "charlie_vision",
            "password": "Str0ng!Pass",
        },
    )

    # 1. Wrong password for existing user
    wrong_pw_res = client.post(
        "/auth/login",
        data={"username": "charlie@example.com", "password": "wrongpassword999"},
    )
    assert wrong_pw_res.status_code == 401
    wrong_pw_msg = wrong_pw_res.json()["detail"]
    assert wrong_pw_msg == "Incorrect credentials"

    # 2. Unknown user
    unknown_user_res = client.post(
        "/auth/login",
        data={"username": "non_existent_user@example.com", "password": "anypassword123"},
    )
    assert unknown_user_res.status_code == 401
    unknown_user_msg = unknown_user_res.json()["detail"]

    # Both errors must have identical error message to prevent account enumeration
    assert unknown_user_msg == wrong_pw_msg


def test_login_inactive_user(client: TestClient, db_session: Session) -> None:
    """Test login is rejected for inactive users with HTTP 401."""
    inactive_user = User(
        email="inactive@example.com",
        username="inactive_user",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=False,
    )
    db_session.add(inactive_user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        data={"username": "inactive@example.com", "password": "password123"},
    )
    assert response.status_code == 401


# ==============================================================================
# 3. /users/me Protected Route Tests
# ==============================================================================

def test_users_me_with_valid_token(client: TestClient) -> None:
    """Test /users/me succeeds with a valid access token."""
    client.post(
        "/auth/register",
        json={
            "email": "david@example.com",
            "username": "david_vision",
            "password": "Str0ng!Pass",
        },
    )
    login_res = client.post(
        "/auth/login",
        data={"username": "david@example.com", "password": "Str0ng!Pass"},
    )
    access_token = login_res.json()["access_token"]

    response = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "david@example.com"
    assert data["username"] == "david_vision"


def test_users_me_token_rejections(client: TestClient) -> None:
    """Test /users/me rejects missing, garbage, expired, and refresh tokens with HTTP 401."""
    # 1. Without token
    res_no_token = client.get("/users/me")
    assert res_no_token.status_code == 401

    # 2. With garbage token
    res_garbage = client.get(
        "/users/me",
        headers={"Authorization": "Bearer not.a.real.jwt.token"},
    )
    assert res_garbage.status_code == 401

    # 3. With expired token
    expired_token = create_access_token(
        subject="1",
        expires_delta=timedelta(seconds=-10),
    )
    res_expired = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res_expired.status_code == 401
    assert "expired" in res_expired.json()["detail"].lower()

    # 4. With REFRESH token used as access token
    refresh_token = create_refresh_token(subject="1")
    res_refresh = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert res_refresh.status_code == 401
    assert "expected 'access'" in res_refresh.json()["detail"].lower()


# ==============================================================================
# 4. Token Refresh Tests
# ==============================================================================

def test_refresh_token_flow(client: TestClient) -> None:
    """Test refreshing an access token with a valid refresh token."""
    client.post(
        "/auth/register",
        json={
            "email": "emma@example.com",
            "username": "emma_vision",
            "password": "Str0ng!Pass",
        },
    )
    login_res = client.post(
        "/auth/login",
        data={"username": "emma@example.com", "password": "Str0ng!Pass"},
    )
    tokens = login_res.json()
    refresh_token = tokens["refresh_token"]

    refresh_res = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens


def test_refresh_token_rejects_access_token(client: TestClient) -> None:
    """Test /auth/refresh rejects an access token with HTTP 401."""
    client.post(
        "/auth/register",
        json={
            "email": "frank@example.com",
            "username": "frank_vision",
            "password": "Str0ng!Pass",
        },
    )
    login_res = client.post(
        "/auth/login",
        data={"username": "frank@example.com", "password": "Str0ng!Pass"},
    )
    access_token = login_res.json()["access_token"]

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": access_token},
    )
    assert response.status_code == 401
    assert "expected 'refresh'" in response.json()["detail"].lower()


# ==============================================================================
# 5. Role-Based Access Control (Admin vs User) Tests
# ==============================================================================

def test_role_enforcement_list_users(client: TestClient, db_session: Session) -> None:
    """Test standard users receive HTTP 403 on GET /users/, while admins receive HTTP 200."""
    # 1. Normal User
    normal_user = User(
        email="regular@example.com",
        username="regular_user",
        hashed_password=hash_password("password123"),
        role="user",
        is_active=True,
    )
    # 2. Admin User
    admin_user = User(
        email="admin@example.com",
        username="admin_user",
        hashed_password=hash_password("password123"),
        role="admin",
        is_active=True,
    )
    db_session.add_all([normal_user, admin_user])
    db_session.commit()
    db_session.refresh(normal_user)
    db_session.refresh(admin_user)

    user_token = create_access_token(subject=normal_user.id)
    admin_token = create_access_token(subject=admin_user.id)

    # Normal user attempt
    user_res = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert user_res.status_code == 403
    assert "insufficient privileges" in user_res.json()["detail"].lower()

    # Admin attempt
    admin_res = client.get(
        "/users/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert admin_res.status_code == 200
    users_list = admin_res.json()
    assert isinstance(users_list, list)
    assert len(users_list) >= 2


# ==============================================================================
# 6. Password Storage Security
# ==============================================================================

def test_password_stored_as_hash(client: TestClient, db_session: Session) -> None:
    """Verify that stored password in the database is an Argon2 hash, never plaintext."""
    raw_password = "Str0ng!Pass"
    client.post(
        "/auth/register",
        json={
            "email": "secure_storage@example.com",
            "username": "secure_storage",
            "password": raw_password,
        },
    )
    user = db_session.query(User).filter_by(username="secure_storage").first()
    assert user is not None
    assert user.hashed_password != raw_password
    assert user.hashed_password.startswith("$argon2")


# ==============================================================================
# 7. Rate Limiting Test
# ==============================================================================

def test_login_rate_limit_exceeded(client: TestClient) -> None:
    """Test that 6 failed login attempts in a row trigger HTTP 429 on the 6th."""
    # Temporarily enable rate limiter for this specific test
    limiter.enabled = True
    limiter.reset()

    try:
        # First 5 attempts should receive 401 Unauthorized
        for i in range(5):
            res = client.post(
                "/auth/login",
                data={"username": "rate_limited_user", "password": "wrongpassword"},
            )
            assert res.status_code == 401, f"Attempt {i+1} failed with status {res.status_code}"

        # 6th attempt should be blocked by slowapi with 429 Too Many Requests
        res_6 = client.post(
            "/auth/login",
            data={"username": "rate_limited_user", "password": "wrongpassword"},
        )
        assert res_6.status_code == 429
        data = res_6.json()
        assert "detail" in data
        assert "rate limit exceeded" in data["detail"].lower()

    finally:
        limiter.reset()
        limiter.enabled = False


# ==============================================================================
# 8. Password Strength Policy Tests
# ==============================================================================

def test_password_strength_rules_individually(client: TestClient) -> None:
    """Test each password complexity rule individually triggers 422 with the exact rule message."""
    # 1. Too short (< 8 chars)
    res_short = client.post(
        "/auth/register",
        json={"email": "short@example.com", "username": "short_user", "password": "Aa1!xyz"},
    )
    assert res_short.status_code == 422
    assert "Password must be at least 8 characters long" in res_short.text
    assert "Password must contain at least one uppercase letter" not in res_short.text
    assert "Password must contain at least one lowercase letter" not in res_short.text
    assert "Password must contain at least one digit" not in res_short.text
    assert "Password must contain at least one special character" not in res_short.text

    # 2. Too long (> 128 chars)
    long_pw = "Str0ng!" + "a" * 125  # 132 chars
    res_long = client.post(
        "/auth/register",
        json={"email": "long@example.com", "username": "long_user", "password": long_pw},
    )
    assert res_long.status_code == 422
    assert "Password must be at most 128 characters long" in res_long.text
    assert "Password must be at least 8 characters long" not in res_long.text

    # 3. Missing uppercase letter
    res_no_upper = client.post(
        "/auth/register",
        json={"email": "noupper@example.com", "username": "noupper_user", "password": "str0ng!pass"},
    )
    assert res_no_upper.status_code == 422
    assert "Password must contain at least one uppercase letter" in res_no_upper.text
    assert "Password must contain at least one lowercase letter" not in res_no_upper.text
    assert "Password must contain at least one digit" not in res_no_upper.text
    assert "Password must contain at least one special character" not in res_no_upper.text

    # 4. Missing lowercase letter
    res_no_lower = client.post(
        "/auth/register",
        json={"email": "nolower@example.com", "username": "nolower_user", "password": "STR0NG!PASS"},
    )
    assert res_no_lower.status_code == 422
    assert "Password must contain at least one lowercase letter" in res_no_lower.text
    assert "Password must contain at least one uppercase letter" not in res_no_lower.text
    assert "Password must contain at least one digit" not in res_no_lower.text
    assert "Password must contain at least one special character" not in res_no_lower.text

    # 5. Missing digit
    res_no_digit = client.post(
        "/auth/register",
        json={"email": "nodigit@example.com", "username": "nodigit_user", "password": "Strong!Pass"},
    )
    assert res_no_digit.status_code == 422
    assert "Password must contain at least one digit" in res_no_digit.text
    assert "Password must contain at least one uppercase letter" not in res_no_digit.text
    assert "Password must contain at least one lowercase letter" not in res_no_digit.text
    assert "Password must contain at least one special character" not in res_no_digit.text

    # 6. Missing special character
    res_no_special = client.post(
        "/auth/register",
        json={"email": "nospec@example.com", "username": "nospec_user", "password": "Str0ngPass"},
    )
    assert res_no_special.status_code == 422
    assert "Password must contain at least one special character" in res_no_special.text
    assert "Password must contain at least one uppercase letter" not in res_no_special.text
    assert "Password must contain at least one lowercase letter" not in res_no_special.text
    assert "Password must contain at least one digit" not in res_no_special.text


def test_password_strength_breaks_several_rules_lists_all(client: TestClient) -> None:
    """Test a password breaking multiple rules lists all unmet rules at once."""
    response = client.post(
        "/auth/register",
        json={"email": "multibad@example.com", "username": "multibad_user", "password": "bad"},
    )
    assert response.status_code == 422
    body = response.text
    assert "Password must be at least 8 characters long" in body
    assert "Password must contain at least one uppercase letter" in body
    assert "Password must contain at least one digit" in body
    assert "Password must contain at least one special character" in body


def test_password_strength_valid_password_registers_fine(client: TestClient) -> None:
    """Test that a compliant password registers successfully."""
    response = client.post(
        "/auth/register",
        json={
            "email": "compliant@example.com",
            "username": "compliant_user",
            "password": "Str0ng!Pass",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "compliant_user"


def test_password_strength_422_response_does_not_contain_password(client: TestClient) -> None:
    """Verify that the 422 response body never leaks the submitted password."""
    secret_bad_password = "SecretPassword123"
    response = client.post(
        "/auth/register",
        json={
            "email": "leakcheck@example.com",
            "username": "leakcheck_user",
            "password": secret_bad_password,
        },
    )
    assert response.status_code == 422
    # Verify the plain password is not anywhere in the raw response text
    assert secret_bad_password not in response.text
    # Verify the 'input' key was stripped from password errors
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    for err in detail:
        if any("password" in str(loc).lower() for loc in err.get("loc", [])):
            assert "input" not in err


def test_login_works_for_legacy_user_with_weak_password(client: TestClient, db_session: Session) -> None:
    """Test that login remains functional for pre-existing users with weak passwords."""
    legacy_password = "simple"
    legacy_user = User(
        email="legacy@example.com",
        username="legacy_user",
        hashed_password=hash_password(legacy_password),
        role="user",
        is_active=True,
    )
    db_session.add(legacy_user)
    db_session.commit()

    # Login must succeed without applying password strength rules
    response = client.post(
        "/auth/login",
        data={"username": "legacy_user", "password": legacy_password},
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_validate_password_strength_unit() -> None:
    """Direct unit tests for validate_password_strength helper."""
    from app.core.security import (
        PASSWORD_MAX_LENGTH,
        PASSWORD_MIN_LENGTH,
        validate_password_strength,
    )

    # Valid password
    assert validate_password_strength("Str0ng!Pass") == []

    # Empty password
    unmet = validate_password_strength("")
    assert f"Password must be at least {PASSWORD_MIN_LENGTH} characters long" in unmet
    assert "Password must contain at least one uppercase letter" in unmet
    assert "Password must contain at least one lowercase letter" in unmet
    assert "Password must contain at least one digit" in unmet
    assert "Password must contain at least one special character" in unmet

    # Length limits
    assert f"Password must be at most {PASSWORD_MAX_LENGTH} characters long" in validate_password_strength("A" * 129 + "a1!")
