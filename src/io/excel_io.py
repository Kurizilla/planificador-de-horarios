"""
Carga y guardado de Excel para Backlog (input) y Story Map (output).
Soporta Backlog_Base_LXP.xlsx, fallback a demo data, validación de columnas mínimas y Comentarios.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

import pandas as pd

INPUT_BACKLOG_NAME = "Backlog_Base_LXP.xlsx"
BACKLOG_ENE26_NAME = "Backlog_ENE26_LXP.xlsx"
ENE26_SHEET = "Backlog - LXP"
ENE26_COLUMNS = ("Module / Functionality", "Type", "Priority", "Description")
INPUTS_DIR = "inputs"
OUTPUTS_DIR = "outputs"

# Al menos una de estas columnas debe existir en el backlog de entrada
BACKLOG_MIN_COLUMNS = (
    "Título", "Titulo", "Descripción", "Descripcion", "Módulo", "Modulo", "Prioridad", "Funcionalidad",
    "Module / Functionality", "Description", "Priority", "Type",
)

# Para distinguir inventario real de template: al menos una de estas
INVENTORY_COLUMNS = (
    "Módulo", "Modulo", "Submódulo", "Submodulo", "Funcionalidad", "Prioridad",
    "Module / Functionality", "Priority", "Type",
)

# Textos típicos de celdas de template/guía (si aparecen 2+ en la primera fila de datos → template)
TEXTS_TEMPLATE = (
    "nuevo id único",
    "narrativa",
    "como... quiero... para",
    "bloque estructurado",
    "escenarios positivos",
    "escenarios negativos",
    "sugerencias de diseño",
    "reglas de negocio",
    "alertas y errores",
    "recomendaciones ux",
    "criterios de aceptación",
    "celda vacía",
    "destinada al feedback",
)

# Columnas del Story Map (Fase 1) — alineadas a schema contractual (epic, phase, context_refs)
STORYMAP_COLUMNS = [
    "ID",
    "Título",
    "User Story",
    "Short Description",
    "Descripción Funcional",
    "Epic",
    "Módulo / Submódulo",
    "Phase",
    "Prioridad",
    "Context Refs",
    "Score de Confianza",
    "Disclaimer / Notas",
    "Comentarios",
]

COL_COMENTARIOS = "Comentarios"
COL_SCORE = "Score de Confianza"
COL_DISCLAIMER = "Disclaimer / Notas"

# Columnas del HU Breakdown (Fase 2A) — solo cardinalidad y cortes lógicos, NO HUs completas
# primary_role: Docente|Estudiante|Sistema|IA|Administrador
# domains: LMS|CMS|IA|Tracking|Offline|Evaluations|Progress
HU_BREAKDOWN_COLUMNS = [
    "story_map_id",
    "hu_id",
    "hu_title",
    "rationale",
    "primary_role",
    "domains",
    "context_refs",
]

# Columnas de Historias Funcionales Revisables (Nueva Fase 1)
# Input: Excel Module/Functionality → Output: historias funcionales para revisión humana
# Nombres alineados a Product: user_story_id, user_story_title; descripcion_funcional con contrato estricto
HISTORIAS_FUNCIONALES_COLUMNS = [
    "module_id",
    "module_name",
    "functionality_id",
    "functionality_name",
    "priority",
    "user_story_id",
    "user_story_title",
    "user_story",
    "descripcion_funcional",
    "comentarios",
    "comentarios_funcionalidad",
    "comentarios_modulo",
]


def dataframe_from_user_stories(stories: list) -> pd.DataFrame:
    """Convierte lista de UserStory objects (DB) en DataFrame con HISTORIAS_FUNCIONALES_COLUMNS.

    Esta es la función puente entre DB y pipeline: garantiza que el DataFrame
    generado tiene exactamente las mismas columnas, en el mismo orden, que el
    Excel producido por el pipeline.
    """
    rows = []
    for s in stories:
        rows.append({
            "module_id": s.module_id,
            "module_name": s.module_name,
            "functionality_id": s.functionality_id,
            "functionality_name": s.functionality_name,
            "priority": s.priority or "",
            "user_story_id": s.user_story_id,
            "user_story_title": s.user_story_title,
            "user_story": s.user_story,
            "descripcion_funcional": s.descripcion_funcional,
            "comentarios": s.comentarios or "",
            "comentarios_funcionalidad": s.comentarios_funcionalidad or "",
            "comentarios_modulo": getattr(s, "comentarios_modulo", None) or "",
        })
    df = pd.DataFrame(rows, columns=list(HISTORIAS_FUNCIONALES_COLUMNS))
    return df


def dataframe_from_detailed_backlogs(backlogs: list) -> pd.DataFrame:
    """Convierte lista de DetailedBacklog objects (DB) en DataFrame con BACKLOG_DETALLADO_P2_COLUMNS."""
    rows = []
    for b in backlogs:
        rows.append({
            "id_historia_usuario": b.id_historia_usuario,
            "id_modulo": b.id_modulo,
            "nombre_modulo": b.nombre_modulo,
            "id_funcionalidad": b.id_funcionalidad,
            "nombre_funcionalidad": b.nombre_funcionalidad,
            "titulo_historia_usuario": b.titulo_historia_usuario,
            "user_story": b.user_story,
            "descripcion_funcional": b.descripcion_funcional,
            "criterios_aceptacion": b.criterios_aceptacion,
            "definition_of_done": b.definition_of_done,
            "reglas_negocio": b.reglas_negocio,
            "ux_ui": b.ux_ui,
            "alertas_errores": b.alertas_errores,
            "data_event_tracking": b.data_event_tracking,
            "dependencias": b.dependencias,
            "flow_ids": b.flow_ids,
            "assumptions_limits": b.assumptions_limits,
            "resultado_esperado": b.resultado_esperado,
            "campo_esperado": b.campo_esperado,
            "hu_formato_oficial": b.hu_formato_oficial,
            "comentarios": b.comentarios or "",
        })
    df = pd.DataFrame(rows, columns=list(BACKLOG_DETALLADO_P2_COLUMNS))
    return df

# Columnas que Fase 1 DEBE tener para que Fase 2 pueda copiar identidad (1:1). Si falta alguna, Fase 2 falla.
FASE1_IDENTITY_COLUMNS = [
    "module_id",
    "module_name",
    "functionality_id",
    "functionality_name",
    "user_story_id",
    "user_story_title",
    "user_story",
    "descripcion_funcional",
]

# Columnas mínimas requeridas para Fase 1.5 (Flow Intelligence). Mismo esquema que output Fase 1.
PHASE1_5_REQUIRED_COLUMNS = [
    "module_id",
    "module_name",
    "functionality_id",
    "functionality_name",
    "user_story_id",
    "user_story_title",
    "user_story",
    "descripcion_funcional",
    "priority",
]

# Columnas del Backlog Detallado (Fase 2) — schema contractual (persona, operational_context, DoD, deps, data/events, context_refs)
# Usado por flujo legacy Fase 2B (storymap + hu_breakdown).
BACKLOG_DETALLADO_COLUMNS = [
    "ID",
    "Título",
    "Epic",
    "Módulo / Submódulo",
    "Phase",
    "Prioridad",
    "Persona",
    "User Story",
    "Operational Context",
    "Criterios de Aceptación (Gherkin)",
    "Definition of Done",
    "Reglas de negocio",
    "UX/UI",
    "Alertas y errores esperados",
    "Data/Event Tracking",
    "Dependencias In",
    "Dependencias Out",
    "Assumptions and Limits",
    "Context Refs",
    "Score de Confianza",
    "Disclaimer / Notas",
    "resultado_esperado",
    "campo_esperado",
    "hu_formato_oficial",
    "Comentarios",
]

# Columnas del Backlog Detallado Fase 2 cuando se ejecuta desde historias_funcionales_revisables (1:1).
# Identidad: copiadas exactamente desde Fase 1. Generados: solo los que Fase 2 produce.
BACKLOG_DETALLADO_P2_COLUMNS = [
    "id_historia_usuario",
    "id_modulo",
    "nombre_modulo",
    "id_funcionalidad",
    "nombre_funcionalidad",
    "titulo_historia_usuario",
    "user_story",
    "descripcion_funcional",
    "criterios_aceptacion",
    "definition_of_done",
    "reglas_negocio",
    "ux_ui",
    "alertas_errores",
    "data_event_tracking",
    "dependencias",
    "flow_ids",  # Fase 1.5: flujos en los que participa esta HU (ej. F-M01-01, F-M30-02)
    "assumptions_limits",
    "resultado_esperado",
    "campo_esperado",
    "hu_formato_oficial",
    "comentarios",
]


def _inputs_path(*parts: str) -> Path:
    base = Path(__file__).resolve().parent.parent.parent
    return base.joinpath(INPUTS_DIR, *parts)


def _outputs_path(*parts: str) -> Path:
    base = Path(__file__).resolve().parent.parent.parent
    return base.joinpath(OUTPUTS_DIR, *parts)


def get_demo_backlog_data() -> pd.DataFrame:
    """
    Datos de demostración cuando no existe Backlog_Base_LXP.xlsx.
    """
    return pd.DataFrame(
        [
            {
                "Título": "Login de usuario",
                "Descripción": "Acceso seguro con email/contraseña y recuperación.",
                "Módulo": "Autenticación",
            },
            {
                "Título": "Ver catálogo de cursos",
                "Descripción": "Listado filtrable y búsqueda de cursos disponibles.",
                "Módulo": "Catálogo",
            },
            {
                "Título": "Inscripción a curso",
                "Descripción": "Inscripción en uno o varios cursos con validación de cupos.",
                "Módulo": "Inscripciones",
            },
        ]
    )


def load_backlog_ene26(path: str | Path | None = None) -> pd.DataFrame:
    """
    Carga el backlog ENE26 desde sheet "Backlog - LXP".
    Valida que existan exactamente las 4 columnas: Module / Functionality, Type, Priority, Description.
    Normaliza: strip en strings, NaN -> "".
    """
    p = Path(path) if path is not None else _inputs_path(BACKLOG_ENE26_NAME)
    if not p.exists():
        raise FileNotFoundError(f"No existe: {p}")

    try:
        df = pd.read_excel(p, sheet_name=ENE26_SHEET)
    except Exception as e:
        raise IOError(f"Error leyendo {p} sheet '{ENE26_SHEET}': {e}") from e

    if df.empty:
        raise ValueError(f"El sheet '{ENE26_SHEET}' en {p} está vacío.")

    missing = [c for c in ENE26_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"El archivo {p} sheet '{ENE26_SHEET}' debe tener exactamente estas columnas: {list(ENE26_COLUMNS)}. Faltan: {missing}."
        )

    df = df[list(ENE26_COLUMNS)].copy()
    for c in df.columns:
        df[c] = df[c].apply(lambda v: "" if v is None or (isinstance(v, float) and (v != v)) else str(v).strip())
    return df


def _has_minimal_backlog_columns(df: pd.DataFrame) -> bool:
    """Comprueba que el DataFrame tenga al menos una columna esperada (Título, Descripción o Módulo o equivalentes)."""
    return any(c in df.columns for c in BACKLOG_MIN_COLUMNS)


def _has_inventory_columns(df: pd.DataFrame) -> bool:
    """Comprueba columnas de inventario: al menos una de Módulo, Submódulo, Funcionalidad, Prioridad (o equivalentes)."""
    return any(c in df.columns for c in INVENTORY_COLUMNS)


def _looks_like_template(df: pd.DataFrame) -> bool:
    """True si la primera fila de datos contiene 2+ frases típicas de template/guía."""
    if df.empty or len(df) < 1:
        return False
    row = df.iloc[0]
    concatenated = " ".join(str(v).lower() for v in row if v is not None and str(v).strip())
    return sum(1 for t in TEXTS_TEMPLATE if t in concatenated) >= 2


def load_backlog_input(path: str | Path | None = None) -> tuple[pd.DataFrame, Literal["real", "demo"]]:
    """
    Carga el backlog de entrada con validación explícita.

    - Si existe `inputs/Backlog_Base_LXP.xlsx` (o `path` si se indica), se usa.
    - Si no existe, se usa demo y se registra en log.
    - Si existe pero no tiene columnas mínimas (al menos una de: Título, Descripción, Módulo o equivalentes), falla.

    Returns:
        (DataFrame, "real"|"demo") y se loguea la fuente en consola.
    """
    used_path: Path | None = None
    if path is not None:
        p = Path(path)
        if not p.is_absolute():
            p = _inputs_path(path) if not Path(path).exists() else Path(path)
        if not p.exists():
            raise FileNotFoundError(f"No existe el archivo: {p}")
        used_path = p
    else:
        p = _inputs_path(INPUT_BACKLOG_NAME)
        if not p.exists():
            print("[storymap] Usando demo: Backlog_Base_LXP.xlsx no existe.")
            return (get_demo_backlog_data(), "demo")
        used_path = p

    try:
        df = pd.read_excel(p, sheet_name=0)
    except Exception as e:
        raise IOError(f"Error leyendo {p}: {e}") from e

    if df.empty:
        if path is None:
            print("[storymap] Usando demo: el archivo está vacío.")
            return (get_demo_backlog_data(), "demo")
        raise ValueError(f"El archivo {used_path} está vacío.")

    if not _has_minimal_backlog_columns(df):
        raise ValueError(
            f"El archivo {used_path} no tiene las columnas mínimas esperadas. "
            f"Se necesita al menos una de: {', '.join(BACKLOG_MIN_COLUMNS)}."
        )

    if _looks_like_template(df):
        raise ValueError(
            f"{used_path} parece template (textos de guía en la primera fila). "
            "Se espera inventario con filas de datos reales y columnas como: Módulo/Modulo, Submódulo/Submodulo, Funcionalidad, Prioridad (o equivalentes)."
        )

    if not _has_inventory_columns(df):
        raise ValueError(
            f"El archivo {used_path} no tiene columnas de inventario. "
            f"Se espera al menos una de: {', '.join(INVENTORY_COLUMNS)}."
        )

    src = "real"
    print(f"[storymap] Fuente: {used_path} (real)")
    return (df, src)


def load_storymap_output(path: str | Path) -> pd.DataFrame:
    """
    Carga un Excel de Story Map existente (p. ej. para el feedback loop).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    df = pd.read_excel(p, sheet_name=0)
    return df


