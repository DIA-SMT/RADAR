# 📡 RADAR — Red de Análisis Digital, Alertas y Respuestas

Escucha activa del vecino en redes sociales. Secretaría General · Ciudad de San Miguel de Tucumán.

Un funcionario aporta evidencia tomada de redes (comentario, mensaje, captura) por un **bot de Telegram**;
el **motor de análisis** la clasifica según el **Manual de Actuación** (6 categorías, niveles N1–N4) y
propone una ficha; el funcionario **confirma o corrige**; el caso queda en el **panel web** para
seguimiento y debate del comité.

> Principio rector: la tecnología analiza, el manual orienta, **el funcionario decide**.
> El sistema no monitorea redes automáticamente: toda intervención empieza con una decisión humana.

## Requisitos

- Python 3.11 o superior (probado con 3.14)
- Un bot de Telegram (token de [@BotFather](https://t.me/BotFather))
- Una clave de [OpenRouter](https://openrouter.ai) para la clasificación automática (opcional:
  sin clave, el bot pasa a clasificación manual con botones)
- Un proyecto de [Supabase](https://supabase.com) como base de datos (opcional: sin
  `DATABASE_URL`, usa SQLite local en `data/radar.db`)

## Instalación

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Completar `.env` con el token del bot y la clave de OpenRouter (ver comentarios en el archivo).

## Uso

```bash
# opcional: cargar casos de ejemplo para ver el panel con datos
.venv\Scripts\python seed.py

# levantar todo (panel + bot en un solo proceso)
.venv\Scripts\python main.py
```

- Panel: <http://localhost:8000>
- Bot: mandarle un texto o captura y seguir las preguntas. `/start` muestra la ayuda y tu ID.

### Base de datos (Supabase)

En el dashboard de Supabase: **Settings → Database → Connection string (URI)**, usar la del
*pooler* (puerto 6543 «transaction» o 5432 «session») y pegarla en `DATABASE_URL` del `.env`,
manteniendo `sslmode=require`. Las tablas se crean solas al arrancar. Sin `DATABASE_URL`
el sistema usa SQLite local: sirve para desarrollo, y los datos NO se comparten entre ambas.

### Acceso al panel (login)

El panel se loguea con **usuarios de Supabase Auth**: en el dashboard de Supabase →
**Authentication → Users → Add user** (email + contraseña, con *Auto confirm* activado).
Requiere en el `.env`: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` y `SESSION_SECRET`
(cadena aleatoria larga; con ella se firman las cookies de sesión).

- Las sesiones duran 7 días. Borrar un usuario en Supabase no corta sus sesiones ya abiertas;
  para cerrar todas las sesiones de golpe, cambiar `SESSION_SECRET` y reiniciar.
- Sin Supabase configurado, el panel cae a `PANEL_PASSWORD` (contraseña única, HTTP Basic);
  sin ninguna de las dos, solo escucha en `127.0.0.1` (modo desarrollo).

### Seguridad del piloto

- `TELEGRAM_ALLOWED_IDS`: lista de IDs habilitados a usar el bot (cada uno ve su ID con `/start`).
  **Vacío = bot abierto a cualquiera que lo encuentre** — completarla apenas se tengan los IDs.
- Las capturas (`/capturas/...`) exigen el mismo login que el resto del panel; los logos
  (`/static/...`) son públicos.

### Deploy al VPS (cuando llegue el momento)

1. Definir `PANEL_PASSWORD` y `TELEGRAM_ALLOWED_IDS` en el `.env` del servidor.
2. Correr uvicorn solo en `127.0.0.1` (`PANEL_HOST=127.0.0.1`) detrás de un reverse proxy con
   HTTPS (Caddy o nginx + Let's Encrypt): HTTP Basic sin TLS manda la contraseña en claro.
3. Apuntar `PANEL_BASE_URL` a la URL pública (ej. `https://radar.smt.gob.ar`) para que los
   links que manda el bot funcionen.

## Estructura

```
main.py              # punto de entrada: uvicorn + bot
seed.py              # casos de ejemplo (uno por categoría)
radar/
  config.py          # configuración (.env)
  manual.py          # Manual de Actuación v0: categorías, niveles, matriz de procedimientos
  db.py              # SQLite (data/radar.db)
  classifier.py      # motor de análisis (OpenRouter, compatible OpenAI)
  bot.py             # bot de Telegram (carga guiada + confirmación)
  webapp.py          # panel FastAPI
  templates/         # vistas del panel
data/                # base de datos y capturas (se crea sola; no versionar)
```

## Hoja de ruta

- **Etapa 1 (esta):** bot de carga + clasificación asistida + panel con seguimiento. ✅
- **Etapa 2:** Manual de Actuación aprobado como reglas del sistema, ficha de actuación completa,
  plazos de escalamiento por nivel.
- **Etapa 3:** comité y debate: hilos por caso, notificaciones N3/N4, registro de decisiones,
  ciclo de aprendizaje del manual.
- **Etapa 4:** tendencias y métricas: agrupación automática por tema/zona/ventana temporal, tablero.
- **Etapa 5:** escucha activa en redes (ingesta semiautomática). Requiere definición institucional
  previa: cambia la premisa de "no monitoreo automático".
