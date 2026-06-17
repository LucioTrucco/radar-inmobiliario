#!/bin/bash
# Actualización automática (la dispara macOS/launchd, sin ventana ni intervención).
# Hace lo mismo que actualizar.command pero headless y dejando un log.
set -u
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
LOG="data/auto-update.log"
mkdir -p data
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="
  git fetch -q origin && git reset --hard -q origin/main
  if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt
  fi
  ./.venv/bin/python run.py
  git add data/radar.db
  if git diff --staged --quiet; then
    echo "Sin cambios."
  else
    git -c user.name="radar-bot" -c user.email="radar-bot@users.noreply.github.com" \
      commit -q -m "Actualización local automática $(date -u +'%Y-%m-%d %H:%M UTC')"
    if git push -q; then echo "Subido a la nube."; else echo "Push falló (la nube cambió o auth); se reintenta la próxima corrida."; fi
  fi
  echo ""
} >> "$LOG" 2>&1
# mantener el log corto (últimas 400 líneas)
tail -n 400 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
