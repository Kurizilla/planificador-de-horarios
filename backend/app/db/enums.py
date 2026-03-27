"""Enums for School Schedule Planner."""
import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    DIRECTOR = "director"


class ProjectStatus(str, enum.Enum):
    DRAFT = "draft"
    DATA_LOADED = "data_loaded"
    GENERATED = "generated"
    VALIDATED = "validated"
    EXPORTED = "exported"


class Shift(str, enum.Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"


class ScheduleStatus(str, enum.Enum):
    DRAFT = "draft"
    REVIEW = "review"
    VALIDATED = "validated"
    EXPORTED = "exported"


class ScheduleSource(str, enum.Enum):
    GENERATED = "generated"
    MANUAL_EDIT = "manual_edit"
    ASSISTANT_EDIT = "assistant_edit"


class ChangeType(str, enum.Enum):
    ASSIGN = "assign"
    REASSIGN = "reassign"
    SWAP = "swap"
    REMOVE = "remove"
    LOCK = "lock"
    UNLOCK = "unlock"


class ImportStatus(str, enum.Enum):
    PENDING = "pending"
    PARSED = "parsed"
    VALIDATED = "validated"
    ERROR = "error"


class BusinessRuleType(str, enum.Enum):
    MAX_CONSECUTIVE_HOURS = "max_consecutive_hours"
    NO_SAME_SUBJECT_TWICE_DAY = "no_same_subject_twice_day"
    TEACHER_MAX_DAILY_HOURS = "teacher_max_daily_hours"
    SUBJECT_PREFERRED_SLOT = "subject_preferred_slot"
    SECTION_FREE_PERIOD = "section_free_period"
    CUSTOM = "custom"
