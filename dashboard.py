"""
Dashboard web del radar inmobiliario.

Correr local:   streamlit run dashboard.py
En la nube:     se publica en Streamlit Community Cloud (Fase 2).
"""
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import config

DB_PATH = Path(__file__).parent / "data" / "radar.db"
AR_TZ = timezone(timedelta(hours=-3))
MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]

st.set_page_config(page_title="Radar Inmobiliario — Banfield/Lomas",
                   page_icon="🏠", layout="wide")

# --- estética: un poco más de aire y tipografía legible ---
st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 2.2rem; max-width: 1100px;}
[data-testid="stMetricValue"] {font-size: 1.6rem;}
div[data-testid="stVerticalBlockBorderWrapper"] {margin-bottom: .15rem;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load(query, params=()):
    if not DB_PATH.exists():
        return pd.DataFrame()
    con = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, con, params=params)
    finally:
        con.close()


# ---------- formato de fechas y precios ----------
def _parse(iso):
    if not iso or pd.isna(iso):
        return None
    try:
        dt = datetime.fromisoformat(str(iso))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(AR_TZ)
    except Exception:
        return None


def fecha(iso):
    dt = _parse(iso)
    return f"{dt.day} {MESES[dt.month - 1]} {dt.strftime('%Y')}" if dt else "—"


