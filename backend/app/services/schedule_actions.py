"""
Service for applying assistant-proposed actions to a schedule.

Takes the proposed actions from an AssistantMessage, validates them,
applies changes to ScheduleEntry records, creates ScheduleChange audit
records, and re-runs conflict detection.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.enums import ChangeType, ScheduleSource
from app.db.models import (
    AssistantMessage,
    BusinessRule,
    ScheduleChange,
    ScheduleEntry,
    ScheduleVersion,
    Section,
    Teacher,
    TeacherSubject,
    TimeSlot,
)
from app.schemas.schedule import ScheduleChangeRead
from app.services.schedule_engine import detect_conflicts

logger = logging.getLogger(__name__)

# Map assistant action types to ChangeType enum values
_ACTION_TYPE_MAP = {
    "REASSIGN_TEACHER": ChangeType.REASSIGN,
    "SWAP_ENTRIES": ChangeType.SWAP,
    "REMOVE": ChangeType.REMOVE,
    "LOCK": ChangeType.LOCK,
    "UNLOCK": ChangeType.UNLOCK,
}


def apply_actions(
    schedule_version_id: UUID,
    message_id: UUID,
    db: Session,
    user_id: UUID,
) -> list[ScheduleChangeRead]:
    """Apply proposed actions from an assistant message to the schedule.

    1. Loads the AssistantMessage by ID
    2. Reads proposed_actions from it
    3. For each action: validates and applies the change
    4. Records ScheduleChange audit entries
    5. Marks message as actions_applied = True
    6. Re-runs conflict detection
    7. Returns list of changes made
    """

    # --- 1. Load message ---
    message = db.query(AssistantMessage).filter(AssistantMessage.id == message_id).first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant message not found",
        )

    if message.actions_applied:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Actions from this message have already been applied",
        )

    if not message.proposed_actions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No proposed actions in this message",
        )

    # Verify the schedule version
    version = (
        db.query(ScheduleVersion)
        .filter(ScheduleVersion.id == schedule_version_id)
        .first()
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule version not found",
        )

    project_id = version.project_id

    # Load teacher-subject assignments for validation
    teacher_subjects = (
        db.query(TeacherSubject)
        .filter(TeacherSubject.project_id == project_id)
        .all()
    )
    # Build lookup: (teacher_id, subject_id) -> True
    valid_teacher_subject: set[tuple[UUID, UUID]] = set()
    for ts in teacher_subjects:
        valid_teacher_subject.add((ts.teacher_id, ts.subject_id))

    # --- 2-3. Process each action ---
    changes_made: list[ScheduleChange] = []

    for action_data in message.proposed_actions:
        action_type = action_data.get("type", "")
        entry_id_str = action_data.get("entry_id")
        changes = action_data.get("changes", {})
        description = action_data.get("description", "")

        change_type = _ACTION_TYPE_MAP.get(action_type)
        if not change_type:
            logger.warning("Unknown action type: %s, skipping", action_type)
            continue

        if not entry_id_str:
            logger.warning("Action missing entry_id, skipping: %s", action_data)
            continue

        try:
            entry_id = UUID(str(entry_id_str))
        except (ValueError, AttributeError):
            logger.warning("Invalid entry_id: %s, skipping", entry_id_str)
            continue

        # Load the entry
        entry = (
            db.query(ScheduleEntry)
            .filter(
                ScheduleEntry.id == entry_id,
                ScheduleEntry.schedule_version_id == schedule_version_id,
            )
            .first()
        )
        if not entry:
            logger.warning("Entry %s not found in version %s, skipping", entry_id, schedule_version_id)
            continue

        # Apply based on action type
        if action_type == "REASSIGN_TEACHER":
            new_teacher_id_str = changes.get("teacher_id")
            if not new_teacher_id_str:
                logger.warning("REASSIGN_TEACHER missing teacher_id in changes")
                continue

            try:
                new_teacher_id = UUID(str(new_teacher_id_str))
            except (ValueError, AttributeError):
                logger.warning("Invalid teacher_id: %s", new_teacher_id_str)
                continue

            # Validate teacher exists
            new_teacher = db.query(Teacher).filter(Teacher.id == new_teacher_id).first()
            if not new_teacher:
                logger.warning("Teacher %s not found, skipping", new_teacher_id)
                continue

            # Validate teacher can teach the subject
            if (new_teacher_id, entry.subject_id) not in valid_teacher_subject:
                logger.warning(
                    "Teacher %s cannot teach subject %s, skipping",
                    new_teacher_id, entry.subject_id,
                )
                continue

            previous_teacher_id = entry.teacher_id
            entry.teacher_id = new_teacher_id

            change = ScheduleChange(
                schedule_version_id=schedule_version_id,
                change_type=ChangeType.REASSIGN,
                entry_id=entry.id,
                previous_values={"teacher_id": str(previous_teacher_id)},
                new_values={"teacher_id": str(new_teacher_id)},
                source="assistant",
                description=description or f"Reassign teacher on entry {entry.id}",
                assistant_message_id=message.id,
                created_by_id=user_id,
            )
            db.add(change)
            changes_made.append(change)

        elif action_type == "SWAP_ENTRIES":
            other_entry_id_str = changes.get("other_entry_id")
            if not other_entry_id_str:
                logger.warning("SWAP_ENTRIES missing other_entry_id in changes")
                continue

            try:
                other_entry_id = UUID(str(other_entry_id_str))
            except (ValueError, AttributeError):
                logger.warning("Invalid other_entry_id: %s", other_entry_id_str)
                continue

            other_entry = (
                db.query(ScheduleEntry)
                .filter(
                    ScheduleEntry.id == other_entry_id,
                    ScheduleEntry.schedule_version_id == schedule_version_id,
                )
                .first()
            )
            if not other_entry:
                logger.warning("Other entry %s not found, skipping", other_entry_id)
                continue

            # Swap the time slots
            prev_slot_a = entry.time_slot_id
            prev_slot_b = other_entry.time_slot_id
            entry.time_slot_id = prev_slot_b
            other_entry.time_slot_id = prev_slot_a

            change = ScheduleChange(
                schedule_version_id=schedule_version_id,
                change_type=ChangeType.SWAP,
                entry_id=entry.id,
                previous_values={
                    "entry_a_slot": str(prev_slot_a),
                    "entry_b_slot": str(prev_slot_b),
                },
                new_values={
                    "entry_a_slot": str(prev_slot_b),
                    "entry_b_slot": str(prev_slot_a),
                },
                source="assistant",
                description=description or f"Swap entries {entry.id} and {other_entry.id}",
                assistant_message_id=message.id,
                created_by_id=user_id,
            )
            db.add(change)
            changes_made.append(change)

        elif action_type == "REMOVE":
            previous_values = {
                "subject_id": str(entry.subject_id),
                "teacher_id": str(entry.teacher_id),
                "time_slot_id": str(entry.time_slot_id),
            }
            db.delete(entry)

            change = ScheduleChange(
                schedule_version_id=schedule_version_id,
                change_type=ChangeType.REMOVE,
                entry_id=None,  # entry is being deleted
                previous_values=previous_values,
                new_values=None,
                source="assistant",
                description=description or f"Remove entry {entry_id}",
                assistant_message_id=message.id,
                created_by_id=user_id,
            )
            db.add(change)
            changes_made.append(change)

        elif action_type == "LOCK":
            entry.is_locked = True

            change = ScheduleChange(
                schedule_version_id=schedule_version_id,
                change_type=ChangeType.LOCK,
                entry_id=entry.id,
                previous_values={"is_locked": False},
                new_values={"is_locked": True},
                source="assistant",
                description=description or f"Lock entry {entry.id}",
                assistant_message_id=message.id,
                created_by_id=user_id,
            )
            db.add(change)
            changes_made.append(change)

        elif action_type == "UNLOCK":
            entry.is_locked = False

            change = ScheduleChange(
                schedule_version_id=schedule_version_id,
                change_type=ChangeType.UNLOCK,
                entry_id=entry.id,
                previous_values={"is_locked": True},
                new_values={"is_locked": False},
                source="assistant",
                description=description or f"Unlock entry {entry.id}",
                assistant_message_id=message.id,
                created_by_id=user_id,
            )
            db.add(change)
            changes_made.append(change)

    # --- 4. Mark message as applied ---
    message.actions_applied = True

    # --- 5. Update schedule version source ---
    version.source = ScheduleSource.ASSISTANT_EDIT

    # --- 6. Re-run conflict detection ---
    db.flush()

    all_entries = (
        db.query(ScheduleEntry)
        .filter(ScheduleEntry.schedule_version_id == schedule_version_id)
        .all()
    )
    teachers = (
        db.query(Teacher)
        .filter(
            Teacher.project_id == project_id,
            (Teacher.shift == version.shift) | (Teacher.shift.is_(None)),
        )
        .all()
    )
    sections = (
        db.query(Section)
        .filter(Section.project_id == project_id, Section.shift == version.shift)
        .all()
    )
    time_slots = (
        db.query(TimeSlot)
        .filter(
            TimeSlot.project_id == project_id,
            TimeSlot.shift == version.shift,
            TimeSlot.is_break == False,  # noqa: E712
        )
        .all()
    )
    business_rules = (
        db.query(BusinessRule)
        .filter(
            BusinessRule.project_id == project_id,
            BusinessRule.is_active == True,  # noqa: E712
        )
        .all()
    )

    conflict_details = detect_conflicts(all_entries, teachers, sections, time_slots, business_rules)

    hard_count = sum(1 for c in conflict_details if c.severity == "error")
    warn_count = sum(1 for c in conflict_details if c.severity == "warning")

    version.conflicts_count = hard_count
    version.warnings_count = warn_count

    # Update conflict flags on entries
    entry_conflicts: dict[UUID, list[str]] = defaultdict(list)
    for cd in conflict_details:
        for eid in cd.affected_entry_ids:
            entry_conflicts[eid].append(cd.type)
    for entry in all_entries:
        flags = entry_conflicts.get(entry.id)
        entry.conflict_flags = flags if flags else None

    db.commit()

    # --- 7. Return changes ---
    result: list[ScheduleChangeRead] = []
    for change in changes_made:
        db.refresh(change)
        result.append(ScheduleChangeRead.model_validate(change))

    return result
