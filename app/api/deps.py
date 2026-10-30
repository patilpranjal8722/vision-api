"""FastAPI dependency providers for authentication, authorization, and database access."""

from typing import Callable
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

# OAuth2 password bearer scheme pointing to the login endpoint URL
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=True,
)


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate access token from the Authorization header and return the authenticated User.

    Raises:
        HTTPException 401: If the token is invalid, expired, not an access token,
        or if the user does not exist or has been deactivated.
    """
    payload = decode_token(token, expected_type="access")
    sub = payload.get("sub")

    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request.state.user_id = user.id
    return user


def require_role(*roles: str) -> Callable[[User], User]:
    """Factory creating a role-enforcement dependency.

    Args:
        *roles: One or more allowed roles (e.g., 'admin', 'user').

    Returns:
        Dependency function that verifies current_user.role is in allowed roles.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Insufficient privileges",
            )
        return current_user

    return role_checker
