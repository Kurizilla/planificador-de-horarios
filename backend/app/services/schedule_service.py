"""
Schedule orchestration service.

Loads data from the database, invokes the planner engine, persists results,
and provides query helpers for schedule versions and entries.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from app.db.enums import (
    ChangeType,
    ProjectStatus,
    ScheduleSource,
    ScheduleStatus,
    Shift,
)
from app.db.models import (
    BusinessRule,
    GradeSubjectLoad,
    Project,
    ScheduleChange,
    ScheduleEntry,
    ScheduleVersion,
    Section,
    Subject,
    Teacher,
    TeacherAvailability,
    TeacherSubject,
    TimeSlot,
)
from app.schemas.schedule import (
    ConflictDetail,
    GenerateScheduleResponse,
    ScheduleChangeRead,
    ScheduleEntryRead,
    ScheduleVersionRead,
    SwapMoveResult,
    ValidationResult,
)
from app.services.schedule_engine import (
    PlanningInput,
    CPSatSchedulePlanner,
    StubSchedulePlanner,
    detect_conflicts,
)

logger = logging.getLogger(__name__)

# Minimum project status required before schedule generation is allowed.
_MIN_STATUS_ORDER = [
    ProjectStatus.DRAFT,
    ProjectStatus.DATA_LOADED,
    ProjectStatus.GENERATED,
    ProjectStatus.VALIDATED,
    ProjectStatus.EXPORTED,
]


def _status_index(s: ProjectStatus) -> int:
    try:
        return _MIN_STATUS_ORDER.index(s)
    except ValueError:
        return -1


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------

def generate_schedule(
    project_id: UUID,
    shift: Shift,
    label: str | None,
    db: Session,
    user_id: UUID,
) -> GenerateScheduleResponse:
    """Generate a schedule for *project_id* / *shift* and persist it."""

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Must be at least DATA_LOADED
    if _status_index(project.status) < _status_index(ProjectStatus.DATA_LOADED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project must have data loaded before generating a schedule.",
        )

    # --- Load data for this shift ---
    sections = (
        db.query(Section)
        .filter(Section.project_id == project_id, Section.shift == shift)
        .order_by(Section.grade, Section.code)
        .all()
    )

    teachers = (
        db.query(Teacher)
        .filter(
            Teacher.project_id == project_id,
            (Teacher.shift == shift) | (Teacher.shift.is_(None)),
        )
        .all()
    )

    subjects = db.query(Subject).filter(Subject.project_id == project_id).all()

    # Grade subject loads for all grades present in this shift's sections
    grades_in_shift = {s.grade for s in sections}
    grade_subject_loads = (
        db.query(GradeSubjectLoad)
        .filter(
            GradeSubjectLoad.project_id == project_id,
            GradeSubjectLoad.grade.in_(grades_in_shift) if grades_in_shift else False,
        )
        .all()
    )

    teacher_subjects = (
        db.query(TeacherSubject)
        .filter(TeacherSubject.project_id == project_id)
        .all()
    )

    time_slots = (
        db.query(TimeSlot)
        .filter(
            TimeSlot.project_id == project_id,
            TimeSlot.shift == shift,
            TimeSlot.is_break == False,  # noqa: E712
        )
        .order_by(TimeSlot.day_of_week, TimeSlot.slot_order)
        .all()
    )

    teacher_ids = {t.id for t in teachers}
    slot_ids = {ts.id for ts in time_slots}
    teacher_availabilities = (
        db.query(TeacherAvailability)
        .filter(
            TeacherAvailability.teacher_id.in_(teacher_ids) if teacher_ids else False,
            TeacherAvailability.time_slot_id.in_(slot_ids) if slot_ids else False,
        )
        .all()
    )

    business_rules = (
        db.query(BusinessRule)
        .filter(BusinessRule.project_id == project_id, BusinessRule.is_active == True)  # noqa: E712
        .all()
    )

    # Build planning input (no locked entries for fresh generation)
    planning_input = PlanningInput(
        sections=sections,
        teachers=teachers,
        subjects=subjects,
        grade_subject_loads=grade_subject_loads,
        teacher_subjects=teacher_subjects,
        time_slots=time_slots,
        teacher_availabilities=teacher_availabilities,
        locked_entries=[],
    )

    # --- Run planner ---
    planner = CPSatSchedulePlanner(time_limit_seconds=30)
    result = planner.generate(planning_input)

    # --- Determine version number ---
    max_version = (
        db.query(sa_func.max(ScheduleVersion.version_number))
        .filter(ScheduleVersion.project_id == project_id, ScheduleVersion.shift == shift)
        .scalar()
    )
    next_version = (max_version or 0) + 1

    # --- Persist version ---
    version = ScheduleVersion(
        project_id=project_id,
        version_number=next_version,
        label=label or f"v{next_version}",
        status=ScheduleStatus.DRAFT,
        source=ScheduleSource.GENERATED,
        shift=shift,
    )
    db.add(version)
    db.flush()  # get version.id

    # --- Persist entries ---
    db_entries: list[ScheduleEntry] = []
    for e in result.entries:
        entry = ScheduleEntry(
            schedule_version_id=version.id,
            section_id=e.section_id,
            subject_id=e.subject_id,
            teacher_id=e.teacher_id,
            time_slot_id=e.time_slot_id,
            is_locked=False,
        )
        db.add(entry)
        db_entries.append(entry)

    db.flush()  # get entry ids for conflict detection

    # --- Conflict detection ---
    conflict_details = detect_conflicts(
        entries=db_entries,
        teachers=teachers,
        sections=sections,
        time_slots=time_slots,
        business_rules=business_rules,
    )

    hard_count = sum(1 for c in conflict_details if c.severity == "error")
    warn_count = sum(1 for c in conflict_details if c.severity == "warning")

    version.conflicts_count = hard_count
    version.warnings_count = warn_count

    # Mark conflict flags on individual entries
    entry_conflicts: dict[UUID, list[str]] = {}
    for cd in conflict_details:
        for eid in cd.affected_entry_ids:
            entry_conflicts.setdefault(eid, []).append(cd.type)
    for entry in db_entries:
        flags = entry_conflicts.get(entry.id)
        if flags:
            entry.conflict_flags = flags

    # --- Record a generation change ---
    change = ScheduleChange(
        schedule_version_id=version.id,
        change_type=ChangeType.ASSIGN,
        source="engine",
        description=f"Generated schedule v{next_version} for {shift.value} shift ({len(db_entries)} entries)",
        created_by_id=user_id,
    )
    db.add(change)

    # --- Update project status ---
    if _status_index(project.status) < _status_index(ProjectStatus.GENERATED):
        project.status = ProjectStatus.GENERATED

    db.commit()
    db.refresh(version)

    return GenerateScheduleResponse(
        version=ScheduleVersionRead.model_validate(version),
        entries_count=len(db_entries),
        conflicts_count=hard_count,
        warnings_count=warn_count,
        unassigned_slots=len(result.unassigned),
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_schedule_entries(
    version_id: UUID,
    db: Session,
    section_id: UUID | None = None,
) -> list[ScheduleEntryRead]:
    """Return entries with denormalized fields for display."""
    q = (
        db.query(
            ScheduleEntry,
            Section.code.label("section_code"),
            Section.grade.label("section_grade"),
            Subject.name.label("subject_name"),
            Subject.code.label("subject_code"),
            Subject.color.label("subject_color"),
            Teacher.full_name.label("teacher_name"),
            TimeSlot.day_of_week,
            TimeSlot.start_time,
            TimeSlot.end_time,
            TimeSlot.slot_order,
        )
        .join(Section, ScheduleEntry.section_id == Section.id)
        .join(Subject, ScheduleEntry.subject_id == Subject.id)
        .join(Teacher, ScheduleEntry.teacher_id == Teacher.id)
        .join(TimeSlot, ScheduleEntry.time_slot_id == TimeSlot.id)
        .filter(ScheduleEntry.schedule_version_id == version_id)
    )

    if section_id:
        q = q.filter(ScheduleEntry.section_id == section_id)

    q = q.order_by(TimeSlot.day_of_week, TimeSlot.slot_order, Section.grade, Section.code)

    results: list[ScheduleEntryRead] = []
    for row in q.all():
        entry = row[0]  # ScheduleEntry ORM object
        results.append(ScheduleEntryRead(
            id=entry.id,
            schedule_version_id=entry.schedule_version_id,
            section_id=entry.section_id,
            subject_id=entry.subject_id,
            teacher_id=entry.teacher_id,
            time_slot_id=entry.time_slot_id,
            is_locked=entry.is_locked,
            conflict_flags=entry.conflict_flags,
            section_code=row.section_code,
            section_grade=row.section_grade,
            subject_name=row.subject_name,
            subject_code=row.subject_code,
            subject_color=row.subject_color,
            teacher_name=row.teacher_name,
            day_of_week=row.day_of_week,
            start_time=row.start_time,
            end_time=row.end_time,
            slot_order=row.slot_order,
        ))

    return results


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _run_conflict_detection_for_version(version: ScheduleVersion, db: Session) -> tuple[list, list]:
    """Load related data and run detect_conflicts for a version.

    Returns (all_conflicts, entries) where entries are eagerly loaded
    with their relationships.
    """
    from sqlalchemy.orm import joinedload

    project_id = version.project_id
    shift = version.shift

    entries = (
        db.query(ScheduleEntry)
        .options(
            joinedload(ScheduleEntry.subject),
            joinedload(ScheduleEntry.teacher),
            joinedload(ScheduleEntry.section),
            joinedload(ScheduleEntry.time_slot),
        )
        .filter(ScheduleEntry.schedule_version_id == version.id)
        .all()
    )

    teachers = (
        db.query(Teacher)
        .filter(
            Teacher.project_id == project_id,
            (Teacher.shift == shift) | (Teacher.shift.is_(None)),
        )
        .all()
    )
    sections = (
        db.query(Section)
        .filter(Section.project_id == project_id, Section.shift == shift)
        .all()
    )
    time_slots = (
        db.query(TimeSlot)
        .filter(
            TimeSlot.project_id == project_id,
            TimeSlot.shift == shift,
            TimeSlot.is_break == False,  # noqa: E712
        )
        .all()
    )
    business_rules = (
        db.query(BusinessRule)
        .filter(BusinessRule.project_id == project_id, BusinessRule.is_active == True)  # noqa: E712
        .all()
    )

    all_conflicts = detect_conflicts(entries, teachers, sections, time_slots, business_rules)
    return all_conflicts, entries


def _update_version_and_entry_conflicts(
    version: ScheduleVersion,
    all_conflicts: list[ConflictDetail],
    entries: list[ScheduleEntry],
    db: Session,
) -> tuple[list[ConflictDetail], list[ConflictDetail]]:
    """Update version counts and entry-level conflict_flags. Returns (errors, warnings)."""
    errors = [c for c in all_conflicts if c.severity == "error"]
    warnings = [c for c in all_conflicts if c.severity == "warning"]

    version.conflicts_count = len(errors)
    version.warnings_count = len(warnings)

    # Build per-entry conflict flags
    entry_conflicts: dict[UUID, list[str]] = {}
    for cd in all_conflicts:
        for eid in cd.affected_entry_ids:
            entry_conflicts.setdefault(eid, []).append(cd.type)

    for entry in entries:
        flags = entry_conflicts.get(entry.id)
        entry.conflict_flags = flags if flags else None

    return errors, warnings


# ---------------------------------------------------------------------------
# Swap / Move
# ---------------------------------------------------------------------------

def swap_entries(
    version_id: UUID,
    entry_id_a: UUID,
    entry_id_b: UUID,
    db: Session,
    user_id: UUID,
) -> SwapMoveResult:
    """Swap the time slots of two entries within the same version."""
    entry_a = db.query(ScheduleEntry).filter(ScheduleEntry.id == entry_id_a).first()
    entry_b = db.query(ScheduleEntry).filter(ScheduleEntry.id == entry_id_b).first()

    if not entry_a or not entry_b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or both entries not found")

    if entry_a.schedule_version_id != version_id or entry_b.schedule_version_id != version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both entries must belong to the specified schedule version",
        )

    if entry_a.is_locked or entry_b.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot swap locked entries",
        )

    # Swap time_slot_ids using raw SQL to avoid UNIQUE constraint collision
    old_slot_a = entry_a.time_slot_id
    old_slot_b = entry_b.time_slot_id

    from sqlalchemy import text
    db.execute(
        text("UPDATE schedule_entries SET time_slot_id = :slot WHERE id = :eid"),
        {"slot": str(old_slot_b), "eid": str(entry_a.id)},
    )
    db.execute(
        text("UPDATE schedule_entries SET time_slot_id = :slot WHERE id = :eid"),
        {"slot": str(old_slot_a), "eid": str(entry_b.id)},
    )
    # Refresh ORM objects
    db.expire(entry_a)
    db.expire(entry_b)

    # Record changes
    change_a = ScheduleChange(
        schedule_version_id=version_id,
        change_type=ChangeType.SWAP,
        entry_id=entry_a.id,
        previous_values={"time_slot_id": str(old_slot_a)},
        new_values={"time_slot_id": str(old_slot_b)},
        source="manual",
        description=f"Swapped entry time slot (part of swap with {entry_id_b})",
        created_by_id=user_id,
    )
    change_b = ScheduleChange(
        schedule_version_id=version_id,
        change_type=ChangeType.SWAP,
        entry_id=entry_b.id,
        previous_values={"time_slot_id": str(old_slot_b)},
        new_values={"time_slot_id": str(old_slot_a)},
        source="manual",
        description=f"Swapped entry time slot (part of swap with {entry_id_a})",
        created_by_id=user_id,
    )
    db.add(change_a)
    db.add(change_b)
    db.flush()

    # Re-run conflict detection
    version = db.query(ScheduleVersion).filter(ScheduleVersion.id == version_id).first()
    all_conflicts, entries = _run_conflict_detection_for_version(version, db)
    errors, warnings = _update_version_and_entry_conflicts(version, all_conflicts, entries, db)

    db.commit()

    # Build response entries
    entry_reads = get_schedule_entries(version_id=version_id, db=db)
    return SwapMoveResult(entries=entry_reads, conflicts=errors, warnings=warnings)


def move_entry_to_slot(
    version_id: UUID,
    entry_id: UUID,
    target_time_slot_id: UUID,
    db: Session,
    user_id: UUID,
) -> SwapMoveResult:
    """Move an entry to a different time slot. If the target slot has an entry for the
    same section in this version, swap them."""
    entry = db.query(ScheduleEntry).filter(ScheduleEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")

    if entry.schedule_version_id != version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Entry does not belong to the specified schedule version",
        )

    if entry.is_locked:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot move a locked entry",
        )

    old_slot = entry.time_slot_id

    if old_slot == target_time_slot_id:
        # No-op: already in the target slot
        entry_reads = get_schedule_entries(version_id=version_id, db=db)
        return SwapMoveResult(entries=entry_reads, conflicts=[], warnings=[])

    # Check if there is already an entry for the same section in the target slot
    existing = (
        db.query(ScheduleEntry)
        .filter(
            ScheduleEntry.schedule_version_id == version_id,
            ScheduleEntry.section_id == entry.section_id,
            ScheduleEntry.time_slot_id == target_time_slot_id,
        )
        .first()
    )

    if existing:
        # Swap both entries
        if existing.is_locked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot swap with a locked entry in the target slot",
            )

        # Use raw SQL to avoid UNIQUE constraint collision during swap
        from sqlalchemy import text
        db.execute(
            text("UPDATE schedule_entries SET time_slot_id = :slot WHERE id = :eid"),
            {"slot": str(old_slot), "eid": str(existing.id)},
        )
        db.execute(
            text("UPDATE schedule_entries SET time_slot_id = :slot WHERE id = :eid"),
            {"slot": str(target_time_slot_id), "eid": str(entry.id)},
        )
        db.expire(existing)
        db.expire(entry)

        change_existing = ScheduleChange(
            schedule_version_id=version_id,
            change_type=ChangeType.SWAP,
            entry_id=existing.id,
            previous_values={"time_slot_id": str(target_time_slot_id)},
            new_values={"time_slot_id": str(old_slot)},
            source="manual",
            description=f"Moved to vacated slot (swap triggered by move of entry {entry_id})",
            created_by_id=user_id,
        )
        db.add(change_existing)

        change_entry = ScheduleChange(
            schedule_version_id=version_id,
            change_type=ChangeType.SWAP,
            entry_id=entry.id,
            previous_values={"time_slot_id": str(old_slot)},
            new_values={"time_slot_id": str(target_time_slot_id)},
            source="manual",
            description=f"Moved entry to target slot (swapped with entry {existing.id})",
            created_by_id=user_id,
        )
        db.add(change_entry)
    else:
        # Simple move
        entry.time_slot_id = target_time_slot_id

        change = ScheduleChange(
            schedule_version_id=version_id,
            change_type=ChangeType.REASSIGN,
            entry_id=entry.id,
            previous_values={"time_slot_id": str(old_slot)},
            new_values={"time_slot_id": str(target_time_slot_id)},
            source="manual",
            description="Moved entry to empty time slot",
            created_by_id=user_id,
        )
        db.add(change)

    db.flush()

    # Re-run conflict detection
    version = db.query(ScheduleVersion).filter(ScheduleVersion.id == version_id).first()
    all_conflicts, entries = _run_conflict_detection_for_version(version, db)
    errors, warnings = _update_version_and_entry_conflicts(version, all_conflicts, entries, db)

    db.commit()

    entry_reads = get_schedule_entries(version_id=version_id, db=db)
    return SwapMoveResult(entries=entry_reads, conflicts=errors, warnings=warnings)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_schedule(version_id: UUID, db: Session) -> ValidationResult:
    """Run conflict detection on an existing schedule version."""
    version = db.query(ScheduleVersion).filter(ScheduleVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    entries = db.query(ScheduleEntry).filter(ScheduleEntry.schedule_version_id == version_id).all()

    project_id = version.project_id
    shift = version.shift

    teachers = (
        db.query(Teacher)
        .filter(
            Teacher.project_id == project_id,
            (Teacher.shift == shift) | (Teacher.shift.is_(None)),
        )
        .all()
    )
    sections = (
        db.query(Section)
        .filter(Section.project_id == project_id, Section.shift == shift)
        .all()
    )
    time_slots = (
        db.query(TimeSlot)
        .filter(
            TimeSlot.project_id == project_id,
            TimeSlot.shift == shift,
            TimeSlot.is_break == False,  # noqa: E712
        )
        .all()
    )
    business_rules = (
        db.query(BusinessRule)
        .filter(BusinessRule.project_id == project_id, BusinessRule.is_active == True)  # noqa: E712
        .all()
    )

    all_conflicts = detect_conflicts(entries, teachers, sections, time_slots, business_rules)

    errors = [c for c in all_conflicts if c.severity == "error"]
    warnings = [c for c in all_conflicts if c.severity == "warning"]

    # Update counts on the version
    version.conflicts_count = len(errors)
    version.warnings_count = len(warnings)
    db.commit()

    return ValidationResult(
        valid=len(errors) == 0,
        conflicts=errors,
        warnings=warnings,
    )