def _ensure_output_dir(output_dir: str | Path) -> Path:
    d = Path(output_dir)
    if not d.is_absolute():
        d = _outputs_path() if output_dir == OUTPUTS_DIR else Path(output_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def validate_and_fix_storymap_df(df: pd.DataFrame) -> None:
    """
    Valida y corrige el DataFrame antes de exportar:
    - Score de Confianza: int entre 0 y 100 (se corrige/clamp si es posible).
    - Si Score < 70, Disclaimer / Notas no debe estar vacío (se asigna mensaje por defecto).
    Lanza ValueError si no se puede corregir (p. ej. Score no convertible a int).
    """
    for idx, row in df.iterrows():
        sid = row.get("ID", idx)
        raw = row.get(COL_SCORE)
        try:
            v = int(float(raw)) if raw is not None and str(raw).strip() != "" else 70
            v = max(0, min(100, v))
        except (TypeError, ValueError):
            raise ValueError(
                f"Score de Confianza inválido en fila ID={sid}: debe ser int 0-100, se obtuvo {raw!r}"
            ) from None
        df.at[idx, COL_SCORE] = v
        if v < 70:
            d = str(row.get(COL_DISCLAIMER) or "").strip()
            if not d:
                df.at[idx, COL_DISCLAIMER] = "Score < 70: revisión humana recomendada."


def save_storymap_output(
    df: pd.DataFrame,
    output_dir: str | Path = OUTPUTS_DIR,
    *,
    filename_prefix: str = "storymap",
    include_audit_columns: bool = False,
) -> str:
    """
    Valida el DataFrame, asegura columnas y guarda como Excel de Story Map en `output_dir`.

    Si include_audit_columns, se agregan columnas "Audit OK" y "Audit Issues".

    Returns:
        Ruta absoluta del archivo guardado (ej. outputs/storymap_20250125_143022.xlsx).
    """
    from datetime import datetime

    export_cols = list(STORYMAP_COLUMNS)
    if include_audit_columns:
        export_cols = export_cols + ["Audit OK", "Audit Issues"]
    for c in export_cols:
        if c not in df.columns:
            df[c] = ""
    df = df[export_cols].copy()
    validate_and_fix_storymap_df(df)

    out = _ensure_output_dir(output_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{filename_prefix}_{stamp}.xlsx"
    filepath = out / fname

    df.to_excel(filepath, index=False, sheet_name="Sheet1")
    return str(filepath.resolve())


def get_storymap_columns() -> list[str]:
    """Columnas estándar del Story Map (Fase 1)."""
    return list(STORYMAP_COLUMNS)


def _series_has_text(ser: pd.Series) -> pd.Series:
    """True donde la celda tiene texto real; False para vacío o string 'nan' (pandas NaN)."""
    s = ser.astype(str).str.strip()
    return (s != "") & (s.str.lower() != "nan")


def rows_with_comentarios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filtra filas donde la columna Comentarios (o comentarios, para Fase 1) tiene texto no vacío.
    Ignora celdas que son NaN (pandas las lee como string "nan").
    """
    col = COL_COMENTARIOS if COL_COMENTARIOS in df.columns else ("comentarios" if "comentarios" in df.columns else None)
    if col is None:
        return pd.DataFrame()
    mask = _series_has_text(df[col])
    return df[mask].copy()


def functionalities_with_comentarios_funcionalidad(df: pd.DataFrame) -> list[tuple[tuple[str, str], str]]:
    """
    Agrupa por (module_id, functionality_id) y devuelve las funcionalidades que tienen
    al menos una fila con comentarios_funcionalidad no vacío.
    Returns: [( (module_id, functionality_id), comment_text ), ...]
    El comment_text es el valor de la primera fila con comentario (todas deben aplicar a la funcionalidad).
    """
    if "comentarios_funcionalidad" not in df.columns:
        return []
    col = "comentarios_funcionalidad"
    out: list[tuple[tuple[str, str], str]] = []
    for key, grp in df.groupby(["module_id", "functionality_id"], dropna=False):
        mid, fid = str(key[0] or "").strip(), str(key[1] or "").strip()
        for _, row in grp.iterrows():
            c = str(row.get(col) or "").strip()
            if c and c.lower() != "nan":
                out.append(((mid, fid), c))
                break
    return out


def modules_with_comentarios_modulo(df: pd.DataFrame) -> list[tuple[str, str]]:
    """
    Agrupa por module_id y devuelve los módulos que tienen al menos una fila
    con comentarios_modulo no vacío.
    Returns: [(module_id, comment_text), ...]
    El comment_text es el valor de la primera fila con comentario en ese módulo.
    """
    if "comentarios_modulo" not in df.columns:
        return []
    col = "comentarios_modulo"
    out: list[tuple[str, str]] = []
    for module_id, grp in df.groupby("module_id", dropna=False):
        mid = str(module_id or "").strip()
        for _, row in grp.iterrows():
            c = str(row.get(col) or "").strip()
            if c and c.lower() != "nan":
                out.append((mid, c))
                break
    return out


def validate_and_fix_backlog_detallado_df(df: pd.DataFrame) -> None:
    """
    Valida y corrige el DataFrame de Backlog Detallado:
    - Score de Confianza: int 0-100 (clamp).
    - Si Score < 70, Disclaimer / Notas no vacío (mensaje por defecto).
    """
    for idx, row in df.iterrows():
        sid = row.get("ID", idx)
        raw = row.get(COL_SCORE)
        try:
            v = int(float(raw)) if raw is not None and str(raw).strip() != "" else 70
            v = max(0, min(100, v))
        except (TypeError, ValueError):
            raise ValueError(f"Score de Confianza inválido en fila ID={sid}: debe ser int 0-100, se obtuvo {raw!r}") from None
        df.at[idx, COL_SCORE] = v
        if v < 70:
            d = str(row.get(COL_DISCLAIMER) or "").strip()
            if not d:
                df.at[idx, COL_DISCLAIMER] = "Score < 70: revisión humana recomendada."


def save_hu_breakdown(
    df: pd.DataFrame,
    output_dir: str | Path = OUTPUTS_DIR,
    *,
    filename_prefix: str = "hu_breakdown",
) -> str:
    """
    Guarda el desglose de HUs (Fase 2A) como Excel.
    Columnas: story_map_id, hu_id, hu_title, rationale, domains, context_refs.

    Returns:
        Ruta absoluta (ej. outputs/hu_breakdown_20250125_143022.xlsx).
    """
    from datetime import datetime

    for c in HU_BREAKDOWN_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[list(HU_BREAKDOWN_COLUMNS)].copy()

    out = _ensure_output_dir(output_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{filename_prefix}_{stamp}.xlsx"
    filepath = out / fname
    df.to_excel(filepath, index=False, sheet_name="Sheet1")
    return str(filepath.resolve())


def load_hu_breakdown(path: str | Path) -> pd.DataFrame:
    """Carga un Excel de HU breakdown (Fase 2A)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe: {path}")
    return pd.read_excel(p, sheet_name=0)


def save_historias_funcionales(
    df: pd.DataFrame,
    output_dir: str | Path = OUTPUTS_DIR,
    *,
    filename_prefix: str = "historias_funcionales_revisables",
) -> str:
    """
    Guarda el Excel de Historias Funcionales Revisables (Nueva Fase 1).
    Columnas: story_map_id, hu_id, hu_title, user_story, descripcion_funcional, como_cuando_donde, comentarios.

    Returns:
        Ruta absoluta (ej. outputs/historias_funcionales_revisables_20250125_143022.xlsx).
    """
    from datetime import datetime

    for c in HISTORIAS_FUNCIONALES_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[list(HISTORIAS_FUNCIONALES_COLUMNS)].copy()

    out = _ensure_output_dir(output_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{filename_prefix}_{stamp}.xlsx"
    filepath = out / fname
    df.to_excel(filepath, index=False, sheet_name="Sheet1")
    return str(filepath.resolve())


def load_historias_funcionales(path: str | Path) -> pd.DataFrame:
    """Carga un Excel de Historias Funcionales Revisables. Asegura columnas estándar."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe: {path}")
    df = pd.read_excel(p, sheet_name=0)
    for c in HISTORIAS_FUNCIONALES_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    return df


def validate_phase1_5_columns(df: pd.DataFrame) -> None:
    """
    Valida que el Excel tenga las columnas mínimas requeridas por Fase 1.5 (Flow Intelligence).
    Si falta alguna columna, lanza ValueError con mensaje claro.
    """
    missing = [c for c in PHASE1_5_REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Fase 1.5 requiere las columnas: {PHASE1_5_REQUIRED_COLUMNS}. Faltan: {missing}. "
            "El archivo debe ser un output de Fase 1 (historias funcionales revisables)."
        )


def validate_phase1_identity_columns(df: pd.DataFrame) -> None:
    """
    Valida que cada fila del Excel de Fase 1 tenga todas las columnas de identidad requeridas por Fase 2.
    Si falta alguna columna o alguna fila tiene valor vacío en identidad, lanza ValueError con mensaje explícito.
    """
    missing_cols = [c for c in FASE1_IDENTITY_COLUMNS if c not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Fase 2 requiere que el archivo de Fase 1 tenga las columnas de identidad: {FASE1_IDENTITY_COLUMNS}. "
            f"Faltan: {missing_cols}. No se puede garantizar relación 1:1 ni identidad inmutable."
        )
    for idx, row in df.iterrows():
        for col in FASE1_IDENTITY_COLUMNS:
            val = row.get(col)
            if val is None or (isinstance(val, float) and math.isnan(val)) or str(val).strip() == "":
                raise ValueError(
                    f"Fase 2 requiere que cada fila tenga identidad completa. "
                    f"Fila (índice {idx}) tiene valor vacío o faltante en columna '{col}'. "
                    f"Valor actual: {repr(val)}. Corrija el archivo de Fase 1 y vuelva a ejecutar."
                )


def load_backlog_detallado(path: str | Path) -> pd.DataFrame:
    """Carga un Excel de Backlog Detallado. Asegura columnas estándar (añade faltantes con '')."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"No existe: {path}")
    df = pd.read_excel(p, sheet_name=0)
    for c in BACKLOG_DETALLADO_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    return df


def save_backlog_detallado(
    df: pd.DataFrame,
    output_dir: str | Path = OUTPUTS_DIR,
    *,
    filename_prefix: str = "backlog_detallado",
) -> str:
    """
    Asegura columnas de Backlog Detallado, valida y guarda como Excel.

    Returns:
        Ruta absoluta del archivo (ej. outputs/backlog_detallado_20250125_143022.xlsx).
    """
    from datetime import datetime

    for c in BACKLOG_DETALLADO_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[list(BACKLOG_DETALLADO_COLUMNS)].copy()
    validate_and_fix_backlog_detallado_df(df)

    out = _ensure_output_dir(output_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{filename_prefix}_{stamp}.xlsx"
    filepath = out / fname
    df.to_excel(filepath, index=False, sheet_name="Sheet1")
    return str(filepath.resolve())


def save_backlog_detallado_p2(
    df: pd.DataFrame,
    output_dir: str | Path = OUTPUTS_DIR,
    *,
    filename_prefix: str = "backlog_detallado_final",
) -> str:
    """
    Guarda el Excel de Backlog Detallado Fase 2 (desde historias funcionales, relación 1:1).
    Columnas: BACKLOG_DETALLADO_P2_COLUMNS (identidad + generados).
    """
    from datetime import datetime

    for c in BACKLOG_DETALLADO_P2_COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[list(BACKLOG_DETALLADO_P2_COLUMNS)].copy()
    out = _ensure_output_dir(output_dir)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{filename_prefix}_{stamp}.xlsx"
    filepath = out / fname
    df.to_excel(filepath, index=False, sheet_name="Sheet1")
    return str(filepath.resolve())
