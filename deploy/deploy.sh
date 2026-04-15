#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/ubuntu/ai-project"
SERVICE="ai-investment-web"

cd "$PROJECT_DIR"

OLD_REQ_HASH=$(md5sum requirements.txt | awk '{print $1}')
git fetch --prune origin
git reset --hard origin/main
NEW_REQ_HASH=$(md5sum requirements.txt | awk '{print $1}')

echo "[deploy] now at $(git log -1 --pretty='%h %s')"

if [ "$OLD_REQ_HASH" != "$NEW_REQ_HASH" ]; then
    echo "[deploy] requirements.txt changed, installing deps..."
    export PATH="$HOME/.local/bin:$PATH"
    uv pip install -r requirements.txt
else
    echo "[deploy] requirements.txt unchanged, skipping pip install"
fi

echo "[deploy] restarting $SERVICE ..."
sudo -n /bin/systemctl restart "$SERVICE"

web_healthy=0
for i in $(seq 1 15); do
    if curl -sf -m 3 http://127.0.0.1:8501/_stcore/health >/dev/null; then
        echo "[deploy] web healthy after $((i*2))s"
        web_healthy=1
        break
    fi
    sleep 2
done
if [ "$web_healthy" -ne 1 ]; then
    echo "[deploy] web health check failed after 30s"
    sudo -n /bin/systemctl status "$SERVICE" --no-pager | tail -20
    exit 1
fi

SCHEDULER="ai-investment-scheduler"
echo "[deploy] restarting $SCHEDULER ..."
sudo -n /bin/systemctl restart "$SCHEDULER"
sleep 3
if sudo -n /bin/systemctl is-active "$SCHEDULER" | grep -qx active; then
    echo "[deploy] $SCHEDULER active"
else
    echo "[deploy] $SCHEDULER NOT active"
    sudo -n /bin/systemctl status "$SCHEDULER" --no-pager | tail -20
    exit 1
fi
