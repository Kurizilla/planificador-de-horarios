"""
Schedule editing assistant service.

Interprets natural-language instructions from the school director, builds
a compact schedule representation for the LLM, calls xAI Grok, and returns
structured actions that can be applied to the schedule.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections import defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.enums import ChangeType
from app.db.models import (
    AssistantConversation,
    AssistantMessage,
    BusinessRule,
    Project,
    ScheduleEntry,
    ScheduleVersion,
    Section,
    Subject,
    Teacher,
    TeacherSubject,
    TimeSlot,
)
from app.schemas.assistant import AssistantAction, AssistantResponse

logger = logging.getLogger(__name__)

# Day names in Spanish for the schedule table
_DAY_NAMES = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_time(t) -> str:
    """Format a time object as HH:MM."""
    if t is None:
        return "??:??"
    return t.strftime("%H:%M")


def _build_schedule_text(
    entries: list[ScheduleEntry],
    sections: list[Section],
    teachers: list[Teacher],
    subjects: list[Subject],
    time_slots: list[TimeSlot],
) -> str:
    """Build a compact text representation of the schedule for the LLM context."""

    section_map = {s.id: s for s in sections}
    teacher_map = {t.id: t for t in teachers}
    subject_map = {s.id: s for s in subjects}
    slot_map = {ts.id: ts for ts in time_slots}

    # Group entries by section
    entries_by_section: dict[UUID, list[ScheduleEntry]] = defaultdict(list)
    for entry in entries:
        entries_by_section[entry.section_id].append(entry)

    # Collect unique time ranges per day for the header
    # Group slots by day_of_week, sorted by slot_order
    slots_by_day: dict[int, list[TimeSlot]] = defaultdict(list)
    for ts in time_slots:
        if not ts.is_break:
            slots_by_day[ts.day_of_week].append(ts)
    for day in slots_by_day:
        slots_by_day[day].sort(key=lambda s: s.slot_order)

    # Unique time ranges (start_time, end_time) across all days, sorted
    time_ranges: list[tuple] = []
    seen_ranges: set[tuple] = set()
    for day in sorted(slots_by_day.keys()):
        for ts in slots_by_day[day]:
            key = (ts.start_time, ts.end_time)
            if key not in seen_ranges:
                seen_ranges.add(key)
                time_ranges.append(key)
    time_ranges.sort()

    # Build a lookup: (day_of_week, start_time, end_time) -> time_slot_id
    slot_lookup: dict[tuple, UUID] = {}
    for ts in time_slots:
        if not ts.is_break:
            slot_lookup[(ts.day_of_week, ts.start_time, ts.end_time)] = ts.id

    lines: list[str] = []

    # Sort sections by grade then code
    sorted_sections = sorted(sections, key=lambda s: (s.grade, s.code))

    for section in sorted_sections:
        sec_entries = entries_by_section.get(section.id, [])
        if not sec_entries:
            continue

        shift_label = "Manana" if section.shift.value == "morning" else "Tarde"
        lines.append(
            f"\nSECCION {section.name} ({section.grade}o grado, {shift_label}):"
        )

        # Build entry lookup: (time_slot_id) -> entry
        entry_by_slot: dict[UUID, ScheduleEntry] = {}
        for e in sec_entries:
            entry_by_slot[e.time_slot_id] = e

        # Header
        header = "| Franja |"
        for day in range(5):
            header += f" {_DAY_NAMES[day]} |"
        lines.append(header)

        sep = "|--------|"
        for _ in range(5):
            sep += "----------|"
        lines.append(sep)

        # Rows
        for start_t, end_t in time_ranges:
            row = f"| {_format_time(start_t)}-{_format_time(end_t)} |"
            for day in range(5):
                slot_id = slot_lookup.get((day, start_t, end_t))
                if slot_id and slot_id in entry_by_slot:
                    e = entry_by_slot[slot_id]
                    subj = subject_map.get(e.subject_id)
                    tchr = teacher_map.get(e.teacher_id)
                    subj_code = subj.code if subj else "?"
                    # Short teacher name: first initial + last name
                    tchr_name = tchr.full_name if tchr else "?"
                    lock_mark = " [L]" if e.is_locked else ""
                    cell = f" {subj_code} ({tchr_name}){lock_mark} |"
                else:
                    cell = " - |"
                row += cell
            lines.append(row)

    # Teacher summary
    lines.append("\nRESUMEN DE DOCENTES:")
    teacher_hours: dict[UUID, int] = defaultdict(int)
    for entry in entries:
        teacher_hours[entry.teacher_id] += 1
    for teacher in sorted(teachers, key=lambda t: t.full_name):
        hours = teacher_hours.get(teacher.id, 0)
        max_h = teacher.max_hours_per_week or "-"
        lines.append(f"  - {teacher.full_name}: {hours}h asignadas (max: {max_h})")

    return "\n".join(lines)


def _build_entry_index(entries: list[ScheduleEntry]) -> str:
    """Build a compact index of entry IDs for the LLM to reference."""
    lines = ["INDICE DE ENTRADAS (entry_id -> detalle):"]
    for e in entries:
        lines.append(f"  {e.id}")
    return "\n".join(lines)


def _build_teacher_subject_info(
    teachers: list[Teacher],
    teacher_subjects: list[TeacherSubject],
    subjects: list[Subject],
) -> str:
    """Build info about which teachers can teach which subjects."""
    subject_map = {s.id: s for s in subjects}
    teacher_map = {t.id: t for t in teachers}

    # Group by teacher
    ts_by_teacher: dict[UUID, list[TeacherSubject]] = defaultdict(list)
    for ts in teacher_subjects:
        ts_by_teacher[ts.teacher_id].append(ts)

    lines = ["MATERIAS POR DOCENTE:"]
    for teacher in sorted(teachers, key=lambda t: t.full_name):
        subj_list = ts_by_teacher.get(teacher.id, [])
        if subj_list:
            subj_names = []
            for ts in subj_list:
                subj = subject_map.get(ts.subject_id)
                if subj:
                    scope = ""
                    if ts.grade is not None:
                        scope = f" (grado {ts.grade})"
                    subj_names.append(f"{subj.code}{scope}")
            lines.append(f"  - {teacher.full_name} (id: {teacher.id}): {', '.join(subj_names)}")

    return "\n".join(lines)


def _build_entry_detail_index(
    entries: list[ScheduleEntry],
    sections: list[Section],
    subjects: list[Subject],
    teachers: list[Teacher],
    time_slots: list[TimeSlot],
) -> str:
    """Build a detailed entry index so the LLM can reference entries by UUID."""
    section_map = {s.id: s for s in sections}
    subject_map = {s.id: s for s in subjects}
    teacher_map = {t.id: t for t in teachers}
    slot_map = {ts.id: ts for ts in time_slots}

    lines = ["INDICE DE ENTRADAS (para usar en actions):"]
    for e in entries:
        sec = section_map.get(e.section_id)
        subj = subject_map.get(e.subject_id)
        tchr = teacher_map.get(e.teacher_id)
        slot = slot_map.get(e.time_slot_id)
        sec_name = sec.name if sec else "?"
        subj_code = subj.code if subj else "?"
        tchr_name = tchr.full_name if tchr else "?"
        day = _DAY_NAMES[slot.day_of_week] if slot and 0 <= slot.day_of_week <= 4 else "?"
        time_str = f"{_format_time(slot.start_time)}-{_format_time(slot.end_time)}" if slot else "?"
        lock = " [LOCKED]" if e.is_locked else ""
        lines.append(
            f"  {e.id} -> {sec_name} | {day} {time_str} | {subj_code} | {tchr_name}{lock}"
        )

    return "\n".join(lines)


def _build_system_prompt(
    schedule_text: str,
    entry_index: str,
    teacher_info: str,
    business_rules: list[BusinessRule],
) -> str:
    """Build the system prompt for the LLM."""

    rules_text = ""
    if business_rules:
        rules_lines = ["REGLAS DE NEGOCIO ACTIVAS:"]
        for rule in business_rules:
            hard = "OBLIGATORIA" if rule.is_hard else "PREFERENCIA"
            rules_lines.append(f"  - [{hard}] {rule.description}")
        rules_text = "\n".join(rules_lines) + "\n\n"

    return f"""Eres un asistente de planificacion de horarios escolares. Tu trabajo es interpretar las instrucciones del director y proponer cambios estructurados al horario.

