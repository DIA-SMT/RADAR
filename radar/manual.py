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
        "subtipos": {
            "Error o dato inexacto": "Corrección informativa; contacto directo si el emisor es identificable.",
            "Rumor": "Monitorear; salir con información verificable solo si crece.",
            "Desinformación (falsa y deliberada)": "Contranarrativa fáctica, nunca adjetiva; responder a la narrativa sin mencionar la publicación original ni al autor.",
            "Contenido manipulado": "Documentación verificable y reporte a la plataforma.",
        },
    },
    "Tendencia": {
        "descripcion": "Varias evidencias sobre un mismo tema revelan una necesidad creciente.",
        "procedimiento": "Agrupar evidencias y avisar preventivamente al área.",
        "responsable": "Escucha digital",
    },
    "Posible acción coordinada": {
        "descripcion": "Indicios de coordinación: textos repetidos, actividad simultánea, perfiles similares.",
        "procedimiento": "Preservar evidencia y escalar si corresponde. Habitualmente no responder. Siempre sujeto a validación humana.",
        "responsable": "Comité de Respuesta",
    },
}

# Coordinación: solo se sugiere con AL MENOS 3 indicios técnicos de esta lista cerrada.
# La coordinación NUNCA se infiere por ideología, consigna común, seguir a los mismos
# dirigentes ni horario habitual de publicación. (Criterio del Protocolo RADAR v1 de
# Prensa/Comunicación, regla D1.)
INDICIOS_COORDINACION = [
    "Publicación sincronizada en ventanas menores a 60 segundos entre cuentas sin relación",
    "Repetición literal del mismo texto, incluidos errores de tipeo idénticos",
    "Mismo recurso gráfico con idéntico archivo/hash",
    "Cuentas creadas en un período acotado y sin actividad previa",
    "Relación seguidores/seguidos atípica en las cuentas participantes",
    "Ausencia de interacción nativa (solo replican, no conversan)",
    "Secuencias de publicación idénticas entre cuentas",
]

# Reglas ante la duda (se aplican SIEMPRE, también en la clasificación automática).
REGLAS_ANTE_DUDA = [
    "Ante duda entre expresión legítima y otra categoría, prevalece la libertad de expresión: se registra y observa.",
    "Ante duda sobre un posible riesgo (amenaza, datos personales expuestos), prevalece la interpretación protectora: mejor un falso positivo que un falso negativo.",
    "La clasificación siempre puede corregirse; la corrección queda registrada.",
]

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
        for subtipo, tratamiento in cat.get("subtipos", {}).items():
            lineas.append(f"    · Subtipo {subtipo}: {tratamiento}")
    lineas.append("")
    lineas.append(
        "REGLA DE COORDINACIÓN: 'Posible acción coordinada' solo se propone si la evidencia "
        "o el contexto describen AL MENOS 3 de estos indicios técnicos (nunca por ideología, "
        "consigna común o seguir a los mismos dirigentes):"
    )
    for indicio in INDICIOS_COORDINACION:
        lineas.append(f"- {indicio}")
    lineas.append("Con menos de 3 indicios, clasificar como Crítica o Tendencia y anotar los indicios en la justificación.")
    lineas.append("")
    lineas.append("REGLAS ANTE LA DUDA:")
    for regla in REGLAS_ANTE_DUDA:
        lineas.append(f"- {regla}")
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
