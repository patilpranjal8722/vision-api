"""User profile and administrative management endpoints."""

from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserOut

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserOut,
    summary="Retrieve current user profile",
)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return profile information for the currently authenticated user."""
    return current_user


@router.get(
    "/",
    response_model=List[UserOut],
    summary="List all users (Admin only)",
)
def list_users(
    db: Session = Depends(get_db),
    _admin_user: User = Depends(require_role("admin")),
) -> List[User]:
    """Retrieve all registered users. Restricted to users with the 'admin' role."""
    return db.query(User).order_by(User.id).all()