REGLAS:
- SIEMPRE responde con JSON valido con la estructura exacta especificada
- Si la instruccion es una consulta sin cambios, actions debe ser []
- Solo propon acciones sobre entradas que existen en el horario
- Si hay ambiguedad, pregunta para clarificar en response_to_user
- Valida que el docente pueda dar la materia antes de proponer reasignacion
- Cuando references un entry_id, usa EXACTAMENTE el UUID del indice de entradas
- Si la instruccion menciona una seccion, dia, franja o docente, busca la entrada correspondiente en el indice

TIPOS DE ACCION VALIDOS:
- REASSIGN_TEACHER: cambiar el docente de una entrada. changes debe tener "teacher_id" con el UUID del nuevo docente.
- SWAP_ENTRIES: intercambiar dos entradas (misma seccion, diferentes slots). changes debe tener "other_entry_id" con el UUID de la otra entrada.
- REMOVE: quitar una asignacion (dejar el slot vacio).
- LOCK: proteger una entrada contra cambios automaticos.
- UNLOCK: desproteger una entrada.

FORMATO DE RESPUESTA (JSON estricto, sin texto antes ni despues):
{{
  "reasoning": "explicacion de tu razonamiento",
  "actions": [
    {{
      "type": "REASSIGN_TEACHER",
      "entry_id": "uuid-de-la-entrada",
      "changes": {{"teacher_id": "uuid-nuevo-docente"}},
      "description": "Reasignar Matematicas 2A Lunes 07:00 de X a Y"
    }}
  ],
  "warnings": ["advertencia si aplica"],
  "response_to_user": "Mensaje legible para el director"
}}

