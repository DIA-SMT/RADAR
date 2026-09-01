"""Configuración central de RADAR. Todo se define en el archivo .env (ver .env.example)."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
_ENV = BASE_DIR / ".env"
try:
    load_dotenv(_ENV)
except UnicodeDecodeError:
    # .env guardado como ANSI/cp1252 por algún editor de Windows
    load_dotenv(_ENV, encoding="cp1252")


def _entero(nombre: str, defecto: int) -> int:
    crudo = (os.getenv(nombre) or "").strip()
    if not crudo:
        return defecto
    try:
        return int(crudo)
    except ValueError:
        sys.exit(
            f"Configuración inválida: {nombre}={crudo!r} debe ser un número entero. Revisar el .env."
        )


def _ids_telegram() -> set:
    """IDs habilitados. Un valor no numérico corta el arranque: mejor que quedar abierto por un typo."""
    crudo = (os.getenv("TELEGRAM_ALLOWED_IDS") or "").replace(";", ",").replace(" ", ",")
    ids = set()
    for parte in crudo.split(","):
        parte = parte.strip()
        if not parte:
            continue
        try:
            ids.add(int(parte))
        except ValueError:
            sys.exit(
                f"Configuración inválida: TELEGRAM_ALLOWED_IDS contiene {parte!r}, que no es un ID numérico. "
                "Formato esperado: IDs separados por coma, ej. 111111,222222. Revisar el .env."
            )
    return ids


DATA_DIR = Path(os.getenv("RADAR_DATA_DIR", str(BASE_DIR / "data")))
CAPTURAS_DIR = DATA_DIR / "capturas"
DB_PATH = DATA_DIR / "radar.db"
PUBLIC_DIR = BASE_DIR / "public"  # logos e imágenes institucionales (contenido no sensible)

# Base de datos: si hay DATABASE_URL (cadena de conexión de Supabase/Postgres) se usa esa;
# si está vacía, se usa SQLite local (data/radar.db) para desarrollo.
DATABASE_URL = (os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or "").strip()

# Login del panel con usuarios de Supabase Auth (los usuarios se crean en el dashboard).
# Si ambos valores están, el panel usa página de login; si no, cae a PANEL_PASSWORD (HTTP Basic).
SUPABASE_URL = (os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_PUBLISHABLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    or ""
).strip()

# Clave con la que se firman las cookies de sesión del panel.
SESSION_SECRET = (os.getenv("SESSION_SECRET") or "").strip()

# Zona horaria para los timestamps de los casos.
RADAR_TZ = os.getenv("RADAR_TZ", "America/Argentina/Tucuman").strip()

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
TELEGRAM_ALLOWED_IDS = _ids_telegram()

# Clasificador: OpenRouter (o cualquier endpoint compatible con la API de OpenAI)
LLM_API_KEY = (os.getenv("OPENROUTER_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
LLM_MODEL = (os.getenv("LLM_MODEL") or "anthropic/claude-sonnet-4.5").strip()

PANEL_PORT = _entero("PANEL_PORT", 8000)
PANEL_BASE_URL = (os.getenv("PANEL_BASE_URL") or f"http://localhost:{PANEL_PORT}").strip().rstrip("/")
PANEL_PASSWORD = (os.getenv("PANEL_PASSWORD") or "").strip()

# Sin contraseña, el panel solo escucha en esta máquina; con contraseña, en todas las interfaces.
PANEL_HOST = (os.getenv("PANEL_HOST") or "").strip() or ("0.0.0.0" if PANEL_PASSWORD else "127.0.0.1")

DATA_DIR.mkdir(parents=True, exist_ok=True)
CAPTURAS_DIR.mkdir(parents=True, exist_ok=True)
