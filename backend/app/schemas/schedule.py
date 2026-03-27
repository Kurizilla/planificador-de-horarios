"""Pydantic schemas for schedule-related entities."""
from __future__ import annotations

from datetime import datetime, time
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# ScheduleVersion
# ---------------------------------------------------------------------------

class ScheduleVersionCreate(BaseModel):
    label: Optional[str] = None
    shift: str


class ScheduleVersionRead(BaseModel):
    id: UUID
    project_id: UUID
    version_number: int
    label: Optional[str] = None
    status: str
    source: str
    parent_version_id: Optional[UUID] = None
    shift: str
    conflicts_count: int
    warnings_count: int
    created_at: datetime
    validated_at: Optional[datetime] = None
    validated_by_id: Optional[UUID] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ScheduleEntry
# ---------------------------------------------------------------------------

class ScheduleEntryRead(BaseModel):
    id: UUID
    schedule_version_id: UUID
    section_id: UUID
    subject_id: UUID
    teacher_id: UUID
    time_slot_id: UUID
    is_locked: bool
    conflict_flags: Optional[list] = None

    # Denormalized for display
    section_code: Optional[str] = None
    section_grade: Optional[int] = None
    subject_name: Optional[str] = None
    subject_code: Optional[str] = None
    subject_color: Optional[str] = None
    teacher_name: Optional[str] = None
    day_of_week: Optional[int] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    slot_order: Optional[int] = None

    model_config = {"from_attributes": True}


class ScheduleEntryUpdate(BaseModel):
    teacher_id: Optional[UUID] = None
    subject_id: Optional[UUID] = None
    is_locked: Optional[bool] = None


# ---------------------------------------------------------------------------
# ScheduleChange
# ---------------------------------------------------------------------------

class ScheduleChangeRead(BaseModel):
    id: UUID
    schedule_version_id: UUID
    change_type: str
    entry_id: Optional[UUID] = None
    previous_values: Optional[dict] = None
    new_values: Optional[dict] = None
    source: str
    description: str
    assistant_message_id: Optional[UUID] = None
    created_at: datetime
    created_by_id: UUID

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Generation request/response
# ---------------------------------------------------------------------------

class GenerateScheduleRequest(BaseModel):
    shift: str
    label: Optional[str] = None


class GenerateScheduleResponse(BaseModel):
    version: ScheduleVersionRead
    entries_count: int
    conflicts_count: int
    warnings_count: int
    unassigned_slots: int


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class ConflictDetail(BaseModel):
    type: str
    severity: str  # "error" | "warning"
    description: str
    affected_entry_ids: list[UUID] = Field(default_factory=list)


class ValidationResult(BaseModel):
    valid: bool
    conflicts: list[ConflictDetail] = Field(default_factory=list)
    warnings: list[ConflictDetail] = Field(default_factory=list)
