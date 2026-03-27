"""Pydantic schemas for the schedule editing assistant."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field


class AssistantMessageSend(BaseModel):
    content: str
    schedule_version_id: UUID


class AssistantAction(BaseModel):
    type: str  # REASSIGN_TEACHER, MOVE_ENTRY, SWAP_ENTRIES, etc.
    entry_id: Optional[UUID] = None
    changes: dict = Field(default_factory=dict)
    description: str = ""


class AssistantResponse(BaseModel):
    message_id: UUID
    content: str
    reasoning: Optional[str] = None
    proposed_actions: list[AssistantAction] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ApplyActionsRequest(BaseModel):
    message_id: UUID


class AssistantMessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    proposed_actions: Optional[list] = None
    actions_applied: bool
    reasoning: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationRead(BaseModel):
    id: UUID
    project_id: UUID
    schedule_version_id: Optional[UUID] = None
    created_at: datetime
    messages: list[AssistantMessageRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}
