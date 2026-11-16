#!/usr/bin/env python3
"""Vigía de RADAR: si el panel o la base se caen, avisa por Telegram al administrador.

Corre cada 5 minutos vía systemd timer (deploy/radar-health.timer). Avisa una vez
al caer, repite el aviso cada 6 horas mientras siga caído, y avisa al recuperarse.
Con --test manda un mensaje de prueba para verificar el canal de aviso.

Limitación conocida: si se cae el VPS entero, el vigía cae con él; cubre los casos
de base pausada/inaccesible y de aplicación rota, que son los que ya nos pasaron.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from radar import config, db  # noqa: E402

# Chat de Telegram que recibe los avisos (administrador del sistema).
AVISAR_A = 8816256269
ESTADO_PATH = config.DATA_DIR / "health_estado.json"
REAVISO_SEGUNDOS = 6 * 3600


def chequear() -> list:
    fallas = []
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/login", timeout=10) as r:
            if r.status != 200:
                fallas.append(f"el panel devuelve código {r.status}")
    except Exception as exc:
        fallas.append(f"el panel no responde ({type(exc).__name__})")
    try:
        db.contar()
    except Exception as exc:
        fallas.append(f"la base de datos no responde ({type(exc).__name__})")
    return fallas


def avisar(texto: str) -> None:
    pedido = urllib.request.Request(
        f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
        data=json.dumps({"chat_id": AVISAR_A, "text": texto}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(pedido, timeout=15)


def cargar_estado() -> dict:
    try:
        return json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"caido": False, "ultimo_aviso": 0}


def guardar_estado(estado: dict) -> None:
    ESTADO_PATH.write_text(json.dumps(estado), encoding="utf-8")


def main() -> None:
    if "--test" in sys.argv:
        avisar("✅ RADAR: el monitoreo quedó activo. Si el panel o la base se caen, te aviso por acá.")
        print("mensaje de prueba enviado")
        return

    fallas = chequear()
    estado = cargar_estado()
    ahora = time.time()

    if fallas:
        hay_que_avisar = (not estado["caido"]) or (ahora - estado["ultimo_aviso"] > REAVISO_SEGUNDOS)
        if hay_que_avisar:
            detalle = "\n".join(f"• {f}" for f in fallas)
            sigue = " (sigue caído)" if estado["caido"] else ""
            try:
                avisar(f"🔴 RADAR caído{sigue}:\n{detalle}\n\nPanel: {config.PANEL_BASE_URL}")
                estado["ultimo_aviso"] = ahora
            except Exception as exc:
                print(f"no se pudo enviar el aviso: {exc}")
        estado["caido"] = True
        print("FALLAS:", "; ".join(fallas))
    else:
        if estado["caido"]:
            try:
                avisar("🟢 RADAR se recuperó: panel y base de datos responden de nuevo.")
            except Exception as exc:
                print(f"no se pudo enviar el aviso de recuperación: {exc}")
        estado = {"caido": False, "ultimo_aviso": 0}
        print("OK: panel y base responden")

    guardar_estado(estado)


if __name__ == "__main__":
    main()
