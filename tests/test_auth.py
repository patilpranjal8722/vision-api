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
            "password": "securepassword123",
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
        "password": "securepassword123",
    }
    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    payload2 = {
        "email": "duplicate_email@example.com",
        "username": "user_beta",
        "password": "securepassword123",
    }
    res2 = client.post("/auth/register", json=payload2)
    assert res2.status_code == 409
    assert "already registered" in res2.json()["detail"].lower()


def test_register_duplicate_username(client: TestClient) -> None:
    """Test registering with an existing username returns HTTP 409 Conflict."""
    payload = {
        "email": "user1@example.com",
        "username": "same_handle",
        "password": "securepassword123",
    }
    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == 201

    payload2 = {
        "email": "user2@example.com",
        "username": "same_handle",
        "password": "securepassword123",
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
            "password": "securepassword123",
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
            "password": "mypassword123",
        },
    )
    assert reg_res.status_code == 201

    # Login using email
    login_email = client.post(
        "/auth/login",
        data={"username": "bob@example.com", "password": "mypassword123"},
    )
    assert login_email.status_code == 200
    token_data = login_email.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Login using username
    login_user = client.post(
        "/auth/login",
        data={"username": "bob_vision", "password": "mypassword123"},
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
            "password": "mypassword123",
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
            "password": "password123",
        },
    )
    login_res = client.post(
        "/auth/login",
        data={"username": "david@example.com", "password": "password123"},
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
            "password": "password123",
        },
    )
    login_res = client.post(
        "/auth/login",
        data={"username": "emma@example.com", "password": "password123"},
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
            "password": "password123",
        },
    )
    login_res = client.post(
        "/auth/login",
        data={"username": "frank@example.com", "password": "password123"},
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
    raw_password = "plaintext_secret_123"
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
