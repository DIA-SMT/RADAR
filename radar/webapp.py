"""Panel web de RADAR: lista de casos, ficha, seguimiento, debate y decisión.

Autenticación, en orden de preferencia:
1. Login con usuarios de Supabase Auth (si SUPABASE_URL y la clave están configuradas):
   página /login, sesión en cookie firmada. Los usuarios se crean en el dashboard de Supabase.
2. Contraseña única PANEL_PASSWORD (HTTP Basic), si no hay Supabase.
3. Sin nada configurado, el panel solo escucha en 127.0.0.1 (modo desarrollo).

En el mismo proceso arranca el bot de Telegram (si hay token configurado),
así todo corre con un solo comando: python main.py
"""
import base64
import hashlib
import hmac
import logging
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from urllib.parse import urlparse

import httpx
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import classifier, config, db, manual

log = logging.getLogger("radar.web")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    log.info("Base de datos en uso: %s", db.backend())
    tg_app = None
    if config.TELEGRAM_BOT_TOKEN:
        try:
            from . import bot

            tg_app = bot.build_application()
            await tg_app.initialize()
            await tg_app.start()
            # Solo mensajes nuevos y botones: los updates de mensajes editados no sirven al flujo.
            await tg_app.updater.start_polling(allowed_updates=["message", "callback_query"])
            log.info("Bot de Telegram iniciado (polling).")
            if not config.TELEGRAM_ALLOWED_IDS:
                log.warning(
                    "TELEGRAM_ALLOWED_IDS vacio: CUALQUIER usuario de Telegram puede usar el bot. "
                    "Definir los IDs habilitados en el .env antes del piloto."
                )
        except Exception as exc:
            log.error("No se pudo iniciar el bot de Telegram: %s", exc)
            tg_app = None
    else:
        log.warning("TELEGRAM_BOT_TOKEN vacio: el panel corre sin bot.")
    if not classifier.disponible():
        log.warning("Sin clave de OpenRouter: la clasificacion automatica queda apagada (circuito manual).")
    if login_supabase_activo():
        log.info("Login del panel: usuarios de Supabase Auth (%s).", config.SUPABASE_URL)
        if not config.SESSION_SECRET:
            log.warning("SESSION_SECRET vacia: las sesiones del panel se cierran en cada reinicio.")
    elif config.PANEL_PASSWORD:
        log.info("Login del panel: contrasena unica (HTTP Basic).")
    else:
        log.warning(
            "Panel sin autenticacion configurada (por eso solo escucha en 127.0.0.1). "
            "Configurar Supabase o PANEL_PASSWORD antes de exponerlo."
        )
    yield
    if tg_app:
        try:
            await tg_app.updater.stop()
            await tg_app.stop()
            await tg_app.shutdown()
        except Exception as exc:
            log.warning("Error al apagar el bot: %s", exc)


