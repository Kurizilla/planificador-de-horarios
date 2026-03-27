"""Database models for School Schedule Planner."""
import uuid

from sqlalchemy import (
    Column, String, Boolean, DateTime, Text, Integer, Float,
    ForeignKey, Enum as SAEnum, UniqueConstraint, Time, JSON,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base
from app.db.enums import (
    UserRole, ProjectStatus, Shift, ScheduleStatus, ScheduleSource,
    ChangeType, ImportStatus, BusinessRuleType,
)


# ---------------------------------------------------------------------------
# Identity & Access
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(
        SAEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        default=UserRole.DIRECTOR,
    )
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    projects = relationship("Project", back_populates="created_by", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email}>"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    school_name = Column(String(255), nullable=True)
    school_code = Column(String(50), nullable=True)
    academic_year = Column(String(20), nullable=True)
    status = Column(
        SAEnum(ProjectStatus, name="project_status", create_constraint=True),
        nullable=False,
        default=ProjectStatus.DRAFT,
    )
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    created_by = relationship("User", back_populates="projects")
    teachers = relationship("Teacher", back_populates="project", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="project", cascade="all, delete-orphan")
    sections = relationship("Section", back_populates="project", cascade="all, delete-orphan")
    time_slots = relationship("TimeSlot", back_populates="project", cascade="all, delete-orphan")
    teacher_subjects = relationship("TeacherSubject", back_populates="project", cascade="all, delete-orphan")
    business_rules = relationship("BusinessRule", back_populates="project", cascade="all, delete-orphan")
    schedule_versions = relationship("ScheduleVersion", back_populates="project", cascade="all, delete-orphan")
    data_imports = relationship("DataImport", back_populates="project", cascade="all, delete-orphan")
    assistant_conversations = relationship("AssistantConversation", back_populates="project", cascade="all, delete-orphan")
    grade_subject_loads = relationship("GradeSubjectLoad", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project {self.key}: {self.name}>"


# ---------------------------------------------------------------------------
# School Data
# ---------------------------------------------------------------------------

class Teacher(Base):
    __tablename__ = "teachers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    nip = Column(String(50), nullable=True)
    dui = Column(String(50), nullable=True)
    id_persona = Column(String(50), nullable=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    cargo = Column(String(100), nullable=True)
    specialty = Column(String(255), nullable=True)
    max_hours_per_week = Column(Integer, nullable=True)
    shift = Column(SAEnum(Shift, name="shift_enum", create_constraint=False), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="teachers")
    teacher_subjects = relationship("TeacherSubject", back_populates="teacher", cascade="all, delete-orphan")
    availabilities = relationship("TeacherAvailability", back_populates="teacher", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "nip", name="uq_teacher_project_nip"),
    )

    def __repr__(self):
        return f"<Teacher {self.full_name}>"


class Subject(Base):
    __tablename__ = "subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    is_remediation = Column(Boolean, default=False, nullable=False)
    parent_subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=True)
    requires_consecutive = Column(Boolean, default=False, nullable=False)
    color = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="subjects")
    parent_subject = relationship("Subject", remote_side="Subject.id")
    teacher_subjects = relationship("TeacherSubject", back_populates="subject", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "code", name="uq_subject_project_code"),
    )

    def __repr__(self):
        return f"<Subject {self.code}: {self.name}>"


class Section(Base):
    __tablename__ = "sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    grade = Column(Integer, nullable=False)
    shift = Column(SAEnum(Shift, name="shift_enum", create_constraint=False), nullable=False)
    student_count = Column(Integer, nullable=True)
    tipo = Column(String(100), nullable=True)
    opcion = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="sections")

    __table_args__ = (
        UniqueConstraint("project_id", "grade", "code", "shift", name="uq_section_project_grade_code_shift"),
    )

    def __repr__(self):
        return f"<Section G{self.grade}{self.code} ({self.shift.value})>"


class GradeSubjectLoad(Base):
    """Hours per week that each grade requires for each subject.

    Derived from the Carga Horaria rules (PDF). Each row says:
    grade X needs Y classes/week of subject Z (including RE variants).
    """
    __tablename__ = "grade_subject_loads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    grade = Column(Integer, nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    hours_per_week = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="grade_subject_loads")
    subject = relationship("Subject")

    __table_args__ = (
        UniqueConstraint("project_id", "grade", "subject_id", name="uq_grade_subject_load"),
    )


class TeacherSubject(Base):
    """N:M — which subjects a teacher can teach, optionally scoped to grade/section."""
    __tablename__ = "teacher_subjects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    grade = Column(Integer, nullable=True)
    section_code = Column(String(50), nullable=True)
    preference_level = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="teacher_subjects")
    teacher = relationship("Teacher", back_populates="teacher_subjects")
    subject = relationship("Subject", back_populates="teacher_subjects")

    __table_args__ = (
        UniqueConstraint("teacher_id", "subject_id", "grade", "section_code",
                         name="uq_teacher_subject_grade_section"),
    )


class TimeSlot(Base):
    """A single period in the weekly timetable grid."""
    __tablename__ = "time_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday … 4=Friday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    slot_order = Column(Integer, nullable=False)
    shift = Column(SAEnum(Shift, name="shift_enum", create_constraint=False), nullable=False)
    is_break = Column(Boolean, default=False, nullable=False)
    label = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="time_slots")

    __table_args__ = (
        UniqueConstraint("project_id", "day_of_week", "start_time", "shift",
                         name="uq_timeslot_project_day_start_shift"),
        CheckConstraint("day_of_week >= 0 AND day_of_week <= 4", name="ck_timeslot_day_range"),
    )


