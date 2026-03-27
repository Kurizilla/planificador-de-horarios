"""Assistant chat endpoints for schedule editing."""
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import CurrentUser, DbSession
from app.core.project_access import get_project_for_user
from app.db.models import AssistantConversation, AssistantMessage
from app.schemas.assistant import (
    ApplyActionsRequest,
    AssistantMessageRead,
    AssistantMessageSend,
    AssistantResponse,
)
from app.schemas.schedule import ScheduleChangeRead
from app.services.schedule_actions import apply_actions
from app.services.schedule_assistant import process_assistant_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/projects/{project_id}", tags=["assistant"])


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@router.post("/assistant/chat", response_model=AssistantResponse)
def chat(
    project_id: str,
    body: AssistantMessageSend,
    db: DbSession,
    current_user: CurrentUser,
):
    """Send a message to the schedule assistant and receive proposed actions."""
    project = get_project_for_user(db, project_id, current_user)

    return process_assistant_message(
        project_id=project.id,
        schedule_version_id=body.schedule_version_id,
        user_message=body.content,
        db=db,
        user_id=current_user.id,
    )


# ---------------------------------------------------------------------------
# Apply actions
# ---------------------------------------------------------------------------

@router.post("/assistant/apply", response_model=list[ScheduleChangeRead])
def apply(
    project_id: str,
    body: ApplyActionsRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Apply the proposed actions from an assistant message to the schedule."""
    project = get_project_for_user(db, project_id, current_user)

    # Find the message and its conversation to get the schedule_version_id
    message = db.query(AssistantMessage).filter(AssistantMessage.id == body.message_id).first()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant message not found",
        )

    conversation = (
        db.query(AssistantConversation)
        .filter(AssistantConversation.id == message.conversation_id)
        .first()
    )
    if not conversation or conversation.project_id != project.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found for this project",
        )

    if not conversation.schedule_version_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversation has no associated schedule version",
        )

    return apply_actions(
        schedule_version_id=conversation.schedule_version_id,
        message_id=body.message_id,
        db=db,
        user_id=current_user.id,
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@router.get("/assistant/history", response_model=list[AssistantMessageRead])
def history(
    project_id: str,
    db: DbSession,
    current_user: CurrentUser,
    schedule_version_id: UUID = Query(..., description="Schedule version to get history for"),
):
    """Get conversation history for a schedule version."""
    project = get_project_for_user(db, project_id, current_user)

    conversation = (
        db.query(AssistantConversation)
        .filter(
            AssistantConversation.project_id == project.id,
            AssistantConversation.schedule_version_id == schedule_version_id,
        )
        .first()
    )
    if not conversation:
        return []

    messages = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation.id)
        .order_by(AssistantMessage.created_at.asc())
        .all()
    )

    return [AssistantMessageRead.model_validate(m) for m in messages]
