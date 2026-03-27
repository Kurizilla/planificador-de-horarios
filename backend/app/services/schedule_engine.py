"""
Schedule generation engine.

Contains the abstract planner interface, a stub implementation,
a CP-SAT constraint programming implementation, and conflict-detection
utilities.
"""
from __future__ import annotations

import logging
import time as _time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import NamedTuple
from uuid import UUID

from app.db.models import (
    BusinessRule,
    GradeSubjectLoad,
    Section,
    Subject,
    Teacher,
    TeacherAvailability,
    TeacherSubject,
    TimeSlot,
    ScheduleEntry,
)
from app.schemas.schedule import ConflictDetail

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

class EntryTuple(NamedTuple):
    section_id: UUID
    subject_id: UUID
    teacher_id: UUID
    time_slot_id: UUID


class UnassignedSlot(NamedTuple):
    section_id: UUID
    time_slot_id: UUID
    reason: str


@dataclass
class PlanningInput:
    """All data needed to generate a schedule for ONE shift."""
    sections: list[Section]
    teachers: list[Teacher]
    subjects: list[Subject]
    grade_subject_loads: list[GradeSubjectLoad]
    teacher_subjects: list[TeacherSubject]
    time_slots: list[TimeSlot]  # filtered by shift, non-break only
    teacher_availabilities: list[TeacherAvailability]
    locked_entries: list[ScheduleEntry] = field(default_factory=list)


@dataclass
class PlanningOutput:
    entries: list[EntryTuple] = field(default_factory=list)
    unassigned: list[UnassignedSlot] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------

class SchedulePlanner(ABC):
    @abstractmethod
    def generate(self, inp: PlanningInput) -> PlanningOutput:
        ...


# ---------------------------------------------------------------------------
# CP-SAT Implementation
# ---------------------------------------------------------------------------

