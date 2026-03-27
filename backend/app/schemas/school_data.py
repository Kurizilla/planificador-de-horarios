"""Pydantic schemas for school data entities."""
from __future__ import annotations

from datetime import datetime, time
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------

class TeacherCreate(BaseModel):
    full_name: str
    nip: Optional[str] = None
    dui: Optional[str] = None
    id_persona: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    cargo: Optional[str] = None
    specialty: Optional[str] = None
    max_hours_per_week: Optional[int] = None
    shift: Optional[str] = None


class TeacherRead(BaseModel):
    id: UUID
    project_id: UUID
    full_name: str
    nip: Optional[str] = None
    dui: Optional[str] = None
    id_persona: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    cargo: Optional[str] = None
    specialty: Optional[str] = None
    max_hours_per_week: Optional[int] = None
    shift: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Subject
# ---------------------------------------------------------------------------

class SubjectCreate(BaseModel):
    code: str
    name: str
    is_remediation: bool = False
    parent_subject_id: Optional[UUID] = None
    requires_consecutive: bool = False
    color: Optional[str] = None


class SubjectRead(BaseModel):
    id: UUID
    project_id: UUID
    code: str
    name: str
    is_remediation: bool
    parent_subject_id: Optional[UUID] = None
    requires_consecutive: bool
    color: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------

class SectionCreate(BaseModel):
    code: str
    name: str
    grade: int
    shift: str
    student_count: Optional[int] = None
    tipo: Optional[str] = None
    opcion: Optional[str] = None


class SectionRead(BaseModel):
    id: UUID
    project_id: UUID
    code: str
    name: str
    grade: int
    shift: str
    student_count: Optional[int] = None
    tipo: Optional[str] = None
    opcion: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# GradeSubjectLoad
# ---------------------------------------------------------------------------

class GradeSubjectLoadCreate(BaseModel):
    grade: int
    subject_id: UUID
    hours_per_week: int


class GradeSubjectLoadRead(BaseModel):
    id: UUID
    project_id: UUID
    grade: int
    subject_id: UUID
    hours_per_week: int
    created_at: datetime

    model_config = {"from_attributes": True}


class GradeSubjectLoadDetail(BaseModel):
    id: UUID
    project_id: UUID
    grade: int
    subject_id: UUID
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    hours_per_week: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# TeacherSubject
# ---------------------------------------------------------------------------

class TeacherSubjectCreate(BaseModel):
    teacher_id: UUID
    subject_id: UUID
    grade: Optional[int] = None
    section_code: Optional[str] = None
    preference_level: int = 0


class TeacherSubjectRead(BaseModel):
    id: UUID
    project_id: UUID
    teacher_id: UUID
    subject_id: UUID
    grade: Optional[int] = None
    section_code: Optional[str] = None
    preference_level: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# TimeSlot
# ---------------------------------------------------------------------------

class TimeSlotCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=4)
    start_time: time
    end_time: time
    slot_order: int
    shift: str
    is_break: bool = False
    label: Optional[str] = None


class TimeSlotRead(BaseModel):
    id: UUID
    project_id: UUID
    day_of_week: int
    start_time: time
    end_time: time
    slot_order: int
    shift: str
    is_break: bool
    label: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# TeacherAvailability
# ---------------------------------------------------------------------------

class TeacherAvailabilityCreate(BaseModel):
    teacher_id: UUID
    time_slot_id: UUID
    available: bool = True
    reason: Optional[str] = None


class TeacherAvailabilityRead(BaseModel):
    id: UUID
    teacher_id: UUID
    time_slot_id: UUID
    available: bool
    reason: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# BusinessRule
# ---------------------------------------------------------------------------

class BusinessRuleCreate(BaseModel):
    rule_type: str
    description: str
    parameters: Optional[dict] = None
    is_hard: bool = True
    is_active: bool = True


class BusinessRuleRead(BaseModel):
    id: UUID
    project_id: UUID
    rule_type: str
    description: str
    parameters: Optional[dict] = None
    is_hard: bool
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Data Import
# ---------------------------------------------------------------------------

class DataImportRead(BaseModel):
    id: UUID
    project_id: UUID
    filename: str
    file_type: str
    status: str
    row_counts: Optional[dict] = None
    errors: Optional[list] = None
    imported_by_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Import summary (returned after Excel upload)
# ---------------------------------------------------------------------------

class ImportSummary(BaseModel):
    import_id: UUID
    status: str
    teachers_count: int = 0
    subjects_count: int = 0
    sections_count: int = 0
    teacher_subjects_count: int = 0
    grade_subject_loads_count: int = 0
    time_slots_count: int = 0
    errors: list = Field(default_factory=list)
    warnings: list = Field(default_factory=list)


class SchoolDataSummary(BaseModel):
    teachers_count: int = 0
    subjects_count: int = 0
    sections_count: int = 0
    teacher_subjects_count: int = 0
    grade_subject_loads_count: int = 0
    time_slots_count: int = 0
    data_imports: list[DataImportRead] = Field(default_factory=list)