{rules_text}HORARIO ACTUAL:
{schedule_text}

{entry_index}

{teacher_info}"""


def _parse_llm_json(raw: str) -> dict:
    """Extract and parse JSON from the LLM response.

    Handles cases where the LLM wraps JSON in markdown code fences or
    adds text before/after.
    """
    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding the first { ... } block
    brace_start = raw.find("{")
    if brace_start != -1:
        # Find matching closing brace
        depth = 0
        for i in range(brace_start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[brace_start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not parse JSON from LLM response: {raw[:500]}")


def _call_llm(messages: list[dict]) -> str:
    """Call the xAI LLM. Returns the raw response text.

    If XAI_API_KEY is not set, returns a mock response.
    """
    # Add project root to sys.path so we can import from src/
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Check if API key is available
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        logger.warning("XAI_API_KEY not set - returning mock response")
        return json.dumps(
            {
                "reasoning": "Assistant not configured - XAI_API_KEY not set.",
                "actions": [],
                "warnings": [
                    "El asistente no esta configurado. Configure XAI_API_KEY para habilitar la IA."
                ],
                "response_to_user": (
                    "El asistente de IA no esta configurado. "
                    "Por favor, configure la variable de entorno XAI_API_KEY "
                    "para habilitar las sugerencias inteligentes."
                ),
            }
        )

    from src.clients.xai_client import chat_completion_with_retry

    return chat_completion_with_retry(
        messages,
        temperature=0.2,
        timeout=180,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def process_assistant_message(
    project_id: UUID,
    schedule_version_id: UUID,
    user_message: str,
    db: Session,
    user_id: UUID,
) -> AssistantResponse:
    """Process a user message and return the assistant response with proposed actions.

    1. Loads schedule context (version, entries, teachers, subjects, etc.)
    2. Builds a compact schedule representation for the LLM
    3. Calls the LLM with conversation history
    4. Parses the structured JSON response
    5. Saves messages to the database
    6. Returns AssistantResponse
    """

    # --- 1. Load context ---
    version = (
        db.query(ScheduleVersion)
        .filter(
            ScheduleVersion.id == schedule_version_id,
            ScheduleVersion.project_id == project_id,
        )
        .first()
    )
    if not version:
        from fastapi import HTTPException, status as http_status

        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Schedule version not found",
        )

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        from fastapi import HTTPException, status as http_status

        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Load all entries with their relationships
    entries = (
        db.query(ScheduleEntry)
        .filter(ScheduleEntry.schedule_version_id == schedule_version_id)
        .all()
    )

    # Eagerly load related objects
    section_ids = {e.section_id for e in entries}
    subject_ids = {e.subject_id for e in entries}
    teacher_ids = {e.teacher_id for e in entries}
    slot_ids = {e.time_slot_id for e in entries}

    sections = (
        db.query(Section)
        .filter(Section.project_id == project_id)
        .all()
    )
    subjects = (
        db.query(Subject)
        .filter(Subject.project_id == project_id)
        .all()
    )
    teachers = (
        db.query(Teacher)
        .filter(Teacher.project_id == project_id)
        .all()
    )
    time_slots = (
        db.query(TimeSlot)
        .filter(
            TimeSlot.project_id == project_id,
            TimeSlot.is_break == False,  # noqa: E712
        )
        .order_by(TimeSlot.day_of_week, TimeSlot.slot_order)
        .all()
    )
    teacher_subjects = (
        db.query(TeacherSubject)
        .filter(TeacherSubject.project_id == project_id)
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

    # --- 2. Build schedule representation ---
    schedule_text = _build_schedule_text(entries, sections, teachers, subjects, time_slots)
    entry_index = _build_entry_detail_index(entries, sections, subjects, teachers, time_slots)
    teacher_info = _build_teacher_subject_info(teachers, teacher_subjects, subjects)

    # --- 3. Build messages for LLM ---
    system_prompt = _build_system_prompt(schedule_text, entry_index, teacher_info, business_rules)

    # Get or create conversation
    conversation = (
        db.query(AssistantConversation)
        .filter(
            AssistantConversation.project_id == project_id,
            AssistantConversation.schedule_version_id == schedule_version_id,
        )
        .first()
    )
    if not conversation:
        conversation = AssistantConversation(
            project_id=project_id,
            schedule_version_id=schedule_version_id,
        )
        db.add(conversation)
        db.flush()

    # Load conversation history (last 10 messages)
    history_messages = (
        db.query(AssistantMessage)
        .filter(AssistantMessage.conversation_id == conversation.id)
        .order_by(AssistantMessage.created_at.desc())
        .limit(10)
        .all()
    )
    history_messages.reverse()  # chronological order

    # Build LLM messages
    llm_messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for msg in history_messages:
        llm_messages.append({"role": msg.role, "content": msg.content})
    llm_messages.append({"role": "user", "content": user_message})

    # --- 4. Call LLM ---
    try:
        raw_response = _call_llm(llm_messages)
        parsed = _parse_llm_json(raw_response)
    except ValueError as e:
        # JSON parse failed - try once more with a clarification
        logger.warning("First LLM response was not valid JSON, retrying: %s", e)
        retry_messages = llm_messages + [
            {"role": "assistant", "content": raw_response},
            {
                "role": "user",
                "content": (
                    "Tu respuesta anterior no fue JSON valido. "
                    "Por favor responde SOLO con el JSON en el formato especificado, "
                    "sin texto adicional."
                ),
            },
        ]
        try:
            raw_response = _call_llm(retry_messages)
            parsed = _parse_llm_json(raw_response)
        except (ValueError, Exception) as retry_err:
            logger.error("LLM retry also failed: %s", retry_err)
            parsed = {
                "reasoning": "Error al procesar la respuesta del asistente.",
                "actions": [],
                "warnings": ["El asistente no pudo generar una respuesta valida."],
                "response_to_user": (
                    "Lo siento, no pude procesar tu solicitud correctamente. "
                    "Por favor, intenta reformular tu instruccion."
                ),
            }
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        parsed = {
            "reasoning": f"Error calling LLM: {e}",
            "actions": [],
            "warnings": [str(e)],
            "response_to_user": (
                "Hubo un error al comunicarse con el asistente de IA. "
                "Por favor, intenta de nuevo mas tarde."
            ),
        }

    # --- 5. Parse actions ---
    actions: list[AssistantAction] = []
    for action_data in parsed.get("actions", []):
        try:
            actions.append(
                AssistantAction(
                    type=action_data.get("type", ""),
                    entry_id=action_data.get("entry_id"),
                    changes=action_data.get("changes", {}),
                    description=action_data.get("description", ""),
                )
            )
        except Exception as e:
            logger.warning("Failed to parse action: %s - %s", action_data, e)

    # --- 6. Save messages ---
    # Save user message
    user_msg = AssistantMessage(
        conversation_id=conversation.id,
        role="user",
        content=user_message,
    )
    db.add(user_msg)
    db.flush()

    # Save assistant message
    response_content = parsed.get("response_to_user", "")
    assistant_msg = AssistantMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=response_content,
        proposed_actions=[a.model_dump(mode="json") for a in actions] if actions else None,
        reasoning=parsed.get("reasoning"),
    )
    db.add(assistant_msg)
    db.flush()

    db.commit()
    db.refresh(assistant_msg)

    # --- 7. Return response ---
    return AssistantResponse(
        message_id=assistant_msg.id,
        content=response_content,
        reasoning=parsed.get("reasoning"),
        proposed_actions=actions,
        warnings=parsed.get("warnings", []),
    )