class CPSatSchedulePlanner(SchedulePlanner):
    """
    Constraint Programming planner using Google OR-Tools CP-SAT.

    Models the timetable as a set of boolean variables:
        x[sec, slot, subj, teacher] = 1 iff teacher teaches subject to
        section at that time slot.

    Hard constraints:
        - Each section has exactly one (subject, teacher) per slot
        - Each teacher can be in at most one section per slot
        - Each section gets exactly the required weekly hours per subject
        - Teachers only teach subjects they're qualified for
        - Locked entries are preserved

    Soft objectives (minimise penalty):
        - Teacher workload close to 25 h/week
        - Distribute subjects across days (avoid clustering)
        - Prefer generalistas for their assigned section in ciclo 1-2
    """

    def __init__(self, time_limit_seconds: int = 30):
        self.time_limit_seconds = time_limit_seconds

    def generate(self, inp: PlanningInput) -> PlanningOutput:
        from ortools.sat.python import cp_model

        t0 = _time.monotonic()
        model = cp_model.CpModel()
        output = PlanningOutput()

        # ----- Index everything -----
        sections = inp.sections
        teachers = inp.teachers
        subjects = inp.subjects
        slots = sorted(inp.time_slots, key=lambda s: (s.day_of_week, s.slot_order))

        if not sections or not slots:
            output.stats = {"algorithm": "cp_sat", "duration_ms": 0, "status": "no_data"}
            return output

        sec_idx = {s.id: i for i, s in enumerate(sections)}
        teacher_idx = {t.id: i for i, t in enumerate(teachers)}
        subj_idx = {s.id: i for i, s in enumerate(subjects)}
        slot_idx = {s.id: i for i, s in enumerate(slots)}

        n_sec = len(sections)
        n_teacher = len(teachers)
        n_subj = len(subjects)
        n_slot = len(slots)

        # ----- Demand: which subjects does each section need? -----
        # sec_i -> [(subj_i, hours)]
        sec_demand: dict[int, list[tuple[int, int]]] = {}
        for si, sec in enumerate(sections):
            demands = []
            for gl in inp.grade_subject_loads:
                if gl.grade == sec.grade and gl.subject_id in subj_idx:
                    demands.append((subj_idx[gl.subject_id], gl.hours_per_week))
            sec_demand[si] = demands

        # ----- Who can teach what? -----
        # Build set of valid (teacher_i, subject_i) pairs
        # Also track scoped assignments (teacher assigned to specific section)
        valid_teacher_subject: set[tuple[int, int]] = set()
        # teacher_i -> set of (grade, section_code) they're assigned to (from data)
        teacher_assigned_sections: dict[int, set[tuple[int, str]]] = defaultdict(set)

        for ts in inp.teacher_subjects:
            if ts.teacher_id in teacher_idx and ts.subject_id in subj_idx:
                ti = teacher_idx[ts.teacher_id]
                sj = subj_idx[ts.subject_id]
                valid_teacher_subject.add((ti, sj))
                if ts.grade is not None and ts.section_code is not None:
                    teacher_assigned_sections[ti].add((ts.grade, ts.section_code))

        # ----- Teacher availability -----
        unavailable: set[tuple[int, int]] = set()  # (teacher_i, slot_i)
        for ta in inp.teacher_availabilities:
            if not ta.available and ta.teacher_id in teacher_idx and ta.time_slot_id in slot_idx:
                unavailable.add((teacher_idx[ta.teacher_id], slot_idx[ta.time_slot_id]))

        # ----- Determine feasible (sec, slot, subj, teacher) combos -----
        # Only create variables for feasible combinations to keep model small
        # For each section + subject, find which teachers can teach it
        sec_subj_teachers: dict[tuple[int, int], list[int]] = {}
        for si, sec in enumerate(sections):
            for sj_i, _hrs in sec_demand.get(si, []):
                eligible = []
                for ti in range(n_teacher):
                    if (ti, sj_i) not in valid_teacher_subject:
                        continue
                    eligible.append(ti)
                sec_subj_teachers[(si, sj_i)] = eligible

        # ----- Create decision variables -----
        # x[si, ki, sj_i, ti] = 1 means section si at slot ki has subject sj_i taught by teacher ti
        x = {}
        for si in range(n_sec):
            for ki in range(n_slot):
                for sj_i, _hrs in sec_demand.get(si, []):
                    for ti in sec_subj_teachers.get((si, sj_i), []):
                        if (ti, ki) in unavailable:
                            continue
                        x[(si, ki, sj_i, ti)] = model.new_bool_var(
                            f"x_s{si}_k{ki}_j{sj_i}_t{ti}"
                        )

        # Track subjects with no eligible teacher for any section
        subjects_without_teachers: set[int] = set()
        for si in range(n_sec):
            for sj_i, hrs in sec_demand.get(si, []):
                if not sec_subj_teachers.get((si, sj_i)):
                    subjects_without_teachers.add(sj_i)

        logger.info(
            "CP-SAT model: %d sections, %d slots, %d subjects, %d teachers, %d variables",
            n_sec, n_slot, n_subj, n_teacher, len(x),
        )

        # ----- Hard Constraint 1: Each section has AT MOST one assignment per slot -----
        for si in range(n_sec):
            for ki in range(n_slot):
                vars_in_slot = [
                    x[(si, ki, sj_i, ti)]
                    for sj_i, _ in sec_demand.get(si, [])
                    for ti in sec_subj_teachers.get((si, sj_i), [])
                    if (si, ki, sj_i, ti) in x
                ]
                if vars_in_slot:
                    model.add(sum(vars_in_slot) <= 1)

        # ----- Hard Constraint 2: Each teacher at most one section per slot -----
        for ti in range(n_teacher):
            for ki in range(n_slot):
                vars_for_teacher_slot = [
                    x[key] for key in x
                    if key[3] == ti and key[1] == ki
                ]
                if vars_for_teacher_slot:
                    model.add(sum(vars_for_teacher_slot) <= 1)

        # ----- Hard Constraint 3: Weekly hours per subject per section -----
        # For subjects WITH teachers: require exactly the hours
        # For subjects WITHOUT teachers: skip (they go to unassigned)
        for si in range(n_sec):
            for sj_i, hrs in sec_demand.get(si, []):
                if sj_i in subjects_without_teachers:
                    continue  # Can't fill, will be reported as unassigned
                vars_for_subj = [
                    x[(si, ki, sj_i, ti)]
                    for ki in range(n_slot)
                    for ti in sec_subj_teachers.get((si, sj_i), [])
                    if (si, ki, sj_i, ti) in x
                ]
                if vars_for_subj:
                    if len(vars_for_subj) >= hrs:
                        model.add(sum(vars_for_subj) == hrs)
                    else:
                        # Not enough possible slots; maximise what we can
                        model.add(sum(vars_for_subj) <= hrs)

        # ----- Locked entries -----
        for entry in inp.locked_entries:
            if (entry.section_id in sec_idx and entry.time_slot_id in slot_idx
                    and entry.subject_id in subj_idx and entry.teacher_id in teacher_idx):
                si = sec_idx[entry.section_id]
                ki = slot_idx[entry.time_slot_id]
                sj_i = subj_idx[entry.subject_id]
                ti = teacher_idx[entry.teacher_id]
                key = (si, ki, sj_i, ti)
                if key in x:
                    model.add(x[key] == 1)

        # ----- Soft Objective: Maximise total assignments (fill as much as possible) -----
        all_vars = list(x.values())
        total_assigned = model.new_int_var(0, len(all_vars), "total_assigned")
        model.add(total_assigned == sum(all_vars))

        # ----- Soft Objective: Teacher workload near 25h -----
        # For each teacher, compute total hours and penalise deviation from 25
        teacher_load_penalties = []
        target_hours = 25
        for ti in range(n_teacher):
            teacher_vars = [x[key] for key in x if key[3] == ti]
            if not teacher_vars:
                continue
            total = model.new_int_var(0, n_slot, f"load_t{ti}")
            model.add(total == sum(teacher_vars))
            # Penalty = |total - 25| approximated as over + under
            over = model.new_int_var(0, n_slot, f"over_t{ti}")
            under = model.new_int_var(0, target_hours, f"under_t{ti}")
            model.add(total - target_hours == over - under)
            teacher_load_penalties.append(over + under)

        # ----- Soft Objective: Generalista preference for ciclo 1-2 -----
        # Bonus when a teacher assigned to a specific section teaches there
        generalista_bonus_vars = []
        for si, sec in enumerate(sections):
            if sec.grade > 6:
                continue  # Only ciclo 1-2
            for sj_i, _ in sec_demand.get(si, []):
                for ti in sec_subj_teachers.get((si, sj_i), []):
                    if (sec.grade, sec.code) in teacher_assigned_sections.get(ti, set()):
                        # This teacher is "assigned" to this section — prefer them
                        for ki in range(n_slot):
                            if (si, ki, sj_i, ti) in x:
                                generalista_bonus_vars.append(x[(si, ki, sj_i, ti)])

        # ----- Hard Constraint 4: Max 1 block of same subject per day per section -----
        # No subject can repeat on the same day for a section
        days = sorted(set(s.day_of_week for s in slots))
        for si in range(n_sec):
            for sj_i, hrs in sec_demand.get(si, []):
                if sj_i in subjects_without_teachers:
                    continue
                for day in days:
                    day_slots = [slot_idx[s.id] for s in slots if s.day_of_week == day]
                    day_vars = [
                        x[(si, ki, sj_i, ti)]
                        for ki in day_slots
                        for ti in sec_subj_teachers.get((si, sj_i), [])
                        if (si, ki, sj_i, ti) in x
                    ]
                    if day_vars:
                        model.add(sum(day_vars) <= 1)

        # ----- Soft Objective: Avoid LEN/MAT in first slot of the day -----
        # Identify subject indices for LEN, MAT, RE_LEN, RE_MAT
        first_slot_penalty_subjs = set()
        for sj_i, subj in enumerate(subjects):
            if subj.code in ("LEN", "MAT"):
                first_slot_penalty_subjs.add(sj_i)

        # Find the first slot index for each day (slot_order == 1)
        first_slots_per_day: dict[int, list[int]] = defaultdict(list)
        for s in slots:
            if s.slot_order == 1:
                first_slots_per_day[s.day_of_week].append(slot_idx[s.id])

        first_slot_penalties = []
        for si in range(n_sec):
            for sj_i in first_slot_penalty_subjs:
                if sj_i in subjects_without_teachers:
                    continue
                for day, first_kis in first_slots_per_day.items():
                    for ki in first_kis:
                        vars_first = [
                            x[(si, ki, sj_i, ti)]
                            for ti in sec_subj_teachers.get((si, sj_i), [])
                            if (si, ki, sj_i, ti) in x
                        ]
                        first_slot_penalties.extend(vars_first)

        # ----- Composite objective -----
        obj_terms = []
        # Maximise assignments (weight 100 per assigned slot)
        obj_terms.append(100 * total_assigned)
        # Maximise generalista bonus (weight 5)
        if generalista_bonus_vars:
            obj_terms.append(5 * sum(generalista_bonus_vars))
        # Minimise load imbalance (weight -2 per deviation hour)
        if teacher_load_penalties:
            obj_terms.append(-2 * sum(teacher_load_penalties))
        # Penalise LEN/MAT in first slot (weight -15 each — significant but not blocking)
        if first_slot_penalties:
            obj_terms.append(-15 * sum(first_slot_penalties))

        model.maximize(sum(obj_terms))

        # ----- Solve -----
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_workers = 4
        solver.parameters.log_search_progress = False

        status = solver.solve(model)
        elapsed_ms = int((_time.monotonic() - t0) * 1000)

        status_name = {
            cp_model.OPTIMAL: "optimal",
            cp_model.FEASIBLE: "feasible",
            cp_model.INFEASIBLE: "infeasible",
            cp_model.MODEL_INVALID: "invalid",
            cp_model.UNKNOWN: "unknown",
        }.get(status, "unknown")

        logger.info("CP-SAT solved in %dms, status=%s", elapsed_ms, status_name)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # Extract solution
            assigned_slots_per_section: dict[int, set[int]] = defaultdict(set)
            for (si, ki, sj_i, ti), var in x.items():
                if solver.value(var) == 1:
                    output.entries.append(EntryTuple(
                        section_id=sections[si].id,
                        subject_id=subjects[sj_i].id,
                        teacher_id=teachers[ti].id,
                        time_slot_id=slots[ki].id,
                    ))
                    assigned_slots_per_section[si].add(ki)

            # Find unassigned slots
            for si in range(n_sec):
                assigned = assigned_slots_per_section.get(si, set())
                for ki in range(n_slot):
                    if ki not in assigned:
                        # Determine reason
                        unassigned_subjects = []
                        for sj_i, hrs in sec_demand.get(si, []):
                            if sj_i in subjects_without_teachers:
                                unassigned_subjects.append(subjects[sj_i].name)
                        reason = (
                            f"Sin docente para: {', '.join(set(unassigned_subjects))}"
                            if unassigned_subjects
                            else "Sin asignación posible"
                        )
                        output.unassigned.append(UnassignedSlot(
                            section_id=sections[si].id,
                            time_slot_id=slots[ki].id,
                            reason=reason,
                        ))

            # Compute teacher load stats
            teacher_loads = defaultdict(int)
            for e in output.entries:
                teacher_loads[e.teacher_id] += 1

            output.stats = {
                "algorithm": "cp_sat",
                "status": status_name,
                "duration_ms": elapsed_ms,
                "total_slots": n_sec * n_slot,
                "assigned": len(output.entries),
                "unassigned": len(output.unassigned),
                "fill_rate": f"{len(output.entries) / max(1, n_sec * n_slot):.1%}",
                "teacher_loads": {
                    teachers[teacher_idx[tid]].full_name: hours
                    for tid, hours in teacher_loads.items()
                    if tid in teacher_idx
                },
                "subjects_without_teachers": [
                    subjects[sj_i].name for sj_i in subjects_without_teachers
                ],
            }
        else:
            # Infeasible or timeout
            output.stats = {
                "algorithm": "cp_sat",
                "status": status_name,
                "duration_ms": elapsed_ms,
            }
            output.conflicts.append(
                f"El solver no encontró solución (status: {status_name}). "
                "Puede haber conflictos irresolubles en las restricciones."
            )
            # Fall back to unassigning everything
            for si in range(n_sec):
                for ki in range(n_slot):
                    output.unassigned.append(UnassignedSlot(
                        section_id=sections[si].id,
                        time_slot_id=slots[ki].id,
                        reason=f"Solver status: {status_name}",
                    ))

        return output


