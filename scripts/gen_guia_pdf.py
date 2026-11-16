# -*- coding: utf-8 -*-
"""Genera la guía rápida de RADAR para el comité (docs/Guia-RADAR-comite.pdf).

Toma categorías, urgencias y reglas directamente de radar/manual.py, así la guía
nunca queda desactualizada. Correr con el python del venv:
    .venv\\Scripts\\python scripts\\gen_guia_pdf.py
"""
import glob
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from radar import manual

SALIDA = str(BASE / "docs" / "Guia-RADAR-comite.pdf")
LOGO = str(BASE / "public" / "muni.png")

AZUL = colors.HexColor("#0066ff")
AMARILLO = colors.HexColor("#f4dc00")
TINTA = colors.HexColor("#22303f")
GRIS = colors.HexColor("#5b6b7d")
BORDE = colors.HexColor("#dce6f1")
FONDO_SUAVE = colors.HexColor("#f0f5fb")
NIVEL_COLORES = {"N1": "#64748b", "N2": "#d97706", "N3": "#ea580c", "N4": "#dc2626"}

# Poppins si está instalada en Windows; si no, Helvetica.
FUENTE, FUENTE_B = "Helvetica", "Helvetica-Bold"
regulares = glob.glob(r"C:\Windows\Fonts\Poppins-Regular.ttf") + glob.glob(
    r"C:\Users\*\AppData\Local\Microsoft\Windows\Fonts\Poppins-Regular.ttf"
)
negritas = glob.glob(r"C:\Windows\Fonts\Poppins-SemiBold.ttf") + glob.glob(
    r"C:\Users\*\AppData\Local\Microsoft\Windows\Fonts\Poppins-SemiBold.ttf"
)
if regulares and negritas:
    pdfmetrics.registerFont(TTFont("Poppins", regulares[0]))
    pdfmetrics.registerFont(TTFont("Poppins-B", negritas[0]))
    FUENTE, FUENTE_B = "Poppins", "Poppins-B"

est_titulo = ParagraphStyle("titulo", fontName=FUENTE_B, fontSize=24, textColor=TINTA, leading=28)
est_bajada = ParagraphStyle("bajada", fontName=FUENTE, fontSize=10.5, textColor=GRIS, leading=15)
est_h2 = ParagraphStyle("h2", fontName=FUENTE_B, fontSize=13, textColor=AZUL, leading=17, spaceBefore=14, spaceAfter=4)
est_cuerpo = ParagraphStyle("cuerpo", fontName=FUENTE, fontSize=10, textColor=TINTA, leading=15)
est_paso = ParagraphStyle("paso", parent=est_cuerpo, leftIndent=16, spaceAfter=3)
est_celda = ParagraphStyle("celda", fontName=FUENTE, fontSize=9, textColor=TINTA, leading=12.5)
est_celda_b = ParagraphStyle("celdab", fontName=FUENTE_B, fontSize=9, textColor=TINTA, leading=12.5)
est_pie = ParagraphStyle("pie", fontName=FUENTE, fontSize=8, textColor=GRIS, leading=11)

ESTILO_TABLA = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), FONDO_SUAVE),
    ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
    ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
])


def regla_amarilla():
    return HRFlowable(width="100%", thickness=2.5, color=AMARILLO, spaceBefore=2, spaceAfter=10)


historia = []

# ── Encabezado ──────────────────────────────────────────────────────
encabezado = Table(
    [[Image(LOGO, width=17 * mm, height=17 * mm),
      [Paragraph('<font color="#0066ff">RADAR</font> · Escucha activa del vecino', est_titulo),
       Paragraph("Guía rápida para el Comité — Secretaría General · S. M. de Tucumán", est_bajada)]]],
    colWidths=[22 * mm, None],
)
encabezado.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 0)]))
historia.append(encabezado)
historia.append(Spacer(1, 6))
historia.append(regla_amarilla())

historia.append(Paragraph(
    "RADAR registra lo que los vecinos dicen en redes sociales sobre la ciudad, lo analiza con "
    "ayuda de inteligencia artificial siguiendo el Manual de Actuación, y le da al comité un solo "
    "lugar para debatir cada caso y dejar asentado qué se decidió. <b>La tecnología analiza y "
    "propone; la decisión es siempre de una persona.</b> Nada se publica ni se responde "
    "automáticamente.", est_cuerpo))
historia.append(Spacer(1, 8))

# ── Accesos ─────────────────────────────────────────────────────────
acc = Table(
    [
        [Paragraph("EL BOT — para cargar lo que ves", ParagraphStyle("a", parent=est_celda_b, textColor=AZUL, fontSize=10)),
         Paragraph("EL PANEL — para debatir y decidir", ParagraphStyle("b", parent=est_celda_b, textColor=AZUL, fontSize=10))],
        [Paragraph("En Telegram: <b>t.me/Radarmuni_bot</b><br/>Mandale una captura, un link o el texto "
                   "de lo que viste en redes. Te hace dos o tres preguntas y listo.", est_celda),
         Paragraph("En el navegador: <b>radar.195-35-42-168.sslip.io</b><br/>Se entra con email y "
                   "contraseña. Las credenciales las entrega la Dirección de IA.", est_celda)],
    ],
    colWidths=["50%", "50%"],
)
acc.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), FONDO_SUAVE),
    ("BOX", (0, 0), (0, -1), 0.75, BORDE), ("BOX", (1, 0), (1, -1), 0.75, BORDE),
    ("TOPPADDING", (0, 0), (-1, 0), 8), ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
    ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
]))
historia.append(acc)

