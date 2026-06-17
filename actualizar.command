#!/bin/bash
# Doble clic para actualizar el radar desde tu compu (incluye ArgenProp, que en
# la nube está bloqueado). Trae lo último de la nube, busca novedades en todas
# las fuentes y vuelve a subir todo. El dashboard online se actualiza solo.

cd "$(dirname "$0")" || exit 1

echo "==> Trayendo la última versión de la nube..."
git fetch -q origin && git reset --hard -q origin/main

echo "==> Preparando entorno..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
source .venv/bin/activate

echo "==> Buscando novedades (ArgenProp + RE/MAX + Tokko)..."
python run.py

echo "==> Guardando y subiendo a la nube..."
git add data/radar.db
if git diff --staged --quiet; then
  echo "    (sin cambios)"
else
  git commit -q -m "Actualización local $(date -u +'%Y-%m-%d %H:%M UTC')"
  if ! git push -q; then
    echo "    La nube cambió mientras corría. Volvé a abrir este archivo en un minuto."
  fi
fi

echo ""
echo "✅ Listo. El dashboard online se actualizará en un ratito."
read -p "Apretá Enter para cerrar."
