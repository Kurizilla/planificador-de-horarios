"""
School Schedule Planner — API.
FastAPI app; health check en /health; API bajo /api/v1.
"""
import logging
import os
from pathlib import Path

# Load .env so environment variables are available (direnv optional)
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    for _p in (_root / ".env", Path(__file__).resolve().parent / ".env"):
        if _p.exists():
            load_dotenv(_p, override=True)
            break
    else:
        load_dotenv()
except ImportError:
    pass

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError

from app.api import assistant, auth, exports, projects, schedules, school_data, users

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.config import get_settings
    s = get_settings()
    if s.is_jwt_secret_unsafe:
        logger.warning(
            "JWT_SECRET is the default value. Set JWT_SECRET in production to a strong random secret."
        )
    if not s.allow_public_registration:
        logger.info("Public registration is disabled (ALLOW_PUBLIC_REGISTRATION=false).")

    yield


app = FastAPI(
    title="School Schedule Planner API",
    description="API for school schedule planning and generation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: si CORS_ORIGINS no está definida, fallback para dev local.
_cors_origins = os.getenv("CORS_ORIGINS")
if _cors_origins:
    allow_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
else:
    allow_origins = [
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cors_headers_for_request(request: Request) -> dict:
    """CORS headers for error responses (5xx) so the browser shows the real error instead of 'CORS'."""
    origin = (request.headers.get("origin") or request.headers.get("Origin") or "").strip()
    if origin and origin in allow_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return {}


@app.exception_handler(SQLAlchemyOperationalError)
async def database_connection_exception_handler(request: Request, exc: SQLAlchemyOperationalError):
    """Database connection errors: friendly message and 503."""
    logger.warning("Database connection error: %s", exc)
    detail = (
        "No se pudo conectar con la base de datos. "
        "Verificá que PostgreSQL esté corriendo (puerto 5432) o usá SQLite en desarrollo con SQLITE=1."
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": detail},
        headers=_cors_headers_for_request(request),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return 500 with CORS so the frontend receives the error."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": str(exc) or "Internal server error"},
        headers=_cors_headers_for_request(request),
    )


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(school_data.router, prefix="/api/v1")
app.include_router(schedules.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1")
app.include_router(assistant.router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": "School Schedule Planner API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