# docs_url/openapi_url apagados: la documentación automática de FastAPI no pasa por el login.
app = FastAPI(title="RADAR", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

# Solo logos institucionales: contenido público no sensible, por eso va sin autenticación
# (las capturas de evidencia, que sí son sensibles, se sirven autenticadas en /capturas).
if config.PUBLIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(config.PUBLIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["fecha"] = (
    lambda s: f"{s[8:10]}/{s[5:7]}/{s[0:4]} {s[11:16]}" if s and len(s) >= 16 else (s or "—")
)


def _url_segura(url):
    """Solo enlaces http(s) se renderizan clickeables (evita esquemas javascript: y similares)."""
    if not url:
        return None
    limpio = str(url).strip()
    return limpio if limpio.lower().startswith(("http://", "https://")) else None


templates.env.filters["url_segura"] = _url_segura

COLORES_NIVEL = {"N1": "#64748b", "N2": "#d97706", "N3": "#ea580c", "N4": "#dc2626"}
COLORES_CATEGORIA = {
    "Consulta": "#0561f5",
    "Reclamo": "#c2410c",
    "Crítica": "#7c3aed",
    "Información incorrecta": "#db2777",
    "Tendencia": "#0d9488",
    "Posible acción coordinada": "#b91c1c",
}
COLORES_ESTADO = {
    "nuevo": "#0561f5",
    "derivado": "#7c3aed",
    "en_curso": "#d97706",
    "resuelto": "#16a34a",
    "cerrado": "#64748b",
    "en_observacion": "#0891b2",
}

_security = HTTPBasic(auto_error=False)

_COOKIE_SESION = "radar_sesion"
_DURACION_SESION = 7 * 24 * 3600  # una semana

# Si el login con Supabase está activo pero falta SESSION_SECRET, se genera uno efímero:
# funciona, pero las sesiones se cierran con cada reinicio (mejor fijarlo en el .env).
_SECRETO = config.SESSION_SECRET or secrets.token_urlsafe(32)


def login_supabase_activo() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_ANON_KEY)


def _firmar_sesion(email: str) -> str:
    vence = str(int(time.time()) + _DURACION_SESION)
    datos = f"{email}|{vence}"
    firma = hmac.new(_SECRETO.encode(), datos.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{datos}|{firma}".encode()).decode()


def _leer_sesion(token: str) -> Optional[str]:
    try:
        datos = base64.urlsafe_b64decode(token.encode()).decode()
        email, vence, firma = datos.rsplit("|", 2)
        esperada = hmac.new(_SECRETO.encode(), f"{email}|{vence}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma, esperada) or int(vence) < time.time():
            return None
        return email
    except Exception:
        return None


def usuario_actual(
    request: Request,
    credentials: Optional[HTTPBasicCredentials] = Depends(_security),
) -> str:
    """Devuelve el email del usuario logueado (o un marcador en los modos sin login)."""
    token = request.cookies.get(_COOKIE_SESION)
    if token:
        email = _leer_sesion(token)
        if email:
            return email
    if login_supabase_activo():
        # Sin sesión: al login. El 303 con Location redirige también los POST vencidos.
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    if config.PANEL_PASSWORD:
        if credentials is not None and secrets.compare_digest(
            credentials.password.encode("utf-8"), config.PANEL_PASSWORD.encode("utf-8")
        ):
            return "panel"
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": 'Basic realm="RADAR"'})
    return "local"


def verificar_origen(request: Request) -> None:
    """Corta form-POSTs cross-site (CSRF): si el navegador declara un Origin/Referer ajeno, 403."""
    origen = request.headers.get("origin") or request.headers.get("referer")
    if not origen:
        return
    host_origen = urlparse(origen).netloc
    if host_origen and host_origen != request.headers.get("host", ""):
        raise HTTPException(status_code=403, detail="Origen no permitido")


def _contexto_base() -> dict:
    return {
        "ESTADOS": db.ESTADOS,
        "ORIGENES": db.ORIGENES,
        "CATEGORIAS": manual.CATEGORIAS,
        "NIVELES": manual.NIVELES,
        "QUE_NO_HACER": manual.QUE_NO_HACER,
        "COLORES_NIVEL": COLORES_NIVEL,
        "COLORES_CATEGORIA": COLORES_CATEGORIA,
        "COLORES_ESTADO": COLORES_ESTADO,
    }


def _nombre_de(usuario: str) -> str:
    """Nombre corto para prellenar autores: la parte local del email."""
    return usuario.split("@")[0] if "@" in usuario else ""


@app.get("/login")
def login_form(request: Request):
    if not login_supabase_activo() or _leer_sesion(request.cookies.get(_COOKIE_SESION, "")):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    _origen: None = Depends(verificar_origen),
):
    if not login_supabase_activo():
        return RedirectResponse("/", status_code=303)
    error = "Email o contraseña incorrectos."
    try:
        respuesta = httpx.post(
            f"{config.SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": config.SUPABASE_ANON_KEY},
            json={"email": email.strip(), "password": password},
            timeout=15,
        )
        if respuesta.status_code == 200:
            email_ok = (respuesta.json().get("user") or {}).get("email") or email.strip()
            destino = RedirectResponse("/", status_code=303)
            destino.set_cookie(
                _COOKIE_SESION,
                _firmar_sesion(email_ok),
                max_age=_DURACION_SESION,
                httponly=True,
                samesite="lax",
                secure=request.headers.get("x-forwarded-proto") == "https",
            )
            return destino
    except Exception as exc:
        log.warning("No se pudo consultar Supabase Auth: %s", exc)
        error = "No se pudo verificar con el servidor de usuarios. Probá de nuevo en un momento."
    return templates.TemplateResponse(
        request, "login.html", {"request": request, "error": error}, status_code=401
    )


@app.get("/logout")
def logout():
    destino = RedirectResponse("/login" if login_supabase_activo() else "/", status_code=303)
    destino.delete_cookie(_COOKIE_SESION)
    return destino


@app.get("/")
def index(
    request: Request,
    categoria: str = "",
    nivel: str = "",
    estado: str = "",
    q: str = "",
    usuario: str = Depends(usuario_actual),
):
    casos = db.listar_casos(
        categoria=categoria or None, nivel=nivel or None, estado=estado or None, q=q or None
    )
    contexto = _contexto_base() | {
        "request": request,
        "casos": casos,
        "conteo": db.contar(),
        "filtros": {"categoria": categoria, "nivel": nivel, "estado": estado, "q": q},
        "hay_filtros": bool(categoria or nivel or estado or q),
        "usuario": usuario,
    }
    return templates.TemplateResponse(request, "index.html", contexto)


@app.get("/caso/{caso_id}")
def detalle(request: Request, caso_id: int, usuario: str = Depends(usuario_actual)):
    caso = db.obtener_caso(caso_id)
    if caso is None:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    contexto = _contexto_base() | {
        "request": request,
        "caso": caso,
        "comentarios": db.comentarios_de(caso_id),
        "manual_cat": manual.CATEGORIAS.get(caso["categoria"]),
        "manual_niv": manual.NIVELES.get(caso["nivel"]),
        "usuario": usuario,
        "autor_defecto": _nombre_de(usuario),
    }
    return templates.TemplateResponse(request, "caso.html", contexto)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    icono = config.PUBLIC_DIR / "muni.png"
    if not icono.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(icono, media_type="image/png")


@app.get("/capturas/{nombre}")
def captura(nombre: str, _usuario: str = Depends(usuario_actual)):
    """Sirve las capturas con la misma autenticación que el resto del panel."""
    if "/" in nombre or "\\" in nombre or ".." in nombre:
        raise HTTPException(status_code=404)
    ruta = config.CAPTURAS_DIR / nombre
    if not ruta.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(ruta)


@app.post("/caso/{caso_id}/estado")
def cambiar_estado(
    caso_id: int,
    estado: str = Form(...),
    _usuario: str = Depends(usuario_actual),
    _origen: None = Depends(verificar_origen),
):
    if db.obtener_caso(caso_id) is None:
        raise HTTPException(status_code=404)
    if estado not in db.ESTADOS:
        raise HTTPException(status_code=400, detail="Estado inválido")
    db.cambiar_estado(caso_id, estado)
    return RedirectResponse(url=f"/caso/{caso_id}", status_code=303)


@app.post("/caso/{caso_id}/clasificacion")
def corregir_clasificacion(
    caso_id: int,
    categoria: str = Form(...),
    nivel: str = Form(...),
    _usuario: str = Depends(usuario_actual),
    _origen: None = Depends(verificar_origen),
):
    caso = db.obtener_caso(caso_id)
    if caso is None:
        raise HTTPException(status_code=404)
    if categoria not in manual.CATEGORIAS or nivel not in manual.NIVELES:
        raise HTTPException(status_code=400, detail="Clasificación inválida")
    misma_categoria = caso["categoria"] == categoria
    db.guardar_clasificacion(
        caso_id,
        {
            "resumen": caso["resumen"],
            "categoria": categoria,
            "nivel": nivel,
            "tema": caso["tema"],
            "ubicacion": caso["ubicacion"],
            "area": caso["area"] if misma_categoria else manual.CATEGORIAS[categoria]["responsable"],
            "accion_recomendada": caso["accion_recomendada"]
            if misma_categoria
            else manual.CATEGORIAS[categoria]["procedimiento"],
            "justificacion": caso["justificacion"],
        },
        origen="corregida",
    )
    return RedirectResponse(url=f"/caso/{caso_id}", status_code=303)


@app.post("/caso/{caso_id}/decision")
def decidir(
    caso_id: int,
    decision: str = Form(...),
    autor: str = Form(""),
    usuario: str = Depends(usuario_actual),
    _origen: None = Depends(verificar_origen),
):
    """Asienta (o actualiza) la decisión del comité: qué se resolvió hacer con el caso."""
    if db.obtener_caso(caso_id) is None:
        raise HTTPException(status_code=404)
    decision = decision.strip()
    if decision:
        db.guardar_decision(caso_id, decision, autor.strip() or _nombre_de(usuario) or "Comité")
    return RedirectResponse(url=f"/caso/{caso_id}", status_code=303)


@app.post("/caso/{caso_id}/comentario")
def comentar(
    caso_id: int,
    autor: str = Form(""),
    texto: str = Form(...),
    usuario: str = Depends(usuario_actual),
    _origen: None = Depends(verificar_origen),
):
    if db.obtener_caso(caso_id) is None:
        raise HTTPException(status_code=404)
    texto = texto.strip()
    if texto:
        db.agregar_comentario(caso_id, autor.strip() or _nombre_de(usuario) or "Comité", texto)
    return RedirectResponse(url=f"/caso/{caso_id}", status_code=303)