class TeacherAvailability(Base):
    """Marks a teacher as unavailable for a specific time slot."""
    __tablename__ = "teacher_availabilities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    time_slot_id = Column(UUID(as_uuid=True), ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False)
    available = Column(Boolean, default=True, nullable=False)
    reason = Column(String(255), nullable=True)

    teacher = relationship("Teacher", back_populates="availabilities")
    time_slot = relationship("TimeSlot")

    __table_args__ = (
        UniqueConstraint("teacher_id", "time_slot_id", name="uq_teacher_availability"),
    )


class BusinessRule(Base):
    __tablename__ = "business_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_type = Column(
        SAEnum(BusinessRuleType, name="business_rule_type", create_constraint=True),
        nullable=False,
    )
    description = Column(Text, nullable=False)
    parameters = Column(JSON, nullable=True)
    is_hard = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="business_rules")


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

class ScheduleVersion(Base):
    __tablename__ = "schedule_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    label = Column(String(255), nullable=True)
    status = Column(
        SAEnum(ScheduleStatus, name="schedule_status", create_constraint=True),
        nullable=False,
        default=ScheduleStatus.DRAFT,
    )
    source = Column(
        SAEnum(ScheduleSource, name="schedule_source", create_constraint=True),
        nullable=False,
        default=ScheduleSource.GENERATED,
    )
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("schedule_versions.id"), nullable=True)
    shift = Column(SAEnum(Shift, name="shift_enum", create_constraint=False), nullable=False)
    conflicts_count = Column(Integer, default=0, nullable=False)
    warnings_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    validated_at = Column(DateTime(timezone=True), nullable=True)
    validated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    project = relationship("Project", back_populates="schedule_versions")
    parent_version = relationship("ScheduleVersion", remote_side="ScheduleVersion.id")
    entries = relationship("ScheduleEntry", back_populates="schedule_version", cascade="all, delete-orphan")
    changes = relationship("ScheduleChange", back_populates="schedule_version", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "version_number", "shift",
                         name="uq_schedule_version_project_number_shift"),
    )


class ScheduleEntry(Base):
    """One cell in the timetable: section × time_slot → subject + teacher."""
    __tablename__ = "schedule_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_version_id = Column(UUID(as_uuid=True), ForeignKey("schedule_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id = Column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("teachers.id"), nullable=False)
    time_slot_id = Column(UUID(as_uuid=True), ForeignKey("time_slots.id"), nullable=False)
    is_locked = Column(Boolean, default=False, nullable=False)
    conflict_flags = Column(JSON, nullable=True)

    schedule_version = relationship("ScheduleVersion", back_populates="entries")
    section = relationship("Section")
    subject = relationship("Subject")
    teacher = relationship("Teacher")
    time_slot = relationship("TimeSlot")

    __table_args__ = (
        UniqueConstraint("schedule_version_id", "section_id", "time_slot_id",
                         name="uq_entry_version_section_slot"),
    )


class ScheduleChange(Base):
    """Audit trail for modifications to a schedule version."""
    __tablename__ = "schedule_changes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_version_id = Column(UUID(as_uuid=True), ForeignKey("schedule_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    change_type = Column(
        SAEnum(ChangeType, name="change_type", create_constraint=True),
        nullable=False,
    )
    entry_id = Column(UUID(as_uuid=True), ForeignKey("schedule_entries.id"), nullable=True)
    previous_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    source = Column(String(50), nullable=False)  # "assistant", "manual", "engine"
    description = Column(Text, nullable=False)
    assistant_message_id = Column(UUID(as_uuid=True), ForeignKey("assistant_messages.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    schedule_version = relationship("ScheduleVersion", back_populates="changes")
    entry = relationship("ScheduleEntry")
    assistant_message = relationship("AssistantMessage")
    created_by = relationship("User")


# ---------------------------------------------------------------------------
# Assistant
# ---------------------------------------------------------------------------

class AssistantConversation(Base):
    __tablename__ = "assistant_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    schedule_version_id = Column(UUID(as_uuid=True), ForeignKey("schedule_versions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="assistant_conversations")
    schedule_version = relationship("ScheduleVersion")
    messages = relationship("AssistantMessage", back_populates="conversation", cascade="all, delete-orphan")


class AssistantMessage(Base):
    __tablename__ = "assistant_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("assistant_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    proposed_actions = Column(JSON, nullable=True)
    actions_applied = Column(Boolean, default=False, nullable=False)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    conversation = relationship("AssistantConversation", back_populates="messages")


# ---------------------------------------------------------------------------
# Data Import
# ---------------------------------------------------------------------------

class DataImport(Base):
    __tablename__ = "data_imports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    storage_path = Column(String(500), nullable=False)
    status = Column(
        SAEnum(ImportStatus, name="import_status", create_constraint=True),
        nullable=False,
        default=ImportStatus.PENDING,
    )
    row_counts = Column(JSON, nullable=True)
    errors = Column(JSON, nullable=True)
    imported_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="data_imports")
    imported_by = relationship("User")
