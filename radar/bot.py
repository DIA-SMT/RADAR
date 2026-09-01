"""Bot de Telegram: la puerta de entrada de la evidencia.

Flujo de carga:
  1. El funcionario manda una captura, un link o el texto de lo que vio.
  2. El bot completa lo que falte (qué dice, plataforma, link) y pide el contexto:
     qué detectó, de qué están hablando.
  3. El motor de análisis interpreta la intención, arma un RESUMEN y propone la
     clasificación según el manual.
  4. Recién cuando el funcionario da el OK, el caso se sube al panel.
     Si lo descarta, no queda nada guardado.

El bot trabaja por chat privado (la etapa de comité en grupo llega en la Etapa 3).
"""
import logging
import uuid
from urllib.parse import urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    TypeHandler,
    filters,
)

from . import classifier, config, db, manual

log = logging.getLogger("radar.bot")

TEXTO, PLATAFORMA, LINK, CONTEXTO, PROPUESTA, ELEGIR_CAT, ELEGIR_NIVEL, INFO_EXTRA = range(8)

# Mensajes que no son evidencia: no tiene sentido arrancar una carga con esto.
_SALUDOS = {
    "hola", "holaa", "buenas", "buen dia", "buenas tardes", "buenas noches",
    "gracias", "ok", "dale", "listo", "si", "no", "hey", "que tal", "como andas",
    "que onda", "probando", "test", "hola bot",
}

_CATEGORIAS = list(manual.CATEGORIAS.keys())

# Los mensajes editados no reinician ni avanzan flujos (update.message es None en esos updates).
_SIN_EDITAR = ~filters.UpdateType.EDITED
_PRIVADO = filters.ChatType.PRIVATE
_TEXTO_NUEVO = filters.TEXT & ~filters.COMMAND & _SIN_EDITAR
_FOTO_NUEVA = filters.PHOTO & _SIN_EDITAR

_DOMINIOS = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "fb.watch": "Facebook",
    "twitter.com": "X (Twitter)",
    "x.com": "X (Twitter)",
    "tiktok.com": "TikTok",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "whatsapp.com": "WhatsApp",
    "wa.me": "WhatsApp",
}


def _plataforma_de_url(url: str):
    try:
        dominio = (urlparse(url).netloc or "").lower().removeprefix("www.")
    except Exception:
        return None
    for conocido, nombre in _DOMINIOS.items():
        if dominio == conocido or dominio.endswith("." + conocido):
            return nombre
    return None


# ---------- teclados ----------

def _filas_de_a_dos(botones):
    return [botones[i : i + 2] for i in range(0, len(botones), 2)]


def _kb_plataformas():
    botones = [
        InlineKeyboardButton(p, callback_data=f"plat:{i}")
        for i, p in enumerate(manual.PLATAFORMAS)
    ]
    return InlineKeyboardMarkup(_filas_de_a_dos(botones))


def _kb_categorias():
    botones = [
        InlineKeyboardButton(c, callback_data=f"cat:{i}") for i, c in enumerate(_CATEGORIAS)
    ]
    filas = _filas_de_a_dos(botones)
    filas.append([InlineKeyboardButton("🗑 Descartar caso", callback_data="conf:desc")])
    return InlineKeyboardMarkup(filas)


def _kb_niveles():
    botones = [
        InlineKeyboardButton(f"{codigo} · {niv['nombre']}", callback_data=f"niv:{codigo}")
        for codigo, niv in manual.NIVELES.items()
    ]
    return InlineKeyboardMarkup(_filas_de_a_dos(botones))


def _kb_omitir(clave):
    return InlineKeyboardMarkup([[InlineKeyboardButton("Omitir ⏭", callback_data=f"skip:{clave}")]])


def _kb_propuesta(con_agregar: bool = False):
    filas = [[InlineKeyboardButton("✅ Subir al panel", callback_data="conf:si")]]
    if con_agregar:
        filas.append([InlineKeyboardButton("➕ Agregar info", callback_data="conf:mas")])
    filas.append(
        [
            InlineKeyboardButton("✏️ Corregir", callback_data="conf:no"),
            InlineKeyboardButton("🗑 Descartar", callback_data="conf:desc"),
        ]
    )
    return InlineKeyboardMarkup(filas)


