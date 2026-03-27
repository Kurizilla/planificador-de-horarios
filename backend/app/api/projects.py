"""Project CRUD endpoints for School Schedule Planner."""
import logging
import uuid

from fastapi import APIRouter, HTTPException, status

from app.core.dependencies import CurrentUser, DbSession
from app.core.project_access import get_project_for_user
from app.db.enums import UserRole
from app.db.models import Project
from app.schemas.project import ProjectCreate, ProjectList, ProjectRead

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects", tags=["projects"])


def _generate_key() -> str:
    return f"SCH-{uuid.uuid4().hex[:8].upper()}"


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: DbSession, current_user: CurrentUser):
    key = _generate_key()
    while db.query(Project).filter(Project.key == key).first():
        key = _generate_key()
    project = Project(
        key=key,
        name=body.name.strip(),
        description=body.description.strip() if body.description else None,
        school_name=body.school_name.strip() if body.school_name else None,
        school_code=body.school_code.strip() if body.school_code else None,
        academic_year=body.academic_year.strip() if body.academic_year else None,
        created_by_id=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectList])
def list_projects(db: DbSession, current_user: CurrentUser):
    q = db.query(Project).order_by(Project.updated_at.desc())
    if current_user.role != UserRole.ADMIN:
        q = q.filter(Project.created_by_id == current_user.id)
    return q.all()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: DbSession, current_user: CurrentUser):
    project = get_project_for_user(db, project_id, current_user)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: DbSession, current_user: CurrentUser):
    """Delete a project. Irreversible."""
    project = get_project_for_user(db, project_id, current_user)
    db.delete(project)
    db.commit()
    return None
