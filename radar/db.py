"""Acceso a datos.

Dos backends con la misma interfaz:
- Postgres (Supabase): si config.DATABASE_URL está definida. Es el backend del piloto.
- SQLite (data/radar.db): si no hay DATABASE_URL. Sirve para desarrollo y demos sin credenciales.

Los timestamps se guardan como texto "YYYY-MM-DD HH:MM:SS" en hora de Tucumán
(config.RADAR_TZ), así el resto del sistema no depende del reloj del servidor.
"""
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from . import config

log = logging.getLogger("radar.db")

_PG = bool(config.DATABASE_URL)
if _PG:
    import psycopg
    from psycopg.rows import dict_row

try:
    from zoneinfo import ZoneInfo

    _TZ = ZoneInfo(config.RADAR_TZ)
except Exception:  # sin base de zonas horarias: se usa la hora local del servidor
    _TZ = None


def ahora() -> str:
    momento = datetime.now(_TZ) if _TZ else datetime.now()
    return momento.strftime("%Y-%m-%d %H:%M:%S")


ESTADOS = {
    "nuevo": "Nuevo",
    "derivado": "Derivado",
    "en_curso": "En curso",
    "resuelto": "Resuelto",
    "cerrado": "Cerrado",
    "en_observacion": "En observación",
}

ORIGENES = {
    "ia_sugerida": "Sugerida por IA (sin revisar)",
    "ia_confirmada": "IA confirmada por funcionario",
    "corregida": "Corregida por funcionario",
    "manual": "Clasificación manual",
}

_COLUMNAS_CASO = """
    creado_en TEXT NOT NULL,
    actualizado_en TEXT,
    -- evidencia aportada por el funcionario
    texto TEXT NOT NULL,
    plataforma TEXT,
    url TEXT,
    captura_path TEXT,
    relevancia TEXT,
    funcionario_nombre TEXT,
    funcionario_tg_id BIGINT,
    -- clasificación (preliminar y siempre revisable)
    resumen TEXT,
    categoria TEXT,
    nivel TEXT,
    tema TEXT,
    ubicacion TEXT,
    area TEXT,
    accion_recomendada TEXT,
    justificacion TEXT,
    clasificacion_origen TEXT,
    -- seguimiento
    estado TEXT NOT NULL DEFAULT 'nuevo',
    -- decisión del comité (qué se resolvió hacer con el caso)
    decision TEXT,
    decision_autor TEXT,
    decision_fecha TEXT
"""

# Columnas agregadas después del primer despliegue: se crean por migración en bases existentes.
_COLUMNAS_NUEVAS = {
    "decision": "TEXT",
    "decision_autor": "TEXT",
    "decision_fecha": "TEXT",
    "resumen": "TEXT",
}

_SCHEMA_SQLITE = [
    f"CREATE TABLE IF NOT EXISTS casos (id INTEGER PRIMARY KEY AUTOINCREMENT, {_COLUMNAS_CASO})",
    """CREATE TABLE IF NOT EXISTS comentarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caso_id INTEGER NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
        autor TEXT NOT NULL,
        texto TEXT NOT NULL,
        creado_en TEXT NOT NULL
    )""",
]

_SCHEMA_PG = [
    f"CREATE TABLE IF NOT EXISTS casos (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, {_COLUMNAS_CASO})",
    """CREATE TABLE IF NOT EXISTS comentarios (
        id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        caso_id BIGINT NOT NULL REFERENCES casos(id) ON DELETE CASCADE,
        autor TEXT NOT NULL,
        texto TEXT NOT NULL,
        creado_en TEXT NOT NULL
    )""",
]


def _q(sql: str) -> str:
    """Las consultas se escriben con '?'; Postgres usa '%s'."""
    return sql.replace("?", "%s") if _PG else sql


@contextmanager
def get_conn():
    if _PG:
        with psycopg.connect(config.DATABASE_URL, row_factory=dict_row) as conn:
            yield conn
    else:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()


def backend() -> str:
    return "Postgres (Supabase)" if _PG else f"SQLite ({config.DB_PATH})"


def _migrar(conn) -> None:
    if _PG:
        for columna, tipo in _COLUMNAS_NUEVAS.items():
            conn.execute(f"ALTER TABLE casos ADD COLUMN IF NOT EXISTS {columna} {tipo}")
    else:
        existentes = {fila["name"] for fila in conn.execute("PRAGMA table_info(casos)").fetchall()}
        for columna, tipo in _COLUMNAS_NUEVAS.items():
            if columna not in existentes:
                conn.execute(f"ALTER TABLE casos ADD COLUMN {columna} {tipo}")


def init_db() -> None:
    esquema = _SCHEMA_PG if _PG else _SCHEMA_SQLITE
    with get_conn() as conn:
        for sentencia in esquema:
            conn.execute(sentencia)
        _migrar(conn)
    log.info("Base de datos lista: %s", backend())


