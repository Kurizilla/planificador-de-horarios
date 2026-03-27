"""
Comprueba conexión a la DB usando DATABASE_URL.
Uso: python scripts/check_db.py
  - Intenta conectar hasta 5 veces (1 s entre intentos), timeout 10 s por intento.
  - Imprime "Conexión OK" o el error y sale con 0 o 1.
"""
import os
import sys
import time

from sqlalchemy import create_engine

def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[check_db] DATABASE_URL no definida.", file=sys.stderr)
        sys.stderr.flush()
        return 1
    # Timeout corto para no colgar el arranque (Cloud Run mata por DEADLINE_EXCEEDED)
    max_attempts = 5
    for i in range(max_attempts):
        try:
            engine = create_engine(url, connect_args={"connect_timeout": 10})
            with engine.connect():
                pass
            print("[check_db] Conexión OK.", file=sys.stderr)
            sys.stderr.flush()
            return 0
        except Exception as e:
            print(f"[check_db] Intento {i+1}/{max_attempts}: {e}", file=sys.stderr)
            sys.stderr.flush()
            if i == max_attempts - 1:
                return 1
            time.sleep(1)
    return 1

if __name__ == "__main__":
    sys.exit(main())
