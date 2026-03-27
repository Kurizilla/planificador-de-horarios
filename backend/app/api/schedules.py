"""Schedule generation, viewing, and validation endpoints."""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, DbSession
from app.core.project_access import get_project_for_user
from app.db.enums import ScheduleStatus, Shift
from app.db.models import ScheduleChange, ScheduleVersion
from app.schemas.schedule import (
    GenerateScheduleRequest,
    GenerateScheduleResponse,
    ScheduleChangeRead,
    ScheduleEntryRead,
    ScheduleVersionRead,
    ValidationResult,
)
from app.services.schedule_service import (
    generate_schedule,
    get_schedule_entries,
    validate_schedule,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}", tags=["schedules"])


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

@router.post("/schedules/generate", response_model=GenerateScheduleResponse)
def generate(
    project_id: str,
    body: GenerateScheduleRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Generate a new schedule version for the given shift."""
    project = get_project_for_user(db, project_id, current_user)

    try:
        shift_enum = Shift(body.shift)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid shift value: {body.shift}. Must be 'morning' or 'afternoon'.",
        )

    return generate_schedule(
        project_id=project.id,
        shift=shift_enum,
        label=body.label,
        db=db,
        user_id=current_user.id,
    )


# ---------------------------------------------------------------------------
# List / Read versions
# ---------------------------------------------------------------------------

@router.get("/schedules", response_model=list[ScheduleVersionRead])
def list_versions(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Return all schedule versions for this project."""
    project = get_project_for_user(db, project_id, current_user)
    versions = (
        db.query(ScheduleVersion)
        .filter(ScheduleVersion.project_id == project.id)
        .order_by(ScheduleVersion.shift, ScheduleVersion.version_number.desc())
        .all()
    )
    return versions


@router.get("/schedules/{version_id}", response_model=ScheduleVersionRead)
def get_version(
    project_id: str,
    version_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Return a single schedule version."""
    project = get_project_for_user(db, project_id, current_user)

    try:
        vid = UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    version = (
        db.query(ScheduleVersion)
        .filter(ScheduleVersion.id == vid, ScheduleVersion.project_id == project.id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")
    return version


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------

@router.get("/schedules/{version_id}/entries", response_model=list[ScheduleEntryRead])
def list_entries(
    project_id: str,
    version_id: str,
    db: DbSession,
    current_user: CurrentUser,
    section_id: Optional[str] = Query(None, description="Filter entries by section"),
):
    """Return entries for a schedule version, optionally filtered by section."""
    project = get_project_for_user(db, project_id, current_user)

    try:
        vid = UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    # Verify version belongs to this project
    version = (
        db.query(ScheduleVersion)
        .filter(ScheduleVersion.id == vid, ScheduleVersion.project_id == project.id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    sid: UUID | None = None
    if section_id:
        try:
            sid = UUID(section_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid section_id")

    return get_schedule_entries(version_id=vid, db=db, section_id=sid)


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

@router.post("/schedules/{version_id}/validate", response_model=ValidationResult)
def validate(
    project_id: str,
    version_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Run validation checks on a schedule version."""
    project = get_project_for_user(db, project_id, current_user)

    try:
        vid = UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    version = (
        db.query(ScheduleVersion)
        .filter(ScheduleVersion.id == vid, ScheduleVersion.project_id == project.id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    return validate_schedule(version_id=vid, db=db)


@router.post("/schedules/{version_id}/validate-and-approve", response_model=ValidationResult)
def validate_and_approve(
    project_id: str,
    version_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Validate a schedule version; if no hard conflicts, set status to VALIDATED."""
    project = get_project_for_user(db, project_id, current_user)

    try:
        vid = UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    version = (
        db.query(ScheduleVersion)
        .filter(ScheduleVersion.id == vid, ScheduleVersion.project_id == project.id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    result = validate_schedule(version_id=vid, db=db)

    if result.valid:
        from datetime import datetime, timezone

        version.status = ScheduleStatus.VALIDATED
        version.validated_at = datetime.now(timezone.utc)
        version.validated_by_id = current_user.id
        db.commit()
        db.refresh(version)

    return result


# ---------------------------------------------------------------------------
# Changes (audit trail)
# ---------------------------------------------------------------------------

@router.get("/schedules/{version_id}/changes", response_model=list[ScheduleChangeRead])
def list_changes(
    project_id: str,
    version_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Return the change history for a schedule version."""
    project = get_project_for_user(db, project_id, current_user)

    try:
        vid = UUID(version_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    version = (
        db.query(ScheduleVersion)
        .filter(ScheduleVersion.id == vid, ScheduleVersion.project_id == project.id)
        .first()
    )
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    changes = (
        db.query(ScheduleChange)
        .filter(ScheduleChange.schedule_version_id == vid)
        .order_by(ScheduleChange.created_at.desc())
        .all()
    )
    return changes