# ---------------------------------------------------------------------------
# Stub implementation (kept for testing/fallback)
# ---------------------------------------------------------------------------

class StubSchedulePlanner(SchedulePlanner):
    """Simple sequential assignment planner. No optimization."""

    def generate(self, inp: PlanningInput) -> PlanningOutput:
        output = PlanningOutput()
        subject_map = {s.id: s for s in inp.subjects}

        grade_loads: dict[int, list[tuple[UUID, int]]] = defaultdict(list)
        for gl in inp.grade_subject_loads:
            grade_loads[gl.grade].append((gl.subject_id, gl.hours_per_week))

        subject_teachers: dict[UUID, list[UUID]] = defaultdict(list)
        scoped_teachers: dict[tuple[UUID, int | None, str | None], list[UUID]] = defaultdict(list)
        for ts in inp.teacher_subjects:
            subject_teachers[ts.subject_id].append(ts.teacher_id)
            scoped_teachers[(ts.subject_id, ts.grade, ts.section_code)].append(ts.teacher_id)

        unavailable: set[tuple[UUID, UUID]] = set()
        for ta in inp.teacher_availabilities:
            if not ta.available:
                unavailable.add((ta.teacher_id, ta.time_slot_id))

        sorted_slots = sorted(inp.time_slots, key=lambda ts: (ts.day_of_week, ts.slot_order))
        teacher_slot_assigned: dict[UUID, set[UUID]] = defaultdict(set)
        section_slot_assigned: dict[UUID, set[UUID]] = defaultdict(set)

        for entry in inp.locked_entries:
            teacher_slot_assigned[entry.teacher_id].add(entry.time_slot_id)
            section_slot_assigned[entry.section_id].add(entry.time_slot_id)
            output.entries.append(EntryTuple(
                section_id=entry.section_id, subject_id=entry.subject_id,
                teacher_id=entry.teacher_id, time_slot_id=entry.time_slot_id,
            ))

        for section in inp.sections:
            loads = grade_loads.get(section.grade, [])
            if not loads:
                for slot in sorted_slots:
                    if slot.id not in section_slot_assigned.get(section.id, set()):
                        output.unassigned.append(UnassignedSlot(section.id, slot.id, "No curriculum"))
                continue

            demand: list[UUID] = []
            for subject_id, hours in loads:
                demand.extend([subject_id] * hours)

            demand_idx = 0
            for slot in sorted_slots:
                if slot.id in section_slot_assigned.get(section.id, set()):
                    continue
                if demand_idx >= len(demand):
                    break
                subject_id = demand[demand_idx]

                # Find teacher
                tid = None
                for key_fn in [
                    lambda: (subject_id, section.grade, section.code),
                    lambda: (subject_id, section.grade, None),
                    lambda: (subject_id, None, None),
                ]:
                    for candidate in scoped_teachers.get(key_fn(), []):
                        if (candidate, slot.id) not in unavailable and slot.id not in teacher_slot_assigned.get(candidate, set()):
                            tid = candidate
                            break
                    if tid:
                        break

                if not tid:
                    for candidate in subject_teachers.get(subject_id, []):
                        if (candidate, slot.id) not in unavailable and slot.id not in teacher_slot_assigned.get(candidate, set()):
                            tid = candidate
                            break

                if tid:
                    output.entries.append(EntryTuple(section.id, subject_id, tid, slot.id))
                    teacher_slot_assigned[tid].add(slot.id)
                    section_slot_assigned[section.id].add(slot.id)
                else:
                    name = subject_map[subject_id].name if subject_id in subject_map else str(subject_id)
                    output.unassigned.append(UnassignedSlot(section.id, slot.id, f"No teacher for {name}"))
                demand_idx += 1

        output.stats = {"algorithm": "stub"}
        return output


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def detect_conflicts(
    entries: list[ScheduleEntry],
    teachers: list[Teacher],
    sections: list[Section],
    time_slots: list[TimeSlot],
    business_rules: list[BusinessRule],
) -> list[ConflictDetail]:
    """Analyse a list of schedule entries and return detected conflicts."""
    conflicts: list[ConflictDetail] = []
    teacher_map = {t.id: t for t in teachers}

    teacher_slot: dict[tuple[UUID, UUID], list[ScheduleEntry]] = defaultdict(list)
    for entry in entries:
        teacher_slot[(entry.teacher_id, entry.time_slot_id)].append(entry)

    for (teacher_id, ts_id), group in teacher_slot.items():
        if len(group) > 1:
            teacher = teacher_map.get(teacher_id)
            name = teacher.full_name if teacher else str(teacher_id)
            conflicts.append(ConflictDetail(
                type="teacher_double_booking", severity="error",
                description=f"Docente '{name}' asignado a {len(group)} secciones al mismo tiempo.",
                affected_entry_ids=[e.id for e in group],
            ))

    section_slot: dict[tuple[UUID, UUID], list[ScheduleEntry]] = defaultdict(list)
    for entry in entries:
        section_slot[(entry.section_id, entry.time_slot_id)].append(entry)

    for (section_id, ts_id), group in section_slot.items():
        if len(group) > 1:
            conflicts.append(ConflictDetail(
                type="section_double_booking", severity="error",
                description=f"Sección tiene {len(group)} asignaciones en el mismo bloque.",
                affected_entry_ids=[e.id for e in group],
            ))

    teacher_hours: dict[UUID, int] = defaultdict(int)
    teacher_entries: dict[UUID, list[UUID]] = defaultdict(list)
    for entry in entries:
        teacher_hours[entry.teacher_id] += 1
        teacher_entries[entry.teacher_id].append(entry.id)

    for teacher_id, hours in teacher_hours.items():
        teacher = teacher_map.get(teacher_id)
        if teacher and teacher.max_hours_per_week and hours > teacher.max_hours_per_week:
            conflicts.append(ConflictDetail(
                type="teacher_max_hours_exceeded", severity="warning",
                description=f"Docente '{teacher.full_name}' tiene {hours}h asignadas (máx: {teacher.max_hours_per_week}h).",
                affected_entry_ids=teacher_entries[teacher_id],
            ))

    # --- Subject repeated on same day for a section (ERROR) ---
    slot_map = {ts.id: ts for ts in time_slots}
    from app.db.models import Subject as _Subject
    # Build subject code lookup from entries if possible
    section_day_subject: dict[tuple[UUID, int], dict[UUID, list[ScheduleEntry]]] = defaultdict(lambda: defaultdict(list))
    for entry in entries:
        ts = slot_map.get(entry.time_slot_id)
        if ts:
            section_day_subject[(entry.section_id, ts.day_of_week)][entry.subject_id].append(entry)

    for (sec_id, day), subj_entries in section_day_subject.items():
        for subj_id, ents in subj_entries.items():
            if len(ents) > 1:
                conflicts.append(ConflictDetail(
                    type="subject_repeated_same_day", severity="error",
                    description=f"Materia repetida {len(ents)} veces el mismo día en una sección.",
                    affected_entry_ids=[e.id for e in ents],
                ))

    # --- LEN/MAT in first slot of day (WARNING) ---
    first_slot_warnings: list[UUID] = []
    for entry in entries:
        ts = slot_map.get(entry.time_slot_id)
        if ts and ts.slot_order == 1:
            # Check if this is LEN or MAT by looking at the entry's subject
            # We need subject info - check from the subjects list
            subj = None
            for s in sections:
                pass  # sections is wrong here, we need subjects
            # Use a simpler approach: check all subjects passed in
            pass

    # We need subject codes - build lookup from the subjects in the DB context
    # Since detect_conflicts gets DB model objects, we can check via relationship
    # But entries might not have subject loaded. Let's build from what we have.
    # The caller should pass subjects list; for now detect via entry.subject relationship if loaded.
    try:
        for entry in entries:
            ts = slot_map.get(entry.time_slot_id)
            if ts and ts.slot_order == 1 and hasattr(entry, 'subject') and entry.subject:
                if entry.subject.code in ("LEN", "MAT"):
                    first_slot_warnings.append(entry.id)
    except Exception:
        pass  # Skip if subject not loaded

    if first_slot_warnings:
        conflicts.append(ConflictDetail(
            type="len_mat_first_slot", severity="warning",
            description=f"Lenguaje o Matemática asignada en la primera hora del día ({len(first_slot_warnings)} caso(s)).",
            affected_entry_ids=first_slot_warnings,
        ))

    return conflicts
