"""Punto de entrada de RADAR: levanta el panel web y, si hay token, el bot de Telegram."""
import logging

import uvicorn

from radar import config
from radar.webapp import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
# El polling de Telegram loguea cada request a nivel INFO; lo bajamos para no llenar la consola.
logging.getLogger("httpx").setLevel(logging.WARNING)

if __name__ == "__main__":
    uvicorn.run(app, host=config.PANEL_HOST, port=config.PANEL_PORT, log_level="info")
