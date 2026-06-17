# 🏠 Radar Inmobiliario — Banfield / Lomas

Sistema que vigila las propiedades en venta de la zona y te avisa de las
**novedades**: propiedades nuevas, bajas de precio e inmobiliarias nuevas.

## ¿Qué hace?

1. **Recolecta** las propiedades publicadas en la zona desde varias fuentes:
   - **ArgenProp** (portal): todo el partido, con ID de inmobiliaria.
   - **RE/MAX** (API): todas las oficinas, con coordenadas GPS reales.
   - **Tokko Broker** (genérico): inmobiliarias con web propia en esa plataforma
     (ej. Pitton). Sumar una nueva es agregar una línea en `config.py`.
2. **Compara** con lo que ya había visto antes.
3. **Detecta y registra** las novedades:
   - 🆕 Propiedades nuevas
   - 📉 Bajas de precio (y 📈 subas)
   - 🏢 Inmobiliarias nuevas operando en la zona
   - ❌ Propiedades dadas de baja
4. **Muestra todo** en un dashboard web con filtros.

## Estado del proyecto

- ✅ **Fase 1 (actual):** funciona localmente. Fuente: ArgenProp (todo Lomas de Zamora).
- ⏳ **Fase 2 (próxima):** corre solo en la nube (gratis), dashboard online,
  más inmobiliarias y ZonaProp.

## Cómo usarlo (local)

```bash
# 1. Preparar el entorno (una sola vez)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Recolectar y detectar novedades
python run.py                 # corrida completa (según config.py)
python run.py --pages 5       # prueba rápida (5 páginas)

# 3. Ver el dashboard
streamlit run dashboard.py
```

La primera corrida "siembra" la base (todo aparece como nuevo). A partir de la
segunda, solo verás lo que realmente cambió.

## Configuración

Todo lo que querés vigilar está en [`config.py`](config.py): zonas, tipo de
operación (venta/alquiler), tipo de propiedad y cuántas páginas recorrer.

### Zonas delimitadas a medida (polígonos)

En `WATCH_ZONES` (dentro de `config.py`) podés definir un área exacta por sus
calles. Cada propiedad de esa zona se **geolocaliza una sola vez** (queda
cacheada) y se marca si cae dentro del polígono. El dashboard tiene un filtro
para ver *"solo esa zona"*.

Zona activa hoy: **Banfield Oeste**, rectángulo entre Alem, Carlos Croce,
Uriarte y Portela (153 propiedades).

```bash
python run.py --geocode-only   # geolocaliza lo pendiente sin volver a scrapear
```

## Estructura

```
radar-inmobiliario/
├── config.py            # qué vigilar (zonas, fuentes y polígonos)
├── run.py               # corre los scrapers, detecta novedades y geolocaliza
├── db.py                # base de datos + lógica de detección
├── geo.py               # geolocalización (Photon/OSM) + pertenencia a zonas
├── dashboard.py         # interfaz web (Streamlit) con filtro de zona
├── scrapers/
│   ├── base.py          # estructura común de una propiedad
│   ├── argenprop.py     # scraper de ArgenProp (portal)
│   ├── remax.py         # scraper de RE/MAX (API, todas las oficinas)
│   └── tokko.py         # scraper genérico de sitios Tokko Broker
└── data/radar.db        # base de datos (se crea sola)
```

## Próximos pasos (Fase 2)

- [ ] Pasar la base a Supabase (Postgres en la nube, gratis)
- [ ] Correr los scrapers solos con GitHub Actions (cron gratis)
- [ ] Publicar el dashboard en Streamlit Community Cloud
- [x] Sumar inmobiliarias con web propia (✅ RE/MAX + Tokko genérico)
- [ ] Sumar más sitios Tokko y plataformas propias (Fandiño, Sortino, etc.)
- [ ] Detectar propiedades repetidas entre fuentes (mismo inmueble en 2 portales)
- [x] Resolver nombres de las inmobiliarias de ArgenProp (✅ vía logo de la ficha)
- [ ] Sumar ZonaProp (requiere navegador automatizado por su anti-robot)
- [x] Delimitar zonas/barrios específicos (✅ Banfield Oeste por polígono)
- [ ] Reintentar geolocalización de direcciones fallidas (41 en Banfield)
```