# ---------- helpers ----------

def _autorizado(update: Update) -> bool:
    if not config.TELEGRAM_ALLOWED_IDS:
        return True
    usuario = update.effective_user
    return usuario is not None and usuario.id in config.TELEGRAM_ALLOWED_IDS


async def _rechazar(update: Update) -> int:
    usuario = update.effective_user
    await update.effective_message.reply_text(
        "No estás habilitado para usar RADAR.\n"
        f"Tu ID de Telegram es {usuario.id if usuario else 'desconocido'}: "
        "pasáselo al administrador para que te habilite."
    )
    return ConversationHandler.END


async def _ack(query) -> None:
    """answer() falla si el callback quedó viejo; eso no debe abortar el handler."""
    try:
        await query.answer()
    except Exception:
        pass


async def _quitar_teclado(update: Update) -> None:
    """Saca los botones del mensaje ya respondido para que no queden activos."""
    if update.callback_query and update.callback_query.message:
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass


def _descartar(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Limpia la carga en curso; si había una captura descargada, borra el archivo."""
    caso = context.user_data.get("caso") or {}
    captura = caso.get("captura_path")
    if captura:
        try:
            (config.CAPTURAS_DIR / captura).unlink(missing_ok=True)
        except Exception:
            pass
    context.user_data.clear()


def _guardar_caso(context: ContextTypes.DEFAULT_TYPE, cls: dict, origen: str) -> int:
    """Recién acá el caso entra a la base (y por lo tanto al panel)."""
    caso = context.user_data["caso"]
    caso_id = db.crear_caso(
        texto=caso.get("texto") or "(sin texto)",
        plataforma=caso.get("plataforma"),
        url=caso.get("url"),
        captura_path=caso.get("captura_path"),
        relevancia=caso.get("relevancia"),
        funcionario_nombre=caso.get("funcionario_nombre"),
        funcionario_tg_id=caso.get("funcionario_tg_id"),
    )
    db.guardar_clasificacion(caso_id, cls, origen=origen)
    return caso_id


def _texto_propuesta(cls: dict) -> str:
    nivel = manual.NIVELES[cls["nivel"]]
    lineas = []
    if cls.get("resumen"):
        lineas.extend(["📝 Resumen:", cls["resumen"], ""])
    lineas.extend(
        [
            "Clasificación propuesta (la decidís vos):",
            f"• Categoría: {cls['categoria']}",
            f"• Nivel: {cls['nivel']} — {nivel['nombre']}",
        ]
    )
    if cls.get("tema"):
        lineas.append(f"• Tema: {cls['tema']}")
    if cls.get("ubicacion"):
        lineas.append(f"• Ubicación (hipótesis): {cls['ubicacion']}")
    lineas.append(f"• Área sugerida: {cls['area']}")
    lineas.append(f"• Acción recomendada: {cls['accion_recomendada']}")
    if cls.get("justificacion"):
        lineas.append(f"• Por qué: {cls['justificacion']}")
    if cls.get("confianza") == "baja":
        lineas.append("")
        lineas.append("⚠️ El análisis tiene poca información para trabajar: revisalo bien antes de subirlo.")
    if cls.get("faltantes"):
        lineas.append("")
        lineas.append("Para afinar el análisis me ayudaría saber:")
        for pedido in cls["faltantes"]:
            lineas.append(f"– {pedido}")
        lineas.append("(tocá ➕ Agregar info y contámelo)")
    lineas.append("")
    lineas.append("¿Lo subo al panel?")
    return "\n".join(lineas)


def _texto_final(caso_id: int, cls: dict) -> str:
    cat = manual.CATEGORIAS[cls["categoria"]]
    niv = manual.NIVELES[cls["nivel"]]
    return "\n".join(
        [
            f"📋 Caso #{caso_id} subido al panel.",
            "",
            f"Categoría: {cls['categoria']} · Nivel: {cls['nivel']} — {niv['nombre']} · Área: {cls['area']}",
            f"Según el manual: {cat['procedimiento']} (Responsable: {cat['responsable']})",
            f"Escalamiento {cls['nivel']}: {niv['escalamiento']} Plazo: {niv['plazo']}.",
            "",
            f"👉 Seguimiento y debate: {config.PANEL_BASE_URL}/caso/{caso_id}",
        ]
    )


# ---------- comandos ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    usuario = update.effective_user
    if not _autorizado(update):
        await _rechazar(update)
        return
    await update.message.reply_text(
        "📡 RADAR — Escucha activa del vecino\n\n"
        "Mandame lo que viste en redes: una captura de pantalla, un link o el texto "
        "del comentario. Te pido el contexto, lo analizo y te muestro un resumen con "
        "la clasificación. Nada se sube al panel hasta que vos des el OK.\n\n"
        "Comandos:\n"
        "/casos — últimos casos cargados\n"
        "/cancelar — descartar la carga en curso\n\n"
        f"Tu ID de Telegram es {usuario.id}."
    )


async def cmd_casos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _autorizado(update):
        await _rechazar(update)
        return
    casos = db.ultimos_casos(5)
    if not casos:
        await update.message.reply_text("Todavía no hay casos cargados.")
        return
    lineas = ["Últimos casos:"]
    for c in casos:
        cat = c["categoria"] or "Sin clasificar"
        nivel = f" · {c['nivel']}" if c["nivel"] else ""
        estado = db.ESTADOS.get(c["estado"], c["estado"])
        resumen = (c["resumen"] or c["texto"] or "").replace("\n", " ")
        if len(resumen) > 60:
            resumen = resumen[:57] + "..."
        lineas.append(f"#{c['id']} [{cat}{nivel}] {estado} — {resumen}")
    lineas.append(f"\nPanel: {config.PANEL_BASE_URL}")
    await update.message.reply_text("\n".join(lineas))


async def cmd_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _descartar(context)
    await update.effective_message.reply_text(
        "Carga descartada: no se subió nada al panel. Cuando quieras, mandame otra evidencia."
    )
    return ConversationHandler.END


async def al_expirar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """La conversación superó el tiempo máximo sin terminar."""
    _descartar(context)
    try:
        await update.effective_message.reply_text(
            "La carga quedó abierta mucho tiempo y se descartó (no se subió nada al panel). "
            "Cuando quieras, mandame la evidencia de nuevo."
        )
    except Exception:
        pass


# ---------- flujo de carga ----------

def _caso_nuevo(update: Update) -> dict:
    usuario = update.effective_user
    return {
        "funcionario_nombre": usuario.full_name if usuario else None,
        "funcionario_tg_id": usuario.id if usuario else None,
    }


async def _avanzar(mensaje, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pregunta lo que falte, en orden: plataforma -> link -> contexto -> análisis."""
    caso = context.user_data["caso"]
    if not caso.get("plataforma"):
        await mensaje.reply_text("¿De qué plataforma salió?", reply_markup=_kb_plataformas())
        return PLATAFORMA
    if "url" not in caso:
        await mensaje.reply_text(
            "Pasame el link de la publicación (si no lo tenés, tocá Omitir):",
            reply_markup=_kb_omitir("link"),
        )
        return LINK
    await mensaje.reply_text(
        "Contame el contexto: ¿de qué están hablando? ¿Qué detectaste vos? "
        "(tema, lugar, si viene repitiéndose, qué te llamó la atención)",
        reply_markup=_kb_omitir("ctx"),
    )
    return CONTEXTO


async def recibir_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entrada por texto: puede ser el contenido de lo que vio, o directamente un link."""
    if not _autorizado(update):
        return await _rechazar(update)
    context.user_data.clear()
    caso = _caso_nuevo(update)
    contenido = update.message.text.strip()
    saludo = contenido.lower().strip(" !¡¿?.,\U0001f44b")
    if saludo in _SALUDOS or len(saludo) <= 3:
        await update.message.reply_text(
            "¡Hola! Para cargar un caso mandame la evidencia: una captura de pantalla, "
            "un link o el texto del comentario que viste en redes. (/start para ver la ayuda)"
        )
        return ConversationHandler.END
    if contenido.lower().startswith(("http://", "https://")):
        caso["url"] = contenido
        plataforma = _plataforma_de_url(contenido)
        if plataforma:
            caso["plataforma"] = plataforma
        context.user_data["caso"] = caso
        detectada = f" (detecté que es de {plataforma})" if plataforma else ""
        await update.message.reply_text(
            f"Link recibido{detectada}. Contame qué dice la publicación, "
            "o mandame una captura de pantalla:"
        )
        return TEXTO
    caso["texto"] = contenido
    context.user_data["caso"] = caso
    return await _avanzar(update.message, context)


async def recibir_foto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not _autorizado(update):
        return await _rechazar(update)
    context.user_data.clear()
    context.user_data["caso"] = _caso_nuevo(update)
    return await _guardar_foto(update, context, primera=True)


async def _descargar_captura(update: Update, caso: dict) -> None:
    foto = update.message.photo[-1]
    archivo = await foto.get_file()
    # Nombre único por carga (no por imagen): así descartar esta carga nunca borra
    # el archivo de un caso ya subido que usó la misma foto.
    nombre = f"{uuid.uuid4().hex}.jpg"
    await archivo.download_to_drive(custom_path=str(config.CAPTURAS_DIR / nombre))
    anterior = caso.get("captura_path")
    if anterior:  # reemplazó la captura a mitad de carga: la vieja no queda huérfana
        try:
            (config.CAPTURAS_DIR / anterior).unlink(missing_ok=True)
        except Exception:
            pass
    caso["captura_path"] = nombre


async def _guardar_foto(update: Update, context: ContextTypes.DEFAULT_TYPE, primera: bool) -> int:
    caso = context.user_data["caso"]
    await _descargar_captura(update, caso)
    if update.message.caption and not caso.get("texto"):
        caso["texto"] = update.message.caption.strip()
    if caso.get("texto"):
        return await _avanzar(update.message, context)
    await update.message.reply_text(
        "Captura guardada. Transcribí o resumí lo que dice (el sistema no puede leer la imagen):"
    )
    return TEXTO


async def recibir_texto_captura(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caso"]["texto"] = update.message.text.strip()
    return await _avanzar(update.message, context)


async def recibir_foto_en_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Estaba pendiente la descripción y mandó una captura: la sumamos al caso."""
    return await _guardar_foto(update, context, primera=False)


async def plataforma_elegida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await _ack(query)
    indice = int(query.data.split(":", 1)[1])
    context.user_data["caso"]["plataforma"] = manual.PLATAFORMAS[indice]
    await _quitar_teclado(update)
    return await _avanzar(query.message, context)


async def recibir_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caso"]["url"] = update.message.text.strip()
    return await _avanzar(update.message, context)


async def omitir_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await _ack(query)
    await _quitar_teclado(update)
    context.user_data["caso"]["url"] = None
    return await _avanzar(query.message, context)


async def recibir_contexto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["caso"]["relevancia"] = update.message.text.strip()
    return await _analizar(update.message, context)


async def omitir_contexto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await _ack(query)
    await _quitar_teclado(update)
    return await _analizar(query.message, context)


async def _analizar(mensaje, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Analiza la evidencia y muestra la propuesta. Nada se guarda hasta el OK."""
    caso = context.user_data["caso"]
    if classifier.disponible():
        await mensaje.reply_text("🔎 Analizando la evidencia...")
    cls = await classifier.clasificar(caso)

    if cls:
        context.user_data["cls"] = cls
        con_agregar = bool(cls.get("faltantes")) or cls.get("confianza") == "baja"
        await mensaje.reply_text(_texto_propuesta(cls), reply_markup=_kb_propuesta(con_agregar))
        return PROPUESTA

    context.user_data["cls"] = None
    await mensaje.reply_text(
        "El análisis automático no está disponible, clasificalo vos.\n¿Qué categoría es?",
        reply_markup=_kb_categorias(),
    )
    return ELEGIR_CAT


async def propuesta_respondida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await _ack(query)
    await _quitar_teclado(update)
    if query.data == "conf:mas":
        cls = context.user_data.get("cls") or {}
        pedidos = "\n".join(f"– {p}" for p in cls.get("faltantes", [])) or "– lo que le sume contexto al caso"
        await query.message.reply_text(
            "Dale, contame (texto o captura):\n" + pedidos
        )
        return INFO_EXTRA
    if query.data == "conf:si":
        cls = context.user_data.get("cls")
        if not cls or not context.user_data.get("caso"):
            # Doble tap o carga ya procesada: no insertar de nuevo.
            await query.message.reply_text("Esa carga ya se procesó. Mandame otra evidencia cuando quieras.")
            return ConversationHandler.END
        if cls.get("faltantes"):
            # Subió igual: lo pendiente queda visible para el comité en el análisis.
            pendiente = "Información pendiente: " + "; ".join(cls["faltantes"])
            base = (cls.get("justificacion") or "").rstrip(".")
            cls = {**cls, "justificacion": f"{base}. {pendiente}" if base else pendiente}
        caso_id = _guardar_caso(context, cls, origen="ia_confirmada")
        # Limpiar ANTES de responder: si la respuesta falla, el timeout no debe
        # borrar la captura de un caso que ya está en la base.
        context.user_data.clear()
        await query.message.reply_text(_texto_final(caso_id, cls))
        return ConversationHandler.END
    if query.data == "conf:desc":
        _descartar(context)
        await query.message.reply_text(
            "Caso descartado: no se subió nada al panel. Cuando quieras, mandame otra evidencia."
        )
        return ConversationHandler.END
    await query.message.reply_text("¿Qué categoría corresponde?", reply_markup=_kb_categorias())
    return ELEGIR_CAT


async def descartar_en_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Botón Descartar dentro de la clasificación manual."""
    query = update.callback_query
    await _ack(query)
    await _quitar_teclado(update)
    _descartar(context)
    await query.message.reply_text(
        "Caso descartado: no se subió nada al panel. Cuando quieras, mandame otra evidencia."
    )
    return ConversationHandler.END


async def categoria_elegida(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await _ack(query)
    await _quitar_teclado(update)
    indice = int(query.data.split(":", 1)[1])
    context.user_data["categoria_elegida"] = _CATEGORIAS[indice]
    await query.message.reply_text("¿Qué nivel de criticidad?", reply_markup=_kb_niveles())
    return ELEGIR_NIVEL


async def nivel_elegido(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await _ack(query)
    await _quitar_teclado(update)
    categoria = context.user_data.get("categoria_elegida")
    if not categoria or not context.user_data.get("caso"):
        await query.message.reply_text("Esa carga ya se procesó. Mandame otra evidencia cuando quieras.")
        return ConversationHandler.END
    nivel = query.data.split(":", 1)[1]
    previa = context.user_data.get("cls") or {}
    cls = {
        "resumen": previa.get("resumen"),
        "categoria": categoria,
        "nivel": nivel,
        "tema": previa.get("tema"),
        "ubicacion": previa.get("ubicacion"),
        "area": manual.CATEGORIAS[categoria]["responsable"],
        "accion_recomendada": manual.CATEGORIAS[categoria]["procedimiento"],
        "justificacion": previa.get("justificacion"),
    }
    origen = "corregida" if previa else "manual"
    caso_id = _guardar_caso(context, cls, origen=origen)
    context.user_data.clear()
    await query.message.reply_text(_texto_final(caso_id, cls))
    return ConversationHandler.END


async def recibir_info_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sumó contexto tras el pedido de 'faltantes': se re-analiza con la info nueva."""
    caso = context.user_data["caso"]
    caso["relevancia"] = f"{caso.get('relevancia') or ''}\n{update.message.text.strip()}".strip()
    return await _analizar(update.message, context)


async def foto_info_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    caso = context.user_data["caso"]
    await _descargar_captura(update, caso)
    if update.message.caption:
        caso["relevancia"] = f"{caso.get('relevancia') or ''}\n{update.message.caption.strip()}".strip()
    return await _analizar(update.message, context)


async def usar_botones(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """El funcionario escribió texto donde se esperaba un botón."""
    await update.message.reply_text("Usá los botones del mensaje de arriba 🙂 (o /cancelar).")


async def foto_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Llegó otra foto a mitad de una carga (p. ej. un álbum de varias capturas)."""
    await update.message.reply_text(
        "Por ahora es una captura por caso y ya estamos a mitad de una carga. "
        "Terminá las preguntas de este caso (o /cancelar) y después mandá esa captura como caso nuevo."
    )


async def manejar_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.error("Error atendiendo un update de Telegram", exc_info=context.error)


# ---------- armado de la aplicación ----------

def build_application() -> Application:
    application = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    descartar_btn = CallbackQueryHandler(descartar_en_manual, pattern=r"^conf:desc$")
    conversacion = ConversationHandler(
        entry_points=[
            MessageHandler(_TEXTO_NUEVO & _PRIVADO, recibir_texto),
            MessageHandler(_FOTO_NUEVA & _PRIVADO, recibir_foto),
        ],
        states={
            TEXTO: [
                MessageHandler(_TEXTO_NUEVO, recibir_texto_captura),
                MessageHandler(_FOTO_NUEVA, recibir_foto_en_texto),
            ],
            PLATAFORMA: [
                CallbackQueryHandler(plataforma_elegida, pattern=r"^plat:\d+$"),
                MessageHandler(_TEXTO_NUEVO, usar_botones),
                MessageHandler(_FOTO_NUEVA, foto_extra),
            ],
            LINK: [
                CallbackQueryHandler(omitir_link, pattern=r"^skip:link$"),
                MessageHandler(_TEXTO_NUEVO, recibir_link),
                MessageHandler(_FOTO_NUEVA, foto_extra),
            ],
            CONTEXTO: [
                CallbackQueryHandler(omitir_contexto, pattern=r"^skip:ctx$"),
                MessageHandler(_TEXTO_NUEVO, recibir_contexto),
                MessageHandler(_FOTO_NUEVA, foto_extra),
            ],
            PROPUESTA: [
                CallbackQueryHandler(propuesta_respondida, pattern=r"^conf:(si|no|desc|mas)$"),
                MessageHandler(_TEXTO_NUEVO, usar_botones),
                MessageHandler(_FOTO_NUEVA, foto_extra),
            ],
            INFO_EXTRA: [
                MessageHandler(_TEXTO_NUEVO, recibir_info_extra),
                MessageHandler(_FOTO_NUEVA, foto_info_extra),
            ],
            ELEGIR_CAT: [
                CallbackQueryHandler(categoria_elegida, pattern=r"^cat:\d+$"),
                descartar_btn,
                MessageHandler(_TEXTO_NUEVO, usar_botones),
                MessageHandler(_FOTO_NUEVA, foto_extra),
            ],
            ELEGIR_NIVEL: [
                CallbackQueryHandler(nivel_elegido, pattern=r"^niv:N[1-4]$"),
                descartar_btn,
                MessageHandler(_TEXTO_NUEVO, usar_botones),
                MessageHandler(_FOTO_NUEVA, foto_extra),
            ],
            ConversationHandler.TIMEOUT: [TypeHandler(Update, al_expirar)],
        },
        fallbacks=[CommandHandler("cancelar", cmd_cancelar)],
        conversation_timeout=1800,
    )

    comando_privado = _PRIVADO & _SIN_EDITAR
    application.add_handler(CommandHandler("start", cmd_start, filters=comando_privado))
    application.add_handler(CommandHandler("ayuda", cmd_start, filters=comando_privado))
    application.add_handler(CommandHandler("casos", cmd_casos, filters=comando_privado))
    application.add_handler(conversacion)
    application.add_handler(CommandHandler("cancelar", cmd_cancelar, filters=comando_privado))
    application.add_error_handler(manejar_error)
    return application
