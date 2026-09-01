# Deploy de RADAR a un VPS (Ubuntu/Debian)

## Resumen

Un solo proceso (`main.py`) corre panel + bot. En el VPS va detrás de un reverse proxy
con HTTPS (Caddy), como servicio systemd, con la base en Supabase.

```
[Telegram] <--polling-- main.py (127.0.0.1:8000) <--reverse proxy-- Caddy (443, HTTPS) <-- funcionarios
                          |
                       Supabase (Postgres)
```

⚠️ **Un solo proceso puede hablar con el bot a la vez**: cuando el VPS quede corriendo,
apagar el `main.py` de la PC local (si los dos hacen polling, Telegram devuelve error 409).

## Pasos

```bash
# 1. Dependencias del sistema
sudo apt update && sudo apt install -y python3 python3-venv

# 2. Usuario sin privilegios y carpeta
sudo useradd --system --create-home --home-dir /opt/radar radar || true
sudo mkdir -p /opt/radar && sudo chown radar:radar /opt/radar

# 3. Copiar el proyecto (desde la PC, en PowerShell):
#    scp -r * usuario@VPS:/tmp/radar && luego mover a /opt/radar
#    (o git clone si el repo está en un remoto)

# 4. Entorno
sudo -u radar bash -c "cd /opt/radar && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"

# 5. Configuración: crear /opt/radar/.env (base: .env.example) con
#    TELEGRAM_BOT_TOKEN, OPENROUTER_API_KEY, DATABASE_URL (Supabase),
#    PANEL_PASSWORD (OBLIGATORIA acá), PANEL_HOST=127.0.0.1,
#    PANEL_BASE_URL=https://<dominio>  (la URL pública, para los links del bot)
sudo chmod 600 /opt/radar/.env && sudo chown radar:radar /opt/radar/.env

# 6. Servicio
sudo cp deploy/radar.service /etc/systemd/system/radar.service
sudo systemctl daemon-reload && sudo systemctl enable --now radar
journalctl -u radar -f   # verificar arranque

# 7. HTTPS (con dominio): instalar Caddy, usar deploy/Caddyfile con el dominio real
#    Sin dominio: no exponer el panel por HTTP plano con contraseña; conseguir al menos
#    un subdominio (el bot funciona igual sin dominio, lo que necesita HTTPS es el panel).

# 8. Firewall básico
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw enable
```

## Checklist antes de dar por bueno el deploy

- [ ] `journalctl -u radar` muestra "Bot de Telegram iniciado (polling)" y "Base de datos lista: Postgres"
- [ ] El panel pide contraseña y responde por HTTPS
- [ ] `main.py` local apagado (sin conflicto 409 de polling)
- [ ] Cargar un caso de prueba por el bot y verlo en el panel público
