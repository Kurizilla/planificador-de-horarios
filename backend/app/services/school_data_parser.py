"""
Parse school Excel file (Estudiantes + Docentes sheets) and persist entities.

The Excel comes from MINEDUCYT with two sheets:
- Estudiantes: student rows grouped by school, shift, grade, section
- Docentes: teacher-subject-section assignments (one row per assignment)

This module reads both sheets, filters by school_code, deduplicates teachers,
creates subjects (including placeholder subjects from the Carga Horaria),
builds section records, teacher-subject assignments, grade-subject loads,
and time slots.
"""
from __future__ import annotations

import logging
import uuid
from datetime import time as dt_time
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy.orm import Session

from app.db.enums import ImportStatus, ProjectStatus, Shift
from app.db.models import (
    DataImport,
    GradeSubjectLoad,
    Project,
    Section,
    Subject,
    Teacher,
    TeacherSubject,
    TimeSlot,
)
from app.schemas.school_data import ImportSummary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Subject catalogue
# ---------------------------------------------------------------------------

SUBJECT_CATALOG: dict[str, dict[str, Any]] = {
    "LEN": {"name": "Lenguaje", "is_remediation": False, "color": "#4A90D9"},
    "MAT": {"name": "Matematica", "is_remediation": False, "color": "#E07B39"},
    "CIE": {"name": "Ciencias", "is_remediation": False, "color": "#50B86C"},
    "SOC": {"name": "Sociales", "is_remediation": False, "color": "#9B59B6"},
    "ART": {"name": "Artes", "is_remediation": False, "color": "#E74C8B"},
    "EDF": {"name": "Ed. Fisica", "is_remediation": False, "color": "#F5A623"},
    "ING": {"name": "Ingles", "is_remediation": False, "color": "#1ABC9C"},
    "RE_LEN": {"name": "Remediacion Lenguaje", "is_remediation": True, "parent_code": "LEN", "color": "#7FB3E0"},
    "RE_MAT": {"name": "Remediacion Matematica", "is_remediation": True, "parent_code": "MAT", "color": "#F0B88A"},
}

# Map data "Asignatura" values to our subject codes
_ASIGNATURA_MAP: dict[str, str] = {
    "Lenguaje": "LEN",
    "Lenguaje y Literatura": "LEN",
    "Matematica": "MAT",
    "Matemática": "MAT",
    "Matematicas": "MAT",
    "Matemáticas": "MAT",
    "Ciencias": "CIE",
    "Ciencias Naturales": "CIE",
    "Sociales": "SOC",
    "Estudios Sociales": "SOC",
    "Artes": "ART",
    "Ed. Fisica": "EDF",
    "Ed. Física": "EDF",
    "Educacion Fisica": "EDF",
    "Educación Física": "EDF",
    "Fisica": "EDF",
    "Física": "EDF",
    "Ingles": "ING",
    "Inglés": "ING",
}

# ---------------------------------------------------------------------------
# Carga Horaria rules (hours per week per subject per grade)
# ---------------------------------------------------------------------------

CARGA_HORARIA: dict[int, dict[str, int]] = {
    2: {"LEN": 5, "RE_LEN": 4, "MAT": 5, "RE_MAT": 4, "SOC": 1, "CIE": 1, "ART": 2, "EDF": 3},
    3: {"LEN": 5, "RE_LEN": 4, "MAT": 5, "RE_MAT": 4, "CIE": 1, "SOC": 1, "ART": 2, "EDF": 3},
    4: {"LEN": 5, "RE_LEN": 3, "MAT": 5, "RE_MAT": 3, "CIE": 2, "SOC": 1, "ART": 3, "EDF": 3},
    5: {"LEN": 5, "RE_LEN": 3, "MAT": 5, "RE_MAT": 3, "CIE": 2, "SOC": 1, "ART": 3, "EDF": 3},
    6: {"LEN": 5, "RE_LEN": 3, "MAT": 5, "RE_MAT": 3, "CIE": 2, "SOC": 1, "ART": 3, "EDF": 3},
    7: {"LEN": 5, "RE_LEN": 3, "MAT": 5, "RE_MAT": 3, "CIE": 2, "SOC": 2, "ING": 3, "EDF": 3},
    8: {"LEN": 5, "RE_LEN": 3, "MAT": 5, "RE_MAT": 3, "CIE": 2, "SOC": 2, "ING": 3, "EDF": 3},
    9: {"LEN": 5, "RE_LEN": 3, "MAT": 5, "RE_MAT": 3, "CIE": 2, "SOC": 2, "ING": 3, "EDF": 3},
    10: {"LEN": 5, "RE_LEN": 1, "MAT": 5, "CIE": 6, "SOC": 5, "ING": 4, "EDF": 2},
    11: {"LEN": 5, "RE_LEN": 1, "MAT": 5, "CIE": 6, "SOC": 4, "ING": 3, "EDF": 3},  # total 27 + 1 flex = 28
}

