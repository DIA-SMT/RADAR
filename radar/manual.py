"""Manual de Actuación v0.

Matriz de referencia tomada de la presentación institucional de RADAR
(Secretaría General, agosto 2026). Cuando el Manual de Actuación definitivo
se apruebe, este archivo se actualiza y el sistema pasa a consultar esas reglas.
El sistema consulta reglas, no las inventa.
"""

CATEGORIAS = {
    "Consulta": {
        "descripcion": "Una persona necesita información.",
        "procedimiento": "Responder con información cierta.",
        "responsable": "Atención ciudadana",
    },
    "Reclamo": {
        "descripcion": "Existe un problema concreto que requiere gestión.",
        "procedimiento": "Derivar al área competente y hacer seguimiento.",
        "responsable": "Área competente",
    },
    "Crítica": {
        "descripcion": "Opinión negativa; no siempre requiere respuesta.",
        "procedimiento": "Registrar y observar evolución. Responder solo si hay un dato concreto que aclarar.",
        "responsable": "Comunicación",
    },
    "Información incorrecta": {
        "descripcion": "Afirmación potencialmente errónea que circula.",
        "procedimiento": "Verificar internamente antes de responder. Sin verificación no hay aclaración.",
        "responsable": "Área técnica y Comunicación",
    },
    "Tendencia": {
        "descripcion": "Varias evidencias sobre un mismo tema revelan una necesidad creciente.",
        "procedimiento": "Agrupar evidencias y avisar preventivamente al área.",
        "responsable": "Escucha digital",
    },
    "Posible acción coordinada": {
        "descripcion": "Indicios de coordinación: textos repetidos, actividad simultánea, perfiles similares.",
        "procedimiento": "Preservar evidencia y escalar si corresponde. Siempre sujeto a validación humana.",
        "responsable": "Comité de Respuesta",
    },
}

NIVELES = {
    "N1": {
        "nombre": "Ordinario",
        "descripcion": "Alcance local, sin crecimiento.",
        "escalamiento": "Queda en el área competente, circuito habitual.",
        "plazo": "Circuito habitual",
    },
    "N2": {
        "nombre": "Atención",
        "descripcion": "El tema se repite o crece.",
        "escalamiento": "Aviso a la conducción del área.",
        "plazo": "Dentro de 24 horas",
    },
    "N3": {
        "nombre": "Alerta",
        "descripcion": "Impacto institucional o presencia en medios.",
        "escalamiento": "Escala al Comité de Respuesta.",
        "plazo": "Dentro de 4 horas",
    },
    "N4": {
        "nombre": "Crisis",
        "descripcion": "Riesgo reputacional, sanitario o de seguridad.",
        "escalamiento": "Convocatoria inmediata del Comité.",
        "plazo": "Sin demora",
    },
}

VARIABLES_CRITICIDAD = [
    ("Alcance", "Cuántas personas lo están viendo."),
    ("Velocidad", "Cuán rápido crece el volumen."),
    ("Impacto", "Qué consecuencia institucional puede tener."),
    ("Necesidad de intervención", "Si algo se agrava por no actuar."),
]

AREAS = [
    "Comunicación",
    "Atención ciudadana",
    "Obras Públicas",
    "Servicios Públicos",
    "Tecnología",
    "Jurídico",
]

PLATAFORMAS = ["Instagram", "Facebook", "WhatsApp", "X (Twitter)", "TikTok", "YouTube", "Otro"]

QUE_NO_HACER = [
    "No responder impulsivamente: la velocidad sin verificación agrava el problema.",
    "No confrontar usuarios: la institución no discute, informa.",
    "No confirmar lo no verificado: un dato sin validar compromete a toda la gestión.",
    "No prometer soluciones sin plazo: una promesa incumplida genera el próximo reclamo.",
]


def manual_como_texto() -> str:
    """Render del manual para el prompt del clasificador."""
    lineas = ["CATEGORÍAS (elegir exactamente una):"]
    for nombre, cat in CATEGORIAS.items():
        lineas.append(
            f"- {nombre}: {cat['descripcion']} Procedimiento: {cat['procedimiento']} "
            f"Responsable: {cat['responsable']}"
        )
    lineas.append("")
    lineas.append("NIVELES DE CRITICIDAD (elegir exactamente uno):")
    for codigo, niv in NIVELES.items():
        lineas.append(
            f"- {codigo} ({niv['nombre']}): {niv['descripcion']} Escalamiento: {niv['escalamiento']}"
        )
    lineas.append("")
    lineas.append("Variables para medir criticidad: " + "; ".join(f"{n} ({d})" for n, d in VARIABLES_CRITICIDAD))
    lineas.append("Áreas municipales de referencia: " + ", ".join(AREAS) + ".")
    return "\n".join(lineas)
