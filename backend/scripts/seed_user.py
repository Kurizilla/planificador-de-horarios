"""
Seed usuarios en la DB. Crea admin y director si las variables están definidas.

Ejecución local (desde backend/):
  SQLITE=1 python scripts/seed_user.py

Variables de entorno:
- SEED_ADMIN_EMAIL + SEED_ADMIN_PASSWORD: crea/actualiza usuario admin.
- SEED_DIRECTOR_EMAIL + SEED_DIRECTOR_PASSWORD: crea/actualiza usuario director.

Si no se definen, usa valores por defecto para desarrollo local.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.db.models import User

# Admin (valores por defecto para dev)
ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "admin123")
ADMIN_NAME = os.getenv("SEED_ADMIN_NAME", "Admin")

# Director (valores por defecto para dev)
DIRECTOR_EMAIL = os.getenv("SEED_DIRECTOR_EMAIL", "director@test.com")
DIRECTOR_PASSWORD = os.getenv("SEED_DIRECTOR_PASSWORD", "test1234")
DIRECTOR_NAME = os.getenv("SEED_DIRECTOR_NAME", "Director")


def upsert_user(db, email: str, password: str, full_name: str, role: str):
    """Crea o actualiza un usuario."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        existing.password_hash = hash_password(password)
        existing.role = role
        existing.full_name = full_name or existing.full_name
        existing.is_active = True
        db.commit()
        print(f"[seed] {role} actualizado: {email}")
    else:
        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
        )
        db.add(user)
        db.commit()
        print(f"[seed] {role} creado: {email}")


def main():
    db = SessionLocal()
    try:
        upsert_user(db, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME, "admin")
        upsert_user(db, DIRECTOR_EMAIL, DIRECTOR_PASSWORD, DIRECTOR_NAME, "director")
    finally:
        db.close()


if __name__ == "__main__":
    main()