# ---------------------------------------------------------------------------
# Turno mapping
# ---------------------------------------------------------------------------

_TURNO_MAP: dict[str, Shift] = {
    "Matutino": Shift.MORNING,
    "matutino": Shift.MORNING,
    "Vespertino": Shift.AFTERNOON,
    "vespertino": Shift.AFTERNOON,
}


def _parse_shift(turno_raw: str | None) -> tuple[Shift, bool]:
    """Return (shift, is_jornada_completa). Default to MORNING."""
    if not turno_raw or pd.isna(turno_raw):
        return Shift.MORNING, False
    turno = str(turno_raw).strip()
    if turno in _TURNO_MAP:
        return _TURNO_MAP[turno], False
    if "completa" in turno.lower() or "jornada" in turno.lower():
        return Shift.MORNING, True
    return Shift.MORNING, False


def _safe_str(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return str(val).strip() or None


def _safe_int(val: Any) -> int | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _normalize_asignatura(raw: str | None) -> str | None:
    """Map an Asignatura value from the Excel to a subject code."""
    if not raw or pd.isna(raw):
        return None
    key = str(raw).strip()
    return _ASIGNATURA_MAP.get(key)


# ---------------------------------------------------------------------------
# Time slot generation
# ---------------------------------------------------------------------------

def _generate_time_slots(
    project_id: UUID,
    shifts: set[Shift],
    grades: set[int],
) -> list[TimeSlot]:
    """Generate weekly time-slot grid.

    Basic education (grades 2-9): 5 periods x 55 min, with a break after period 3.
    Bachillerato (grades 10-11): 7 periods x 45 min, with a break after period 4.

    Morning starts at 7:00.  Afternoon starts at 12:30.
    """
    has_basic = bool(grades & set(range(2, 10)))
    has_bach = bool(grades & {10, 11})

    slots: list[TimeSlot] = []

    for shift in sorted(shifts, key=lambda s: s.value):
        if shift == Shift.MORNING:
            start_hour, start_min = 7, 0
        else:
            start_hour, start_min = 12, 30

        configs: list[tuple[int, int, int]] = []  # (period_count, duration_min, break_after)
        if has_basic:
            configs.append((5, 55, 3))
        if has_bach:
            configs.append((7, 45, 4))

        # Use the first matching config for this shift (simplification:
        # if school has both basic and bach in the same shift, we use the bach
        # grid because it has more periods and is a superset).
        if has_bach and has_basic:
            # Use bach grid (more periods); basic classes fit in first 5.
            configs = [(7, 45, 4)]
        elif has_basic:
            configs = [(5, 55, 3)]
        elif has_bach:
            configs = [(7, 45, 4)]

        for period_count, duration, break_after in configs:
            cur_hour, cur_min = start_hour, start_min
            order = 1
            for day in range(5):  # Mon-Fri
                cur_hour, cur_min = start_hour, start_min
                order_in_day = 1
                for period in range(1, period_count + 1):
                    s_time = dt_time(cur_hour, cur_min)
                    total_min = cur_hour * 60 + cur_min + duration
                    e_time = dt_time(total_min // 60, total_min % 60)

                    slots.append(TimeSlot(
                        id=uuid.uuid4(),
                        project_id=project_id,
                        day_of_week=day,
                        start_time=s_time,
                        end_time=e_time,
                        slot_order=order_in_day,
                        shift=shift,
                        is_break=False,
                        label=f"Periodo {period}",
                    ))
                    cur_hour, cur_min = total_min // 60, total_min % 60
                    order_in_day += 1

                    # Insert break after the designated period
                    if period == break_after:
                        break_duration = 20 if period_count <= 5 else 15
                        bs_time = dt_time(cur_hour, cur_min)
                        bt = cur_hour * 60 + cur_min + break_duration
                        be_time = dt_time(bt // 60, bt % 60)
                        slots.append(TimeSlot(
                            id=uuid.uuid4(),
                            project_id=project_id,
                            day_of_week=day,
                            start_time=bs_time,
                            end_time=be_time,
                            slot_order=order_in_day,
                            shift=shift,
                            is_break=True,
                            label="Recreo",
                        ))
                        cur_hour, cur_min = bt // 60, bt % 60
                        order_in_day += 1

    return slots


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_school_excel(
    file_path: str,
    school_code: str,
    project_id: UUID,
    db: Session,
    imported_by_id: UUID,
) -> ImportSummary:
    """Read the MINEDUCYT Excel, filter by school code, and persist all entities."""

    warnings: list[str] = []
    errors: list[str] = []

    # -- Create DataImport record -------------------------------------------
    data_import = DataImport(
        id=uuid.uuid4(),
        project_id=project_id,
        filename=file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path,
        file_type="xlsx",
        storage_path=file_path,
        status=ImportStatus.PENDING,
        imported_by_id=imported_by_id,
    )
    db.add(data_import)

    try:
        # -- Read Excel -----------------------------------------------------
        try:
            df_students = pd.read_excel(file_path, sheet_name="Estudiantes", dtype=str)
            df_teachers = pd.read_excel(file_path, sheet_name="Docentes", dtype=str)
        except Exception as exc:
            errors.append(f"Error reading Excel file: {exc}")
            data_import.status = ImportStatus.ERROR
            data_import.errors = errors
            db.commit()
            return ImportSummary(
                import_id=data_import.id,
                status=ImportStatus.ERROR.value,
                errors=errors,
                warnings=warnings,
            )

        # Normalize column names (strip whitespace)
        df_students.columns = [c.strip() for c in df_students.columns]
        df_teachers.columns = [c.strip() for c in df_teachers.columns]

        # -- Filter by school code ------------------------------------------
        code_col_students = "Código" if "Código" in df_students.columns else "Codigo"
        code_col_teachers = "Código" if "Código" in df_teachers.columns else "Codigo"

        df_students = df_students[df_students[code_col_students].astype(str).str.strip() == str(school_code).strip()]
        df_teachers = df_teachers[df_teachers[code_col_teachers].astype(str).str.strip() == str(school_code).strip()]

        if df_students.empty and df_teachers.empty:
            errors.append(f"No data found for school code '{school_code}'")
            data_import.status = ImportStatus.ERROR
            data_import.errors = errors
            db.commit()
            return ImportSummary(
                import_id=data_import.id,
                status=ImportStatus.ERROR.value,
                errors=errors,
                warnings=warnings,
            )

        # ===================================================================
        # 1. SUBJECTS - create standard subject catalogue
        # ===================================================================
        subject_map: dict[str, Subject] = {}  # code -> Subject

        for code, info in SUBJECT_CATALOG.items():
            subj = Subject(
                id=uuid.uuid4(),
                project_id=project_id,
                code=code,
                name=info["name"],
                is_remediation=info["is_remediation"],
                color=info.get("color"),
            )
            subject_map[code] = subj

        # Link remediation subjects to parents
        for code, info in SUBJECT_CATALOG.items():
            parent_code = info.get("parent_code")
            if parent_code and parent_code in subject_map:
                subject_map[code].parent_subject_id = subject_map[parent_code].id

        for subj in subject_map.values():
            db.add(subj)

        # ===================================================================
        # 2. SECTIONS - from students sheet
        # ===================================================================
        section_map: dict[tuple[Shift, int, str], Section] = {}  # (shift, grade, section_code) -> Section

        if not df_students.empty:
            for (turno_raw, grado_raw, seccion_raw), group in df_students.groupby(
                ["Turno", "Grado", "Sección"], dropna=False
            ):
                shift, is_jc = _parse_shift(turno_raw)
                if is_jc:
                    warnings.append(
                        f"'Jornada completa' found for G{grado_raw}{seccion_raw}; mapped to MORNING shift."
                    )
                grade = _safe_int(grado_raw)
                if grade is None:
                    warnings.append(f"Skipping students with invalid grade: {grado_raw}")
                    continue
                sec_code = _safe_str(seccion_raw) or "A"
                student_count = len(group)

                # Tipo and Opcion: take first non-null value from the group
                tipo = None
                opcion = None
                if "Tipo" in group.columns:
                    tipo_vals = group["Tipo"].dropna().unique()
                    tipo = str(tipo_vals[0]).strip() if len(tipo_vals) > 0 else None
                if "Opción" in group.columns:
                    opc_vals = group["Opción"].dropna().unique()
                    opcion = str(opc_vals[0]).strip() if len(opc_vals) > 0 else None
                elif "Opcion" in group.columns:
                    opc_vals = group["Opcion"].dropna().unique()
                    opcion = str(opc_vals[0]).strip() if len(opc_vals) > 0 else None

                sec = Section(
                    id=uuid.uuid4(),
                    project_id=project_id,
                    code=sec_code,
                    name=f"G{grade}{sec_code}",
                    grade=grade,
                    shift=shift,
                    student_count=student_count,
                    tipo=tipo,
                    opcion=opcion,
                )
                section_map[(shift, grade, sec_code)] = sec
                db.add(sec)

        # ===================================================================
        # 3. TEACHERS - deduplicate from docentes sheet
        # ===================================================================
        teacher_map: dict[str, Teacher] = {}  # dedup key -> Teacher
        teacher_subject_records: list[TeacherSubject] = []

        if not df_teachers.empty:
            for _, row in df_teachers.iterrows():
                nip = _safe_str(row.get("NIP"))
                id_persona = _safe_str(row.get("Id_persona"))
                dui = _safe_str(row.get("DUI"))

                # Dedup key: prefer NIP, fall back to Id_persona, then DUI
                dedup_key = nip or id_persona or dui
                if not dedup_key:
                    # Generate a key from name as last resort
                    nombre_completo = _safe_str(row.get("Nombre_completo")) or ""
                    if not nombre_completo:
                        nombres = _safe_str(row.get("Nombres")) or ""
                        apellidos = _safe_str(row.get("Apellidos")) or ""
                        nombre_completo = f"{nombres} {apellidos}".strip()
                    dedup_key = f"name:{nombre_completo}"
                    if not nombre_completo:
                        warnings.append("Skipping teacher row with no identifiers")
                        continue

                if dedup_key not in teacher_map:
                    nombre_completo = _safe_str(row.get("Nombre_completo")) or ""
                    if not nombre_completo:
                        nombres = _safe_str(row.get("Nombres")) or ""
                        apellidos = _safe_str(row.get("Apellidos")) or ""
                        nombre_completo = f"{nombres} {apellidos}".strip()

                    turno_raw = _safe_str(row.get("Turno"))
                    shift, is_jc = _parse_shift(turno_raw)
                    if is_jc:
                        warnings.append(
                            f"Teacher '{nombre_completo}' has 'Jornada completa'; mapped to MORNING."
                        )

                    carga = _safe_int(row.get("Carga académica")) or _safe_int(row.get("Carga academica"))

                    teacher = Teacher(
                        id=uuid.uuid4(),
                        project_id=project_id,
                        nip=nip,
                        dui=dui,
                        id_persona=id_persona,
                        full_name=nombre_completo or "Sin nombre",
                        email=_safe_str(row.get("Correo institucional")),
                        phone=_safe_str(row.get("Teléfono")) or _safe_str(row.get("Telefono")),
                        cargo=_safe_str(row.get("Cargo")),
                        specialty=_safe_str(row.get("Especialidad")),
                        max_hours_per_week=carga,
                        shift=shift,
                    )
                    teacher_map[dedup_key] = teacher
                    db.add(teacher)

                # -- Teacher-Subject assignment ---------------------------------
                asignatura_raw = _safe_str(row.get("Asignatura"))
                subject_code = _normalize_asignatura(asignatura_raw)
                grado = _safe_int(row.get("Grado"))
                seccion = _safe_str(row.get("Sección")) or _safe_str(row.get("Seccion"))

                if subject_code and subject_code in subject_map:
                    teacher = teacher_map[dedup_key]
                    ts = TeacherSubject(
                        id=uuid.uuid4(),
                        project_id=project_id,
                        teacher_id=teacher.id,
                        subject_id=subject_map[subject_code].id,
                        grade=grado,
                        section_code=seccion,
                    )
                    teacher_subject_records.append(ts)
                    db.add(ts)
                elif asignatura_raw:
                    warnings.append(
                        f"Unknown subject '{asignatura_raw}' for teacher row; skipped assignment."
                    )

                # -- Create sections from docentes that don't exist in students --
                if grado is not None and seccion:
                    turno_raw = _safe_str(row.get("Turno"))
                    shift, _ = _parse_shift(turno_raw)
                    key = (shift, grado, seccion)
                    if key not in section_map:
                        tipo = _safe_str(row.get("Tipo"))
                        opcion = _safe_str(row.get("Opción")) or _safe_str(row.get("Opcion"))
                        sec = Section(
                            id=uuid.uuid4(),
                            project_id=project_id,
                            code=seccion,
                            name=f"G{grado}{seccion}",
                            grade=grado,
                            shift=shift,
                            student_count=None,  # no student data for this section
                            tipo=tipo,
                            opcion=opcion,
                        )
                        section_map[key] = sec
                        db.add(sec)
                        warnings.append(
                            f"Section G{grado}{seccion} ({shift.value}) found in Docentes but not Estudiantes; "
                            f"created with unknown student count."
                        )

        # ===================================================================
        # 3b. REMEDIATION teacher-subject assignments
        # ===================================================================
        # Business rules:
        # - RE_LEN: taught by the same teacher that teaches LEN to that section
        #   (ciclo 1-2 generalistas) or by SOC/Letras specialists (ciclo 3)
        # - RE_MAT: taught by the same teacher that teaches MAT to that section
        #   (ciclo 1-2 generalistas) or by CIE/Ciencias specialists (ciclo 3)
        re_len_subj = subject_map.get("RE_LEN")
        re_mat_subj = subject_map.get("RE_MAT")

        if re_len_subj and re_mat_subj:
            # Collect existing assignments: (teacher_id, subject_code, grade, section_code)
            existing_ts = set()
            for ts in teacher_subject_records:
                subj = None
                for code, s in subject_map.items():
                    if s.id == ts.subject_id:
                        subj = code
                        break
                if subj:
                    existing_ts.add((ts.teacher_id, subj, ts.grade, ts.section_code))

            re_assignments_added = 0
            for ts in list(teacher_subject_records):  # iterate over copy
                subj_code = None
                for code, s in subject_map.items():
                    if s.id == ts.subject_id:
                        subj_code = code
                        break

                # Teacher that teaches LEN → also can teach RE_LEN
                if subj_code == "LEN":
                    key = (ts.teacher_id, "RE_LEN", ts.grade, ts.section_code)
                    if key not in existing_ts:
                        re_ts = TeacherSubject(
                            id=uuid.uuid4(),
                            project_id=project_id,
                            teacher_id=ts.teacher_id,
                            subject_id=re_len_subj.id,
                            grade=ts.grade,
                            section_code=ts.section_code,
                        )
                        teacher_subject_records.append(re_ts)
                        db.add(re_ts)
                        existing_ts.add(key)
                        re_assignments_added += 1

                # Teacher that teaches MAT → also can teach RE_MAT
                if subj_code == "MAT":
                    key = (ts.teacher_id, "RE_MAT", ts.grade, ts.section_code)
                    if key not in existing_ts:
                        re_ts = TeacherSubject(
                            id=uuid.uuid4(),
                            project_id=project_id,
                            teacher_id=ts.teacher_id,
                            subject_id=re_mat_subj.id,
                            grade=ts.grade,
                            section_code=ts.section_code,
                        )
                        teacher_subject_records.append(re_ts)
                        db.add(re_ts)
                        existing_ts.add(key)
                        re_assignments_added += 1

                # SOC/Sociales specialists → can teach RE_LEN (for ciclo 3)
                if subj_code == "SOC" and ts.grade and ts.grade >= 7:
                    key = (ts.teacher_id, "RE_LEN", ts.grade, ts.section_code)
                    if key not in existing_ts:
                        re_ts = TeacherSubject(
                            id=uuid.uuid4(),
                            project_id=project_id,
                            teacher_id=ts.teacher_id,
                            subject_id=re_len_subj.id,
                            grade=ts.grade,
                            section_code=ts.section_code,
                        )
                        teacher_subject_records.append(re_ts)
                        db.add(re_ts)
                        existing_ts.add(key)
                        re_assignments_added += 1

                # CIE/Ciencias specialists → can teach RE_MAT (for ciclo 3)
                if subj_code == "CIE" and ts.grade and ts.grade >= 7:
                    key = (ts.teacher_id, "RE_MAT", ts.grade, ts.section_code)
                    if key not in existing_ts:
                        re_ts = TeacherSubject(
                            id=uuid.uuid4(),
                            project_id=project_id,
                            teacher_id=ts.teacher_id,
                            subject_id=re_mat_subj.id,
                            grade=ts.grade,
                            section_code=ts.section_code,
                        )
                        teacher_subject_records.append(re_ts)
                        db.add(re_ts)
                        existing_ts.add(key)
                        re_assignments_added += 1

            if re_assignments_added:
                logger.info("Added %d remediation teacher-subject assignments", re_assignments_added)

        # ===================================================================
        # 4. GRADE SUBJECT LOADS
        # ===================================================================
        all_grades = {s.grade for s in section_map.values()}
        grade_load_count = 0

        for grade in sorted(all_grades):
            if grade not in CARGA_HORARIA:
                warnings.append(f"No carga horaria rules defined for grade {grade}; skipping loads.")
                continue
            for subj_code, hours in CARGA_HORARIA[grade].items():
                if subj_code in subject_map:
                    gsl = GradeSubjectLoad(
                        id=uuid.uuid4(),
                        project_id=project_id,
                        grade=grade,
                        subject_id=subject_map[subj_code].id,
                        hours_per_week=hours,
                    )
                    db.add(gsl)
                    grade_load_count += 1

        # ===================================================================
        # 5. TIME SLOTS
        # ===================================================================
        all_shifts = {s.shift for s in section_map.values()}
        if not all_shifts:
            all_shifts = {Shift.MORNING}
        time_slots = _generate_time_slots(project_id, all_shifts, all_grades)
        for ts in time_slots:
            db.add(ts)

        # ===================================================================
        # 6. Update project status
        # ===================================================================
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = ProjectStatus.DATA_LOADED

        # ===================================================================
        # 7. Finalize import record
        # ===================================================================
        data_import.status = ImportStatus.VALIDATED if not errors else ImportStatus.ERROR
        data_import.row_counts = {
            "students_rows": len(df_students),
            "teachers_rows": len(df_teachers),
            "teachers_created": len(teacher_map),
            "subjects_created": len(subject_map),
            "sections_created": len(section_map),
            "teacher_subjects_created": len(teacher_subject_records),
            "grade_subject_loads_created": grade_load_count,
            "time_slots_created": len(time_slots),
        }
        data_import.errors = errors if errors else None
        db.commit()

        return ImportSummary(
            import_id=data_import.id,
            status=data_import.status.value,
            teachers_count=len(teacher_map),
            subjects_count=len(subject_map),
            sections_count=len(section_map),
            teacher_subjects_count=len(teacher_subject_records),
            grade_subject_loads_count=grade_load_count,
            time_slots_count=len(time_slots),
            errors=errors,
            warnings=warnings,
        )

    except Exception as exc:
        logger.exception("Error parsing school Excel: %s", exc)
        data_import.status = ImportStatus.ERROR
        data_import.errors = [str(exc)]
        db.commit()
        return ImportSummary(
            import_id=data_import.id,
            status=ImportStatus.ERROR.value,
            errors=[str(exc)],
            warnings=warnings,
        )