def crear_caso(
    texto: str,
    plataforma: Optional[str] = None,
    url: Optional[str] = None,
    captura_path: Optional[str] = None,
    relevancia: Optional[str] = None,
    funcionario_nombre: Optional[str] = None,
    funcionario_tg_id: Optional[int] = None,
) -> int:
    sql = """INSERT INTO casos (creado_en, texto, plataforma, url, captura_path, relevancia,
                                funcionario_nombre, funcionario_tg_id)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
    params = (ahora(), texto, plataforma, url, captura_path, relevancia,
              funcionario_nombre, funcionario_tg_id)
    with get_conn() as conn:
        if _PG:
            fila = conn.execute(_q(sql + " RETURNING id"), params).fetchone()
            return fila["id"]
        return conn.execute(sql, params).lastrowid


def guardar_clasificacion(caso_id: int, clasificacion: dict, origen: str) -> None:
    with get_conn() as conn:
        conn.execute(
            _q(
                """UPDATE casos SET categoria = ?, nivel = ?, tema = ?, ubicacion = ?, area = ?,
                                    accion_recomendada = ?, justificacion = ?, resumen = ?,
                                    clasificacion_origen = ?, actualizado_en = ?
                   WHERE id = ?"""
            ),
            (
                clasificacion.get("categoria"),
                clasificacion.get("nivel"),
                clasificacion.get("tema"),
                clasificacion.get("ubicacion"),
                clasificacion.get("area"),
                clasificacion.get("accion_recomendada"),
                clasificacion.get("justificacion"),
                clasificacion.get("resumen"),
                origen,
                ahora(),
                caso_id,
            ),
        )


def marcar_origen(caso_id: int, origen: str) -> None:
    with get_conn() as conn:
        conn.execute(
            _q("UPDATE casos SET clasificacion_origen = ?, actualizado_en = ? WHERE id = ?"),
            (origen, ahora(), caso_id),
        )


def obtener_caso(caso_id: int):
    with get_conn() as conn:
        return conn.execute(_q("SELECT * FROM casos WHERE id = ?"), (caso_id,)).fetchone()


def listar_casos(
    categoria: Optional[str] = None,
    nivel: Optional[str] = None,
    estado: Optional[str] = None,
    q: Optional[str] = None,
    limite: int = 200,
) -> list:
    condiciones, params = [], []
    if categoria:
        condiciones.append("categoria = ?")
        params.append(categoria)
    if nivel:
        condiciones.append("nivel = ?")
        params.append(nivel)
    if estado:
        condiciones.append("estado = ?")
        params.append(estado)
    if q:
        like = "ILIKE" if _PG else "LIKE"
        patron = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        condiciones.append(
            f"(texto {like} ? ESCAPE '\\' OR tema {like} ? ESCAPE '\\' "
            f"OR ubicacion {like} ? ESCAPE '\\' OR relevancia {like} ? ESCAPE '\\')"
        )
        params.extend([patron] * 4)
    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    with get_conn() as conn:
        return conn.execute(
            _q(f"SELECT * FROM casos {where} ORDER BY id DESC LIMIT ?"), (*params, limite)
        ).fetchall()


def ultimos_casos(limite: int = 5) -> list:
    with get_conn() as conn:
        return conn.execute(
            _q("SELECT * FROM casos ORDER BY id DESC LIMIT ?"), (limite,)
        ).fetchall()


def contar() -> dict:
    with get_conn() as conn:
        total = list(conn.execute("SELECT COUNT(*) AS n FROM casos").fetchone())[0]
        por_nivel = {
            fila["nivel"]: fila["n"]
            for fila in conn.execute(
                "SELECT nivel, COUNT(*) AS n FROM casos WHERE nivel IS NOT NULL GROUP BY nivel"
            ).fetchall()
        }
        por_estado = {
            fila["estado"]: fila["n"]
            for fila in conn.execute(
                "SELECT estado, COUNT(*) AS n FROM casos GROUP BY estado"
            ).fetchall()
        }
    return {"total": total, "por_nivel": por_nivel, "por_estado": por_estado}


def cambiar_estado(caso_id: int, estado: str) -> None:
    if estado not in ESTADOS:
        raise ValueError(f"Estado inválido: {estado}")
    with get_conn() as conn:
        conn.execute(
            _q("UPDATE casos SET estado = ?, actualizado_en = ? WHERE id = ?"),
            (estado, ahora(), caso_id),
        )


def eliminar_caso(caso_id: int) -> None:
    """Descarta un caso cargado a medias (lo usa /cancelar del bot antes de confirmar)."""
    with get_conn() as conn:
        conn.execute(_q("DELETE FROM comentarios WHERE caso_id = ?"), (caso_id,))
        conn.execute(_q("DELETE FROM casos WHERE id = ?"), (caso_id,))


def guardar_decision(caso_id: int, decision: str, autor: str) -> None:
    with get_conn() as conn:
        conn.execute(
            _q(
                """UPDATE casos SET decision = ?, decision_autor = ?, decision_fecha = ?,
                                    actualizado_en = ? WHERE id = ?"""
            ),
            (decision, autor, ahora(), ahora(), caso_id),
        )


def agregar_comentario(caso_id: int, autor: str, texto: str) -> None:
    with get_conn() as conn:
        conn.execute(
            _q("INSERT INTO comentarios (caso_id, autor, texto, creado_en) VALUES (?, ?, ?, ?)"),
            (caso_id, autor, texto, ahora()),
        )


def comentarios_de(caso_id: int) -> list:
    with get_conn() as conn:
        return conn.execute(
            _q("SELECT * FROM comentarios WHERE caso_id = ? ORDER BY id ASC"), (caso_id,)
        ).fetchall()