def relativo(iso):
    dt = _parse(iso)
    if not dt:
        return ""
    secs = (datetime.now(AR_TZ) - dt).total_seconds()
    if secs < 0:
        return "recién"
    if secs < 3600:
        return f"hace {max(1, int(secs // 60))} min"
    if secs < 86400:
        return f"hace {int(secs // 3600)} h"
    días = int(secs // 86400)
    if días == 1:
        return "ayer"
    if días < 30:
        return f"hace {días} días"
    return fecha(iso)


def plata(price, currency):
    if price is None or pd.isna(price):
        return "Consultar"
    return f"{currency} {int(price):,}".replace(",", ".")


# ---------- carga ----------
st.title("🏠 Radar Inmobiliario")

if not DB_PATH.exists():
    st.warning("Todavía no hay datos. Corré `python run.py` primero.")
    st.stop()

listings = load("SELECT * FROM listings")
events = load("SELECT e.*, l.zones AS l_zones FROM events e "
              "LEFT JOIN listings l ON e.uid = l.uid ORDER BY e.created_at DESC")
agencies = load("SELECT * FROM agencies ORDER BY first_seen DESC")
runs = load("SELECT * FROM runs ORDER BY id DESC LIMIT 1")


def in_zone(zones_json, zone_name):
    if not zones_json:
        return False
    try:
        return zone_name in json.loads(zones_json)
    except Exception:
        return False


# ---------- filtro de zona (arriba) ----------
# Por defecto se muestra TU zona delimitada (no todo Lomas), para no confundir.
zone_names = [z["name"] for z in config.WATCH_ZONES]
zsel = st.radio("Mostrar:", zone_names + ["🌍 Toda la zona"], horizontal=True)
zone_active = zsel if zsel in zone_names else None

if zone_active:
    listings = listings[listings["zones"].apply(lambda z: in_zone(z, zone_active))]
    events = events[events["l_zones"].apply(lambda z: in_zone(z, zone_active))]

última = runs.iloc[0]["finished_at"] if not runs.empty else None
st.caption(f"Última actualización: **{relativo(última)}**  ·  "
           f"viendo: **{zsel.replace('🌍 ', '')}**")

# ---------- métricas ----------
c1, c2, c3 = st.columns(3)
c1.metric("🏘️ Propiedades activas",
          int((listings["active"] == 1).sum()) if not listings.empty else 0)
c2.metric("🏢 Inmobiliarias",
          listings["agency_id"].nunique() if not listings.empty else 0)
c3.metric("🔔 Novedades", len(events))

st.write("")
tab1, tab2, tab3 = st.tabs(["🔔 Novedades", "🏘️ Propiedades", "🏢 Inmobiliarias"])

EVENTOS = {
    "propiedad_nueva":        ("🆕", "Propiedad nueva",   "green"),
    "baja_precio":            ("📉", "Bajó de precio",    "blue"),
    "suba_precio":            ("📈", "Subió de precio",   "orange"),
    "inmobiliaria_nueva":     ("🏢", "Inmobiliaria nueva", "violet"),
    "propiedad_dada_de_baja": ("❌", "Dada de baja",      "gray"),
}

# ============ NOVEDADES ============
with tab1:
    if events.empty:
        st.info("Sin novedades todavía. Cuando aparezca algo nuevo en tu zona, lo vas a ver acá.")
    else:
        opciones = list(EVENTOS.keys())
        sel = st.pills("Filtrar", opciones, selection_mode="multi", default=opciones,
                       format_func=lambda k: f"{EVENTOS[k][0]} {EVENTOS[k][1]}",
                       label_visibility="collapsed")
        sel = sel or opciones
        ev = events[events["type"].isin(sel)].head(200)
        st.caption(f"{len(ev)} novedades")

        for _, r in ev.iterrows():
            d = json.loads(r["detail"]) if r["detail"] else {}
            icono, nombre, color = EVENTOS.get(r["type"], ("•", r["type"], "gray"))
            with st.container(border=True):
                top, der = st.columns([4, 1])
                top.markdown(f":{color}-background[{icono} {nombre}] &nbsp; "
                             f"**{r['title'] or 'Propiedad'}**", unsafe_allow_html=True)
                der.markdown(f"<div style='text-align:right;color:#888;font-size:.85em'>"
                             f"{relativo(r['created_at'])}</div>", unsafe_allow_html=True)
                if r["type"] in ("baja_precio", "suba_precio"):
                    st.markdown(f"💲 {plata(d.get('old_price'), d.get('currency',''))} "
                                f"→ **{plata(d.get('new_price'), d.get('currency',''))}**")
                elif d.get("price"):
                    st.markdown(f"💲 **{plata(d.get('price'), d.get('currency',''))}**")
                linea = []
                if d.get("address"):
                    linea.append(f"📍 {d['address']}")
                if d.get("url"):
                    linea.append(f"[Ver aviso ↗]({d['url']})")
                if linea:
                    st.caption("  ·  ".join(linea))

# ============ PROPIEDADES ============
with tab2:
    if listings.empty:
        st.info("Sin propiedades.")
    else:
        f1, f2, f3 = st.columns([2, 1, 1])
        buscar = f1.text_input("🔎 Buscar por dirección o título", "")
        fuentes = ["Todas"] + sorted(listings["source"].dropna().unique().tolist())
        fsel = f2.selectbox("Fuente", fuentes)
        moneda = f3.selectbox("Moneda", ["Todas", "USD", "ARS"])

        df = listings[listings["active"] == 1].copy()
        if buscar:
            m = (df["address"].fillna("").str.contains(buscar, case=False)
                 | df["title"].fillna("").str.contains(buscar, case=False))
            df = df[m]
        if fsel != "Todas":
            df = df[df["source"] == fsel]
        if moneda != "Todas":
            df = df[df["currency"] == moneda]

        df = df.sort_values("first_seen", ascending=False)
        df["Precio"] = df.apply(lambda r: plata(r["price"], r["currency"]), axis=1)
        df["Visto"] = pd.to_datetime(df["first_seen"], utc=True, errors="coerce") \
            .dt.tz_convert("America/Argentina/Buenos_Aires").dt.tz_localize(None)

        show = df[["Precio", "title", "address", "bedrooms", "source",
                   "agency_name", "Visto", "url"]].rename(columns={
                       "title": "Título", "address": "Dirección", "bedrooms": "Dorm.",
                       "source": "Fuente", "agency_name": "Inmobiliaria", "url": "Link"})
        st.caption(f"{len(show)} propiedades")
        st.dataframe(
            show, hide_index=True, use_container_width=True, height=560,
            column_config={
                "Link": st.column_config.LinkColumn("", display_text="ver ↗", width="small"),
                "Visto": st.column_config.DatetimeColumn("Visto", format="DD MMM YYYY"),
                "Dorm.": st.column_config.NumberColumn("Dorm.", width="small"),
                "Precio": st.column_config.TextColumn("Precio", width="small"),
            },
        )

# ============ INMOBILIARIAS ============
with tab3:
    if agencies.empty:
        st.info("Sin inmobiliarias.")
    else:
        counts = listings[listings["active"] == 1].groupby("agency_id").size().rename("Propiedades")
        ag = agencies.merge(counts, left_on="agency_id", right_index=True, how="left")
        ag["Propiedades"] = ag["Propiedades"].fillna(0).astype(int)
        if zone_active:
            ag = ag[ag["Propiedades"] > 0]
        ag["Inmobiliaria"] = ag["name"].fillna("(sin nombre)")
        ag["Detectada"] = pd.to_datetime(ag["first_seen"], utc=True, errors="coerce") \
            .dt.tz_convert("America/Argentina/Buenos_Aires").dt.tz_localize(None)
        ag = ag.sort_values("Propiedades", ascending=False)
        st.caption(f"{len(ag)} inmobiliarias")
        topn = int(ag["Propiedades"].max() or 1)
        st.dataframe(
            ag[["Inmobiliaria", "source", "Propiedades", "Detectada"]].rename(
                columns={"source": "Fuente"}),
            hide_index=True, use_container_width=True, height=560,
            column_config={
                "Propiedades": st.column_config.ProgressColumn(
                    "Propiedades", format="%d", min_value=0, max_value=topn),
                "Detectada": st.column_config.DatetimeColumn("Detectada", format="DD MMM YYYY"),
            },
        )
