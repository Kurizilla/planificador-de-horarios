"""Export endpoints for schedule data."""
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
import io

from app.core.dependencies import CurrentUser, DbSession
from app.core.project_access import get_project_for_user
from app.db.models import ScheduleVersion
from app.services.schedule_exporter import export_schedule_to_excel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}", tags=["exports"])


@router.get("/schedules/{version_id}/export")
def export_schedule(
    project_id: str,
    version_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Export a schedule version as an Excel file."""
    project = get_project_for_user(db, project_id, current_user)

    # Verify the version belongs to this project
    from uuid import UUID as _UUID
    try:
        vid = _UUID(version_id)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")
    version = (
        db.query(ScheduleVersion)
        .filter(
            ScheduleVersion.id == vid,
            ScheduleVersion.project_id == project.id,
        )
        .first()
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule version not found",
        )

    excel_bytes = export_schedule_to_excel(vid, db)

    filename = f"horario_v{version.version_number}_{version.shift.value}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
