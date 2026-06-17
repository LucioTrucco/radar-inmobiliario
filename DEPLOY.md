# 🚀 Poner el Radar en la nube (Fase 2)

Objetivo: que corra solo todos los días y ver el dashboard online desde el celular.
Usamos 2 servicios gratis: **GitHub** (corre el scraper) y **Streamlit Cloud** (muestra el dashboard).

## Parte 1 — GitHub (ya hecho ✅)

El proyecto ya está subido a tu GitHub y el "robot" (GitHub Actions) está programado
para correr **todos los días a las 8:00 (hora Argentina)**.

- Para correrlo a mano cuando quieras: andá a tu repo → pestaña **Actions** →
  "Radar Inmobiliario" → botón **Run workflow**.
- Cada corrida actualiza la base de datos sola y guarda los cambios.

## Parte 2 — Dashboard online (Streamlit Community Cloud)

1. Entrá a **https://share.streamlit.io** y tocá **"Sign in with GitHub"**
   (usás tu misma cuenta de GitHub, no creás nada nuevo).
2. Autorizá a Streamlit a ver tus repositorios.
3. Tocá **"Create app"** → **"Deploy a public app from GitHub"**.
4. Completá:
   - **Repository:** `LucioTrucco/radar-inmobiliario`
   - **Branch:** `main`
   - **Main file path:** `dashboard.py`
5. (Opcional) En **Advanced settings** → **Python version**: elegí **3.12**.
6. Tocá **Deploy**. En 1-2 minutos te da una URL tipo
   `https://radar-inmobiliario.streamlit.app` → esa es tu dashboard, entrás desde
   cualquier dispositivo.

Cada vez que el robot actualiza la base, el dashboard se actualiza solo.

## ¿Y ZonaProp?

Queda como próximo paso: necesita un navegador automatizado (headless) que sortee
su bloqueo. Se monta sobre este mismo esquema de GitHub Actions.

## Notas

- **Costo:** $0. Ambos servicios tienen plan gratis de sobra para este uso.
- **Posible límite:** ArgenProp a veces frena los pedidos automáticos desde
  servidores (no desde tu casa). Si en la nube trae menos propiedades de lo
  esperado, lo resolvemos agregando un proxy o más pausas. RE/MAX y las
  inmobiliarias Tokko no tienen ese problema.
