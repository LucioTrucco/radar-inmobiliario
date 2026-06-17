"""
Dashboard web del radar inmobiliario.

Correr local:   streamlit run dashboard.py
En la nube:     se publica en Streamlit Community Cloud (Fase 2).
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

import config

DB_PATH = Path(__file__).parent / "data" / "radar.db"

st.set_page_config(page_title="Radar Inmobiliario — Banfield/Lomas",
                   page_icon="🏠", layout="wide")


@st.cache_data(ttl=60)
def load(query, params=()):
    if not DB_PATH.exists():
        return pd.DataFrame()
    con = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, con, params=params)
    finally:
        con.close()


def fmt_price(row):
    if pd.isna(row["price"]):
        return "—"
    return f"{row['currency']} {int(row['price']):,}".replace(",", ".")


EVENT_LABELS = {
    "propiedad_nueva": "🆕 Propiedad nueva",
    "baja_precio": "📉 Bajó de precio",
    "suba_precio": "📈 Subió de precio",
    "inmobiliaria_nueva": "🏢 Inmobiliaria nueva",
    "propiedad_dada_de_baja": "❌ Dada de baja",
}

st.title("🏠 Radar Inmobiliario — Banfield / Lomas")

if not DB_PATH.exists():
    st.warning("Todavía no hay datos. Corré `python run.py` primero.")
    st.stop()

# ---- datos ----
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


# ---- filtro de zona (arriba de todo) ----
zone_names = [z["name"] for z in config.WATCH_ZONES]
zone_opts = ["🌍 Toda la zona"] + zone_names
zsel = st.radio("Vista", zone_opts, horizontal=True, label_visibility="collapsed")
zone_active = zsel if zsel in zone_names else None

if zone_active:
    listings = listings[listings["zones"].apply(lambda z: in_zone(z, zone_active))]
    events = events[events["l_zones"].apply(lambda z: in_zone(z, zone_active))]

# ---- métricas arriba ----
c1, c2, c3, c4 = st.columns(4)
c1.metric("Propiedades activas", int((listings["active"] == 1).sum()) if not listings.empty else 0)
c2.metric("Inmobiliarias", listings["agency_id"].nunique() if not listings.empty else 0)
c3.metric("Novedades", len(events))
last = "—"
if not runs.empty and runs.iloc[0]["finished_at"]:
    last = runs.iloc[0]["finished_at"][:16].replace("T", " ")
c4.metric("Última actualización", last)

tab1, tab2, tab3 = st.tabs(["🔔 Novedades", "🏘️ Propiedades", "🏢 Inmobiliarias"])

# ============ NOVEDADES ============
with tab1:
    if events.empty:
        st.info("Sin novedades todavía.")
    else:
        tipos = st.multiselect(
            "Filtrar por tipo",
            options=list(EVENT_LABELS.keys()),
            default=list(EVENT_LABELS.keys()),
            format_func=lambda k: EVENT_LABELS.get(k, k),
        )
        ev = events[events["type"].isin(tipos)].head(300)
        for _, r in ev.iterrows():
            d = json.loads(r["detail"]) if r["detail"] else {}
            label = EVENT_LABELS.get(r["type"], r["type"])
            when = r["created_at"][:16].replace("T", " ")
            line = f"**{label}** · {when} · {r['zone']}  \n{r['title'] or ''}"
            if r["type"] in ("baja_precio", "suba_precio"):
                line += (f"  \n{d.get('currency','')} {int(d.get('old_price',0)):,} → "
                         f"{int(d.get('new_price',0)):,}").replace(",", ".")
            elif d.get("price"):
                line += f"  \n{d.get('currency','')} {int(d['price']):,}".replace(",", ".")
            if d.get("url"):
                line += f"  \n[Ver aviso]({d['url']})"
            st.markdown(line)
            st.divider()

# ============ PROPIEDADES ============
with tab2:
    if listings.empty:
        st.info("Sin propiedades.")
    else:
        col1, col2, col3 = st.columns(3)
        fuentes = ["(todas)"] + sorted(listings["source"].dropna().unique().tolist())
        fsel = col1.selectbox("Fuente", fuentes)
        solo_activas = col2.checkbox("Solo activas", value=True)
        moneda = col3.selectbox("Moneda", ["(todas)", "USD", "ARS"])

        df = listings.copy()
        if fsel != "(todas)":
            df = df[df["source"] == fsel]
        if solo_activas:
            df = df[df["active"] == 1]
        if moneda != "(todas)":
            df = df[df["currency"] == moneda]

        df = df.sort_values("first_seen", ascending=False)
        df["precio"] = df.apply(fmt_price, axis=1)
        show = df[["precio", "title", "address", "bedrooms", "source", "agency_name", "url", "first_seen"]]
        show = show.rename(columns={
            "title": "Título", "address": "Dirección", "bedrooms": "Dorm.",
            "source": "Fuente", "agency_name": "Inmobiliaria", "url": "Link",
            "first_seen": "Visto desde"})
        st.caption(f"{len(show)} propiedades")
        st.dataframe(
            show, hide_index=True, use_container_width=True,
            column_config={"Link": st.column_config.LinkColumn("Link", display_text="abrir")},
        )

# ============ INMOBILIARIAS ============
with tab3:
    if agencies.empty:
        st.info("Sin inmobiliarias.")
    else:
        counts = listings.groupby("agency_id").size().rename("propiedades")
        ag = agencies.copy()
        ag = ag.merge(counts, left_on="agency_id", right_index=True, how="left")
        ag["propiedades"] = ag["propiedades"].fillna(0).astype(int)
        if zone_active:
            ag = ag[ag["propiedades"] > 0]
        ag = ag[["name", "agency_id", "source", "propiedades", "first_seen"]].rename(columns={
            "name": "Nombre", "agency_id": "ID", "source": "Fuente",
            "propiedades": "Propiedades", "first_seen": "Detectada"})
        st.dataframe(ag.sort_values("Propiedades", ascending=False),
                     hide_index=True, use_container_width=True)
