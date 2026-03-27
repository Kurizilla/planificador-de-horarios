from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import CurrentUser, DbSession
from app.core.security import create_access_token, hash_password, verify_password
from app.core.utils import email_allowed
from app.db.enums import UserRole
from app.db.models import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut)
def register(body: RegisterIn, db: DbSession) -> User:
    if not get_settings().allow_public_registration:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled. Contact an administrator.",
        )
    if not email_allowed(body.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email is not allowed to register. Contact an administrator.",
        )
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.DIRECTOR,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=dict)
def login(body: LoginIn, db: DbSession) -> dict:
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    expires_seconds = get_settings().access_token_expire_minutes * 60
    token = create_access_token(str(user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_seconds,
        "user": UserOut.model_validate(user),
    }


@router.get("/me", response_model=UserOut)
def me(current_user: CurrentUser) -> User:
    return current_user


@router.post("/refresh", response_model=dict)
def refresh(current_user: CurrentUser) -> dict:
    """Return a new access token. Requires a valid (non-expired) Bearer token."""
    expires_seconds = get_settings().access_token_expire_minutes * 60
    token = create_access_token(str(current_user.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_seconds,
    }
