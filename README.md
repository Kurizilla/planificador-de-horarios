# Planificador de Horarios Escolares

Sistema de planificacion de horarios para directores de escuelas. Genera horarios semanales optimizados a partir de datos del centro educativo (docentes, secciones, materias) y permite editarlos via drag-and-drop o con un asistente de IA.

## Funcionalidades

- **Importacion de datos**: Sube un Excel con las hojas de Estudiantes y Docentes (formato MINEDUCYT). El sistema parsea, deduplica docentes, crea secciones, materias (incluyendo Remediacion), y genera las franjas horarias automaticamente.
- **Generacion de horarios con CP-SAT**: Motor de optimizacion basado en Google OR-Tools (Constraint Programming) que respeta todas las reglas de negocio y busca la solucion optima.
- **Visualizacion en grilla**: Horario semanal por seccion o por docente, con colores por materia y badges de conflictos/advertencias.
- **Drag-and-drop**: Arrastra celdas para intercambiar bloques horarios. El sistema re-valida conflictos despues de cada cambio.
- **Asistente de IA**: Chat lateral con lenguaje natural para editar el horario (reasignar docente, mover clase, consultar carga). Usa xAI Grok.
- **Exportacion a Excel**: Descarga el horario formateado con una hoja por seccion + resumen de carga docente.
- **Validacion y estados**: Flujo draft -> validado -> exportado con deteccion de conflictos y advertencias.
- **Audit trail**: Cada cambio (generacion, swap, movimiento, edicion por IA) queda registrado.

## Reglas de Negocio del Motor de Planificacion

El solver CP-SAT aplica las siguientes reglas:

### Restricciones duras (se cumplen siempre)
- Cada seccion tiene exactamente una materia por bloque horario
- Un docente no puede estar en dos secciones al mismo tiempo
- Cada seccion recibe las horas semanales exactas por materia segun la Carga Horaria de su grado
- Los docentes solo imparten materias para las que estan habilitados
- Una materia no puede repetirse dos veces en el mismo dia para una seccion

### Restricciones blandas (se optimizan)
- Lenguaje, Matematica, y Remediacion no deben asignarse en la primera hora del dia (advertencia si es inevitable)
- Carga docente cercana a 25 horas semanales
- Generalistas ensenan todas las materias a "su" seccion en ciclo 1-2 (grados 2-6)

### Carga Horaria por Grado

| Grado | LEN | MAT | RE_LEN | RE_MAT | CIE | SOC | ART | EDF | ING | Total |
|-------|-----|-----|--------|--------|-----|-----|-----|-----|-----|-------|
| 2     | 5   | 5   | 4      | 4      | 1   | 1   | 2   | 3   | -   | 25    |
| 3     | 5   | 5   | 4      | 4      | 1   | 1   | 2   | 3   | -   | 25    |
| 4-6   | 5   | 5   | 3      | 3      | 2   | 1   | 3   | 3   | -   | 25    |
| 7-9   | 5   | 5   | 3      | 3      | 2   | 2   | -   | 3   | 3   | 26    |
| 10-11 | 5   | 5   | 1      | -      | 6   | 4-5 | -   | 2-3 | 3-4 | 28    |

RE = Remediacion (clases digitales). Duracion de clase: 55 min (grados 2-9), 45 min (bachillerato).

## Arquitectura

```
backend/                    FastAPI (Python 3.12)
  app/
    api/                    Routers: auth, projects, school_data, schedules, assistant, exports
    core/                   Config, JWT security, dependencies
    db/                     SQLAlchemy models (16 tablas), enums, Alembic migrations
    schemas/                Pydantic request/response models
    services/
      school_data_parser    Parser del Excel MINEDUCYT
      schedule_engine       CP-SAT solver + StubPlanner + deteccion de conflictos
      schedule_service      Orquestacion: generar, mover, swap, validar
      schedule_assistant    Asistente IA (xAI Grok)
      schedule_exporter     Generacion de Excel de salida
      schedule_actions      Aplicacion de acciones del asistente

frontend/                   React 19 + Vite
  src/
    pages/
      ScheduleView          Grilla semanal + drag-and-drop + toolbar
      DataImport            Carga de Excel + preview de datos
      ProjectNew/List       CRUD de proyectos
      Login/Register        Autenticacion
    components/
      ScheduleAssistantWidget   Chat flotante con IA
      FileInput                 Componente de upload
      ErrorModal                Modal de errores

src/clients/                xAI API client (OpenAI-compatible)
```

### Modelo de Datos (16 tablas)

```
users ── projects ─┬─ teachers ── teacher_subjects ── subjects
                   ├─ sections
                   ├─ time_slots
                   ├─ teacher_availabilities
                   ├─ business_rules
                   ├─ grade_subject_loads
                   ├─ data_imports
                   ├─ schedule_versions ─┬─ schedule_entries
                   │                     └─ schedule_changes
                   └─ assistant_conversations ── assistant_messages
```

### Stack Tecnologico

