"""Pydantic schemas for Project endpoints."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    school_name: Optional[str] = None
    school_code: Optional[str] = None
    academic_year: Optional[str] = None


class ProjectRead(BaseModel):
    id: UUID
    key: str
    name: str
    description: Optional[str] = None
    school_name: Optional[str] = None
    school_code: Optional[str] = None
    academic_year: Optional[str] = None
    status: str
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectList(BaseModel):
    id: UUID
    key: str
    name: str
    description: Optional[str] = None
    school_name: Optional[str] = None
    school_code: Optional[str] = None
    academic_year: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
