"""
Project access: get project by id, with optional ownership/Admin check for endpoints.
"""
import uuid as _uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.enums import UserRole
from app.db.models import Project, User


def _to_uuid(value: str) -> _uuid.UUID:
    try:
        return _uuid.UUID(value) if isinstance(value, str) else value
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


def get_project_or_404(db: Session, project_id: str) -> Project:
    """Return project by id; raise 404 if not found. Use from background jobs (no user context)."""
    pid = _to_uuid(project_id)
    project = db.query(Project).filter(Project.id == pid).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def get_project_for_user(db: Session, project_id: str, current_user: User) -> Project:
    """Return project by id if current_user may access it (owner or ADMIN); raise 404 or 403."""
    pid = _to_uuid(project_id)
    project = db.query(Project).filter(Project.id == pid).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.created_by_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this project")
    return project
