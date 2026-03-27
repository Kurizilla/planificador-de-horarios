from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentAdmin, DbSession
from app.core.security import hash_password
from app.core.utils import email_allowed
from app.db.enums import UserRole
from app.db.models import Project, User
from app.schemas.user import UserCreateIn, UserListItem, UserPasswordUpdateIn, UserUpdateIn

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserListItem])
def list_users(db: DbSession, current_user: CurrentAdmin) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreateIn, db: DbSession, current_user: CurrentAdmin) -> User:
    if not email_allowed(body.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email is not on the whitelist. Add it to USER_WHITELIST to allow.",
        )
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserListItem)
def update_user(
    user_id: str,
    body: UserUpdateIn,
    db: DbSession,
    current_user: CurrentAdmin,
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user_id == current_user.id:
        if body.role is not None and body.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change your own role to non-admin",
            )
        if body.is_active is not None and not body.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate yourself",
            )
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return user


@router.post("/{user_id}/password", response_model=UserListItem)
def update_user_password(
    user_id: str,
    body: UserPasswordUpdateIn,
    db: DbSession,
    current_user: CurrentAdmin,
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: DbSession,
    current_user: CurrentAdmin,
) -> None:
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    has_projects = db.query(Project.id).filter(Project.created_by_id == user_id).first() is not None

    if has_projects:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has associated projects; deactivate instead.",
        )

    db.delete(user)
    db.commit()
