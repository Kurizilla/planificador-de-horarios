"""School data import and query endpoints."""
import logging
import tempfile
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.core.dependencies import CurrentUser, DbSession
from app.core.project_access import get_project_for_user
from app.db.enums import ProjectStatus, Shift
from app.db.models import (
    DataImport,
    GradeSubjectLoad,
    Section,
    Subject,
    Teacher,
    TeacherSubject,
    TimeSlot,
)
from app.schemas.school_data import (
    GradeSubjectLoadDetail,
    ImportSummary,
    SchoolDataSummary,
    SectionRead,
    SubjectRead,
    TeacherRead,
    TeacherSubjectRead,
    TimeSlotRead,
    DataImportRead,
)
from app.services.school_data_parser import parse_school_excel
from app.services.storage import get_storage, _sanitize_path_segment

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}", tags=["school-data"])


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@router.post("/school-data/upload", response_model=ImportSummary)
def upload_school_data(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    school_code: str = Form(...),
):
    """Upload an Excel file with school data (Estudiantes + Docentes sheets)."""
    project = get_project_for_user(db, project_id, current_user)

    # Validate file type
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an Excel file (.xlsx or .xls)",
        )

    # Save uploaded file via storage service
    storage = get_storage()
    safe_filename = _sanitize_path_segment(file.filename)
    rel_path = f"projects/{project.id}/imports/{safe_filename}"
    storage.store(rel_path, file.file)

    # Get the absolute path for pandas to read
    abs_path = str(storage.get_download_path(rel_path))

    # Parse and persist
    summary = parse_school_excel(
        file_path=abs_path,
        school_code=school_code,
        project_id=project.id,
        db=db,
        imported_by_id=current_user.id,
    )

    return summary


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@router.get("/school-data/summary", response_model=SchoolDataSummary)
def get_school_data_summary(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Return counts of all school data entities for this project."""
    project = get_project_for_user(db, project_id, current_user)
    pid = project.id

    imports = db.query(DataImport).filter(DataImport.project_id == pid).all()

    return SchoolDataSummary(
        teachers_count=db.query(Teacher).filter(Teacher.project_id == pid).count(),
        subjects_count=db.query(Subject).filter(Subject.project_id == pid).count(),
        sections_count=db.query(Section).filter(Section.project_id == pid).count(),
        teacher_subjects_count=db.query(TeacherSubject).filter(TeacherSubject.project_id == pid).count(),
        grade_subject_loads_count=db.query(GradeSubjectLoad).filter(GradeSubjectLoad.project_id == pid).count(),
        time_slots_count=db.query(TimeSlot).filter(TimeSlot.project_id == pid).count(),
        data_imports=[DataImportRead.model_validate(i) for i in imports],
    )


# ---------------------------------------------------------------------------
# Teachers
# ---------------------------------------------------------------------------

@router.get("/teachers", response_model=list[TeacherRead])
def list_teachers(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    project = get_project_for_user(db, project_id, current_user)
    teachers = (
        db.query(Teacher)
        .filter(Teacher.project_id == project.id)
        .order_by(Teacher.full_name)
        .all()
    )
    return teachers


# ---------------------------------------------------------------------------
# Subjects
# ---------------------------------------------------------------------------

@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    project = get_project_for_user(db, project_id, current_user)
    subjects = (
        db.query(Subject)
        .filter(Subject.project_id == project.id)
        .order_by(Subject.code)
        .all()
    )
    return subjects


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

@router.get("/sections", response_model=list[SectionRead])
def list_sections(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
    shift: Optional[str] = Query(None, description="Filter by shift: morning or afternoon"),
    grade: Optional[int] = Query(None, description="Filter by grade"),
):
    project = get_project_for_user(db, project_id, current_user)
    q = db.query(Section).filter(Section.project_id == project.id)

    if shift:
        try:
            shift_enum = Shift(shift)
            q = q.filter(Section.shift == shift_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid shift value: {shift}. Must be 'morning' or 'afternoon'.",
            )

    if grade is not None:
        q = q.filter(Section.grade == grade)

    return q.order_by(Section.grade, Section.code).all()


# ---------------------------------------------------------------------------
# Time Slots
# ---------------------------------------------------------------------------

@router.get("/time-slots", response_model=list[TimeSlotRead])
def list_time_slots(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
    shift: Optional[str] = Query(None, description="Filter by shift: morning or afternoon"),
):
    project = get_project_for_user(db, project_id, current_user)
    q = db.query(TimeSlot).filter(TimeSlot.project_id == project.id)

    if shift:
        try:
            shift_enum = Shift(shift)
            q = q.filter(TimeSlot.shift == shift_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid shift value: {shift}. Must be 'morning' or 'afternoon'.",
            )

    return q.order_by(TimeSlot.day_of_week, TimeSlot.slot_order).all()


# ---------------------------------------------------------------------------
# Grade Subject Loads
# ---------------------------------------------------------------------------

@router.get("/grade-loads", response_model=list[GradeSubjectLoadDetail])
def list_grade_subject_loads(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    project = get_project_for_user(db, project_id, current_user)
    loads = (
        db.query(GradeSubjectLoad)
        .filter(GradeSubjectLoad.project_id == project.id)
        .order_by(GradeSubjectLoad.grade)
        .all()
    )

    results = []
    for load in loads:
        subject = db.query(Subject).filter(Subject.id == load.subject_id).first()
        results.append(GradeSubjectLoadDetail(
            id=load.id,
            project_id=load.project_id,
            grade=load.grade,
            subject_id=load.subject_id,
            subject_code=subject.code if subject else None,
            subject_name=subject.name if subject else None,
            hours_per_week=load.hours_per_week,
            created_at=load.created_at,
        ))

    return results


# ---------------------------------------------------------------------------
# Delete all school data
# ---------------------------------------------------------------------------

@router.delete("/school-data", status_code=status.HTTP_204_NO_CONTENT)
def delete_school_data(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
):
    """Delete all school data for a project and reset status to DRAFT."""
    project = get_project_for_user(db, project_id, current_user)
    pid = project.id

    # Delete in dependency order
    db.query(TeacherSubject).filter(TeacherSubject.project_id == pid).delete()
    db.query(GradeSubjectLoad).filter(GradeSubjectLoad.project_id == pid).delete()
    db.query(TimeSlot).filter(TimeSlot.project_id == pid).delete()
    db.query(Section).filter(Section.project_id == pid).delete()
    db.query(Teacher).filter(Teacher.project_id == pid).delete()
    db.query(Subject).filter(Subject.project_id == pid).delete()
    db.query(DataImport).filter(DataImport.project_id == pid).delete()

    # Reset project status
    project.status = ProjectStatus.DRAFT
    db.commit()

    # Clean up stored files
    storage = get_storage()
    storage.delete_tree(f"projects/{pid}/imports")

    return None