| Componente | Tecnologia |
|-----------|-----------|
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic v2 |
| Frontend | React 19, React Router 7, Vite |
| Base de datos | PostgreSQL (prod) / SQLite (dev) |
| Solver | Google OR-Tools CP-SAT |
| IA | xAI Grok (API compatible con OpenAI) |
| Infraestructura | Docker, Cloud Run (GCP) |

## Quick Start

### Opcion 1: Desarrollo local (mas rapido)

```bash
# Instalar dependencias
uv sync --extra backend       # Python
cd frontend && npm install     # Node

# Terminal 1: Backend
cd backend
SQLITE=1 ../.venv/bin/python3 -m alembic upgrade head
SQLITE=1 ../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

Abrir **http://localhost:5173**

### Opcion 2: Docker Compose

```bash
docker compose up --build
```

Abrir **http://localhost:3000**

### Variables de entorno

Copiar `env.example` a `.env` y configurar:

```bash
# Obligatorio para el asistente IA:
XAI_API_KEY=tu-clave-xai

# Obligatorio en produccion:
JWT_SECRET=un-secreto-fuerte-random

# Base de datos (default: PostgreSQL via Docker):
DATABASE_URL=postgresql://scheduler:scheduler@localhost:5432/scheduler
# O para dev sin Docker:
SQLITE=1
```

## Flujo de Uso

1. **Registrarse / Login**
2. **Crear proyecto** (nombre, centro educativo)
3. **Importar datos** — subir Excel MINEDUCYT + codigo del centro (ej: `10001`)
4. **Generar horario** — seleccionar turno (Matutino/Vespertino), click "Generar Horario" (~5-10 seg)
5. **Revisar** — navegar entre secciones, ver carga docente
6. **Editar** — drag-and-drop para intercambiar bloques, o usar el asistente IA
7. **Validar** — verificar 0 conflictos
8. **Exportar** — descargar Excel formateado

## Formato del Excel de Entrada

El sistema acepta el formato estandar de MINEDUCYT con dos hojas:

**Hoja "Estudiantes":**
| Columna | Descripcion |
|---------|-------------|
| Codigo | Codigo del centro educativo |
| NIE | Numero de identificacion del estudiante |
| Nombres | Nombres del estudiante |
| Apellidos | Apellidos del estudiante |
| Turno | Matutino / Vespertino / Jornada completa |
| Grado | 2-11 |
| Seccion | A, B, C... |
| Tipo | (Bachillerato) General / Tecnico Vocacional / Tecnico Productivo |
| Opcion | (Bachillerato tecnico) Especialidad |

**Hoja "Docentes":**
| Columna | Descripcion |
|---------|-------------|
| NIP | Numero de identificacion profesional |
| DUI | Documento de identidad |
| Codigo | Codigo del centro educativo |
| Nombre_completo | Nombre completo del docente |
| Cargo | DOCENTE / INTERINO / etc. |
| Turno | Matutino / Vespertino |
| Grado | Grado que atiende |
| Seccion | Seccion que atiende |
| Carga academica | Horas maximas por semana |
| Especialidad | Formacion profesional |
| Asignatura | Materia que imparte |

## API

La documentacion interactiva de la API esta disponible en **http://localhost:8000/docs** (Swagger UI).

### Endpoints principales

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Registro de usuario |
| POST | `/api/v1/auth/login` | Login (JWT) |
| POST | `/api/v1/projects` | Crear proyecto |
| POST | `/api/v1/projects/{id}/school-data/upload` | Importar Excel |
| GET | `/api/v1/projects/{id}/school-data/summary` | Resumen de datos importados |
| GET | `/api/v1/projects/{id}/teachers` | Listar docentes |
| GET | `/api/v1/projects/{id}/sections` | Listar secciones |
| POST | `/api/v1/projects/{id}/schedules/generate` | Generar horario (CP-SAT) |
| GET | `/api/v1/projects/{id}/schedules/{vid}/entries` | Obtener entradas del horario |
| POST | `/api/v1/projects/{id}/schedules/{vid}/move` | Mover/intercambiar entrada |
| POST | `/api/v1/projects/{id}/schedules/{vid}/validate` | Validar horario |
| GET | `/api/v1/projects/{id}/schedules/{vid}/export` | Exportar Excel |
| POST | `/api/v1/projects/{id}/assistant/chat` | Chat con asistente IA |
| POST | `/api/v1/projects/{id}/assistant/apply` | Aplicar acciones del asistente |

## Despliegue

Ver [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) para instrucciones de despliegue en Google Cloud Run.

```bash
# Build y deploy
make build-push
make deploy
```

## Desarrollo

Ver [docs/setup.md](docs/setup.md) para configuracion detallada del entorno de desarrollo.

### Estructura de archivos clave

```
backend/app/services/schedule_engine.py    Motor CP-SAT (653 lineas)
backend/app/services/schedule_service.py   Orquestacion (669 lineas)
backend/app/services/school_data_parser.py Parser Excel (664 lineas)
backend/app/db/models.py                   16 modelos SQLAlchemy
frontend/src/pages/ScheduleView.jsx        Grilla + DnD (819 lineas)
```

## Licencia

Proyecto interno - MINEDUCYT / GOES.