# ── Cómo cargar un caso ─────────────────────────────────────────────
historia.append(Paragraph("Cargar un caso desde Telegram (dos minutos)", est_h2))
pasos = [
    "<b>1.</b> Mandale al bot lo que viste: una captura de pantalla, un link o el texto del comentario.",
    "<b>2.</b> Contestá lo que te pregunte: de qué plataforma salió, si hay link, y el contexto "
    "(qué detectaste, de qué están hablando, si se repite).",
    "<b>3.</b> El sistema analiza y te muestra un <b>resumen con qué hay que hacer</b>: la medida "
    "recomendada, la urgencia, el área competente y qué información le falta al caso.",
    "<b>4.</b> Vos decidís: <b>Subir al panel</b> (queda registrado), <b>Agregar info</b> (si pidió "
    "más datos), <b>Corregir</b> (elegís vos el tipo y la urgencia) o <b>Descartar</b> (no queda nada).",
]
for paso in pasos:
    historia.append(Paragraph(paso, est_paso))
historia.append(Spacer(1, 4))
historia.append(Paragraph(
    "Nada se sube al panel sin tu confirmación. Comandos útiles: <b>/casos</b> muestra los últimos "
    "casos, <b>/cancelar</b> descarta la carga en curso, <b>/start</b> repite la ayuda.", est_cuerpo))

# ── Categorías ──────────────────────────────────────────────────────
historia.append(Paragraph("Los seis tipos de situación del Manual de Actuación", est_h2))
filas = [[Paragraph("Tipo", est_celda_b), Paragraph("Qué es", est_celda_b), Paragraph("Qué se hace", est_celda_b)]]
for nombre, cat in manual.CATEGORIAS.items():
    filas.append([Paragraph(f"<b>{nombre}</b>", est_celda),
                  Paragraph(cat["descripcion"], est_celda),
                  Paragraph(cat["procedimiento"], est_celda)])
tabla_cat = Table(filas, colWidths=["22%", "34%", "44%"], repeatRows=1)
tabla_cat.setStyle(ESTILO_TABLA)
historia.append(tabla_cat)

historia.append(PageBreak())

# ── Urgencias ───────────────────────────────────────────────────────
historia.append(Paragraph("Qué tan urgente puede ser un caso", est_h2))
historia.append(Paragraph("El tipo dice qué es; la urgencia dice cuánto importa y qué medidas dispara.", est_cuerpo))
historia.append(Spacer(1, 4))
filas = [[Paragraph("Urgencia", est_celda_b), Paragraph("Cuándo aplica", est_celda_b), Paragraph("Qué medidas dispara", est_celda_b)]]
for codigo, niv in manual.NIVELES.items():
    color = NIVEL_COLORES[codigo]
    filas.append([
        Paragraph(f'<font color="{color}"><b>{niv["urgencia"]}</b></font>', est_celda),
        Paragraph(niv["descripcion"], est_celda),
        Paragraph(f'{niv["escalamiento"]} <font color="#5b6b7d">({niv["plazo"]})</font>', est_celda),
    ])
tabla_niv = Table(filas, colWidths=["20%", "36%", "44%"], repeatRows=1)
tabla_niv.setStyle(ESTILO_TABLA)
historia.append(tabla_niv)
historia.append(Paragraph(
    "Los casos <b>Urgente</b> y <b>Crítico</b> convocan al Comité de Respuesta: son los que exigen "
    "una posición institucional coordinada.", est_cuerpo))

# ── El panel ────────────────────────────────────────────────────────
historia.append(Paragraph("En el panel, el comité puede", est_h2))
panel_items = [
    "<b>Ver todos los casos</b> y filtrarlos por tipo, urgencia, estado o texto.",
    "<b>Abrir la ficha</b> de cada caso: la evidencia original, el resumen, qué hay que hacer y lo que dice el Manual de Actuación para esa situación.",
    "<b>Debatir</b>: cada miembro deja su aporte con su nombre en el hilo del caso.",
    "<b>Asentar la decisión</b>: qué se resolvió hacer, quién lo decidió y cuándo. También cuando la decisión es <i>no</i> actuar: eso también se registra.",
    "<b>Hacer seguimiento</b>: cambiar el estado (nuevo, derivado, en curso, resuelto, cerrado, en observación) hasta cerrar el circuito.",
    "<b>Corregir el análisis</b> si el sistema propuso mal: la última palabra es siempre humana.",
]
for item in panel_items:
    historia.append(Paragraph("•  " + item, est_paso))

# ── Reglas de oro ───────────────────────────────────────────────────
historia.append(Paragraph("Las cuatro reglas de oro", est_h2))
for regla in manual.QUE_NO_HACER:
    historia.append(Paragraph("•  " + regla, est_paso))
historia.append(Spacer(1, 10))
historia.append(regla_amarilla())
historia.append(Paragraph(
    "Dudas, credenciales de acceso o propuestas de mejora: Dirección de IA, Secretaría General. "
    "Esta guía acompaña al Manual de Actuación vigente; ante diferencia, vale el manual.", est_pie))

doc = SimpleDocTemplate(
    SALIDA, pagesize=A4,
    leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    title="RADAR — Guía rápida para el comité", author="Dirección de IA — S. M. de Tucumán",
)
doc.build(historia)
print("PDF generado:", SALIDA, "| fuente:", FUENTE)
