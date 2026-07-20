"""
FastAPI dependencies for pulling the authenticated user off a bearer token.
Import `CurrentUser` in any endpoint that requires auth.
"""
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.db.models.user import User
from app.db.session import get_db
from app.exceptions import AuthenticationError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise AuthenticationError("Expected an access token")

    user_id = payload.get("sub")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not current_user.is_superuser:
        from app.exceptions import AuthorizationError

        raise AuthorizationError("Superuser privileges required")
    return current_user


CurrentUser = Annotated[User, Depends(get_current_user)]
