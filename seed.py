"""Carga casos de ejemplo (los de la presentación institucional) para probar el panel.

Uso:  python seed.py
Solo carga si la base está vacía; no pisa datos reales.
"""
from radar import db

EJEMPLOS = [
    {
        "caso": {
            "texto": "arreglen las calles primero, hace un mes que reclamo el bache de Bolívar al 500 y nadie viene",
            "plataforma": "Instagram",
            "relevancia": "Reclamo reiterado con respuestas de otros vecinos (142 me gusta, 38 respuestas).",
            "funcionario_nombre": "Ejemplo (seed)",
        },
        "cls": {
            "categoria": "Reclamo",
            "nivel": "N2",
            "tema": "Bacheo y calzada",
            "ubicacion": "Bolívar al 500",
            "area": "Obras Públicas",
            "accion_recomendada": "Derivar a Obras Públicas, validar reclamo previo y estado de obra, comunicar al vecino.",
            "justificacion": "Problema concreto que requiere gestión; se repite y tiene acompañamiento de otros vecinos.",
        },
        "origen": "ia_confirmada",
        "estado": "derivado",
        "comentarios": [
            ("Comité", "Se derivó a Obras Públicas. Queda pendiente confirmar el estado de obra en la zona."),
        ],
    },
    {
        "caso": {
            "texto": "¿el turno para la licencia de conducir se saca por la web o hay que ir a la sede?",
            "plataforma": "Facebook",
            "relevancia": "Mensaje directo a la cuenta institucional.",
            "funcionario_nombre": "Ejemplo (seed)",
        },
        "cls": {
            "categoria": "Consulta",
            "nivel": "N1",
            "tema": "Licencias de conducir",
            "ubicacion": None,
            "area": "Atención ciudadana",
            "accion_recomendada": "Responder con el dato cierto del circuito de turnos.",
            "justificacion": "Pedido de información puntual; la respuesta cierra el caso sin escalamiento.",
        },
        "origen": "ia_confirmada",
        "estado": "resuelto",
        "comentarios": [],
    },
    {
        "caso": {
            "texto": "chanta, puro anuncio y nada de obra",
            "plataforma": "Instagram",
            "relevancia": "Comentario sin datos verificables en una publicación institucional.",
            "funcionario_nombre": "Ejemplo (seed)",
        },
        "cls": {
            "categoria": "Crítica",
            "nivel": "N1",
            "tema": "Gestión de obra pública",
            "ubicacion": None,
            "area": "Comunicación",
            "accion_recomendada": "Registrar y observar evolución; responder solo si aparece un dato concreto.",
            "justificacion": "Valoración política sin reclamo operativo; se registra para medir volumen y tema.",
        },
        "origen": "ia_confirmada",
        "estado": "en_observacion",
        "comentarios": [],
    },
    {
        "caso": {
            "texto": "dicen que sacan el estacionamiento medido de toda la ciudad a partir del lunes",
            "plataforma": "WhatsApp",
            "relevancia": "Cadena reenviada varias veces; llegó por distintos grupos.",
            "funcionario_nombre": "Ejemplo (seed)",
        },
        "cls": {
            "categoria": "Información incorrecta",
            "nivel": "N2",
            "tema": "Estacionamiento medido",
            "ubicacion": None,
            "area": "Área técnica y Comunicación",
            "accion_recomendada": "Verificar con el área competente qué es cierto antes de decidir si corresponde aclarar.",
            "justificacion": "Afirmación potencialmente errónea en circulación; sin verificación no hay aclaración.",
        },
        "origen": "ia_confirmada",
        "estado": "en_curso",
        "comentarios": [
            ("Comité", "El área de tránsito confirma que NO hay cambios previstos. Evaluar si amerita aclaración pública."),
        ],
    },
    {
        "caso": {
            "texto": "no hay luz en Marcos Paz al 1200 / toda la cuadra a oscuras hace 4 días / columna sin luminaria frente a la escuela",
            "plataforma": "Facebook",
            "relevancia": "Cuatro publicaciones distintas sobre el mismo tema en 72 horas, zona Villa 9 de Julio.",
            "funcionario_nombre": "Ejemplo (seed)",
        },
        "cls": {
            "categoria": "Tendencia",
            "nivel": "N2",
            "tema": "Alumbrado público",
            "ubicacion": "Villa 9 de Julio",
            "area": "Servicios Públicos",
            "accion_recomendada": "Agrupar las evidencias y avisar preventivamente a Servicios Públicos: no son cuatro casos, es un problema con cuatro señales.",
            "justificacion": "Varias evidencias sobre el mismo tema y zona en una ventana de 72 horas.",
        },
        "origen": "ia_confirmada",
        "estado": "en_curso",
        "comentarios": [
            ("Comité", "Servicios Públicos programó cuadrilla para la zona."),
        ],
    },
    {
        "caso": {
            "texto": "El mismo texto sobre la licitación de transporte replicado por unas 40 cuentas en 20 minutos, varias sin actividad previa.",
            "plataforma": "X (Twitter)",
            "relevancia": "Sin repercusión fuera de esa publicación por ahora; se preservaron capturas.",
            "funcionario_nombre": "Ejemplo (seed)",
        },
        "cls": {
            "categoria": "Posible acción coordinada",
            "nivel": "N2",
            "tema": "Licitación de transporte",
            "ubicacion": None,
            "area": "Tecnología",
            "accion_recomendada": "Preservar evidencia, monitorear alcance y escalar al Comité si crece. El sistema señala indicios: no concluye que exista una campaña.",
            "justificacion": "Textos repetidos y actividad simultánea de perfiles similares; alcance mínimo por ahora.",
        },
        "origen": "ia_confirmada",
        "estado": "en_observacion",
        "comentarios": [],
    },
]


def main() -> None:
    db.init_db()
    if db.contar()["total"] > 0:
        print("La base ya tiene casos: no se cargan ejemplos (para empezar de cero, borrar data/radar.db).")
        return
    for ejemplo in EJEMPLOS:
        caso_id = db.crear_caso(**ejemplo["caso"])
        db.guardar_clasificacion(caso_id, ejemplo["cls"], origen=ejemplo["origen"])
        db.cambiar_estado(caso_id, ejemplo["estado"])
        for autor, texto in ejemplo["comentarios"]:
            db.agregar_comentario(caso_id, autor, texto)
    print(f"Cargados {len(EJEMPLOS)} casos de ejemplo (uno por categoria del manual).")


if __name__ == "__main__":
    main()
