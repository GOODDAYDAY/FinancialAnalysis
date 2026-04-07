# Deployment Guide

This project supports two deployment targets:

- **Local Windows** development (via `scripts/run.bat`)
- **Linux server** production (via `deploy/install_linux.sh`)

## Linux server deployment (Singapore or any Linux host)

### Quick install on a fresh Ubuntu/Debian server

```bash
# 1. Clone the repo
git clone <your-repo-url> /opt/ai-investment
cd /opt/ai-investment

# 2. Run the installer (will use sudo for systemd setup)
bash deploy/install_linux.sh

# 3. Edit your credentials
nano .env
# Set DEEPSEEK_API_KEY, QQ_EMAIL, QQ_EMAIL_PASSWORD, QQ_EMAIL_RECIPIENTS, WATCHLIST

# 4. Start the web app
sudo systemctl start ai-investment-web
sudo systemctl status ai-investment-web

# 5. Start the scheduled timer (daily email)
sudo systemctl start ai-investment-scheduled.timer
sudo systemctl list-timers | grep ai-investment
```

### What the installer does

| Step | Action |
|:---|:---|
| 1 | Installs system packages (curl, git, build-essential) |
| 2 | Installs `uv` (Python package manager) |
| 3 | Creates `.venv` with Python 3.11 and installs all dependencies |
| 4 | Copies `.env.example` to `.env` if missing |
| 5 | Installs two systemd units: web service + scheduled timer |
| 6 | Opens port 8501 in `ufw` firewall (if installed) |

### Systemd units installed

| Unit | Purpose |
|:---|:---|
| `ai-investment-web.service` | Streamlit web UI on port 8501, restart on failure |
| `ai-investment-scheduled.service` | Oneshot scheduled analysis + email |
| `ai-investment-scheduled.timer` | Triggers the scheduled service Mon-Fri 09:30 UTC (= 17:30 Singapore Time, after A-share market close) |

### Customizing the schedule

Edit `/etc/systemd/system/ai-investment-scheduled.timer`:

```ini
[Timer]
# Examples:
# Every day at 09:30 UTC (17:30 SGT):
OnCalendar=*-*-* 09:30:00 UTC

# Every 4 hours during trading hours (UTC):
OnCalendar=*-*-* 01,05,07 *:30:00 UTC

# Multiple times per day:
OnCalendar=Mon..Fri 01:30,07:30 UTC
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ai-investment-scheduled.timer
```

### Logs

```bash
# Web app logs
tail -f logs/web.log
sudo journalctl -u ai-investment-web -f

# Scheduled task logs
tail -f logs/scheduled.log
sudo journalctl -u ai-investment-scheduled.service -f

# Timer status
sudo systemctl list-timers | grep ai-investment
```

### Reverse proxy with HTTPS (optional)

For production use with a domain, put nginx + Let's Encrypt in front:

```nginx
# /etc/nginx/sites-available/ai-investment
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```

Then:
```bash
sudo ln -s /etc/nginx/sites-available/ai-investment /etc/nginx/sites-enabled/
sudo certbot --nginx -d your-domain.com
```

### Singapore-specific notes

- **Timezone**: Singapore is UTC+8. A-share trading hours are 09:30-15:00 SGT. Schedule the daily task after 15:00 SGT (07:00 UTC) for closing-price analysis.
- **Network**: yfinance, akshare (Eastmoney), DeepSeek API, and QQ SMTP are all reachable from Singapore.
- **DeepSeek API**: Singapore IPs can access `api.deepseek.com` directly without proxy.
- **akshare data sources**: Eastmoney/Sina/THS are accessible globally.
- **QQ Mail SMTP**: `smtp.qq.com:465` is reachable from Singapore.

### Updating the deployment

```bash
cd /opt/ai-investment
git pull
uv pip install -r requirements.txt
sudo systemctl restart ai-investment-web
```

### Uninstalling

```bash
sudo systemctl stop ai-investment-web ai-investment-scheduled.timer
sudo systemctl disable ai-investment-web ai-investment-scheduled.timer
sudo rm /etc/systemd/system/ai-investment-web.service
sudo rm /etc/systemd/system/ai-investment-scheduled.service
sudo rm /etc/systemd/system/ai-investment-scheduled.timer
sudo systemctl daemon-reload
```
