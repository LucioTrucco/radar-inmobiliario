"""
Dashboard web del radar inmobiliario.

Correr local:   streamlit run dashboard.py
En la nube:     se publica en Streamlit Community Cloud.
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

st.markdown("""
<style>
#MainMenu, footer, header[data-testid="stHeader"] {visibility: hidden;}
.block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1080px;}
h1 {font-size: 1.7rem !important; font-weight: 600;}
[data-testid="stMetric"] {background: var(--secondary-background-color);
   border-radius: 12px; padding: 14px 18px;}
[data-testid="stMetricValue"] {font-size: 1.5rem; font-weight: 600;}
[data-testid="stMetricLabel"] {opacity: .8;}
/* tarjetas */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-tag) {
   border-radius: 14px; transition: border-color .15s; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.card-tag):hover {
   border-color: rgba(128,128,128,.5); }
.price {font-size: 1.35rem; font-weight: 700; line-height: 1.1;}
.addr {opacity: .85; font-size: .95rem;}
.muted {opacity: .6; font-size: .82rem;}
.tag {display:inline-block; padding: 1px 9px; border-radius: 20px;
   font-size: .72rem; font-weight: 600; letter-spacing:.02em;}
a.verlink {text-decoration: none; font-weight: 600; font-size: .85rem;}
.stTabs [data-baseweb="tab-list"] {gap: 4px;}
.stTabs [data-baseweb="tab"] {font-size: 1rem; padding: 8px 14px;}
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


def _dt(iso):
    if not iso or pd.isna(iso):
        return None
    try:
        d = datetime.fromisoformat(str(iso))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(AR_TZ)
    except Exception:
        return None


def fecha(iso):
    d = _dt(iso)
    return f"{d.day} {MESES[d.month - 1]} {d.year}" if d else "—"


def relativo(iso):
    d = _dt(iso)
    if not d:
        return ""
    s = (datetime.now(AR_TZ) - d).total_seconds()
    if s < 0:
        return "recién"
    if s < 3600:
        return f"hace {max(1, int(s // 60))} min"
    if s < 86400:
        return f"hace {int(s // 3600)} h"
    días = int(s // 86400)
    return "ayer" if días == 1 else (f"hace {días} días" if días < 30 else fecha(iso))


def plata(price, currency):
    if price is None or pd.isna(price):
        return "Consultar"
    return f"{currency} {int(price):,}".replace(",", ".")


SRC = {"argenprop": ("ArgenProp", "#185FA5", "#E6F1FB"),
       "remax": ("RE/MAX", "#A32D2D", "#FCEBEB"),
       "tokko": ("Inmobiliaria", "#534AB7", "#EEEDFE")}


def tag(text, fg, bg):
    return f"<span class='tag' style='color:{fg};background:{bg}'>{text}</span>"


# ---------- carga ----------
if not DB_PATH.exists():
    st.title("🏠 Radar Inmobiliario")
    st.warning("Todavía no hay datos. Corré `python run.py` primero.")
    st.stop()

listings = load("SELECT * FROM listings WHERE active = 1")
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


st.title("🏠 Radar Inmobiliario")
última = runs.iloc[0]["finished_at"] if not runs.empty else None

# ---------- selector de zona (vista principal) ----------
zone_names = [z["name"].split(" (")[0] for z in config.WATCH_ZONES]
zone_full = {z["name"].split(" (")[0]: z["name"] for z in config.WATCH_ZONES}
opciones_zona = zone_names + ["Toda la zona"]
zsel = st.segmented_control("Zona", opciones_zona, default=zone_names[0],
                            label_visibility="collapsed")
zsel = zsel or "Toda la zona"
zone_active = zone_full.get(zsel)

if zone_active:
    listings = listings[listings["zones"].apply(lambda z: in_zone(z, zone_active))]
    events = events[events["l_zones"].apply(lambda z: in_zone(z, zone_active))]

st.caption(f"📍 {zsel}  ·  actualizado {relativo(última)}")

c1, c2, c3 = st.columns(3)
c1.metric("Casas activas", len(listings))
c2.metric("Inmobiliarias", listings["agency_id"].nunique() if not listings.empty else 0)
nuevas_7d = 0
if not events.empty:
    lim = datetime.now(AR_TZ) - timedelta(days=7)
    nuevas_7d = sum(1 for x in events["created_at"]
                    if (_dt(x) or datetime.now(AR_TZ)) >= lim)
c3.metric("Novedades (7 días)", nuevas_7d)

st.write("")
tab1, tab2, tab3 = st.tabs(["🏘️ Propiedades", "🔔 Novedades", "🏢 Inmobiliarias"])

EVENTOS = {
    "propiedad_nueva":        ("🆕", "Nueva",            "#3B6D11", "#EAF3DE"),
    "baja_precio":            ("📉", "Bajó de precio",   "#185FA5", "#E6F1FB"),
    "suba_precio":            ("📈", "Subió de precio",  "#854F0B", "#FAEEDA"),
    "inmobiliaria_nueva":     ("🏢", "Inmobiliaria nueva", "#534AB7", "#EEEDFE"),
    "propiedad_dada_de_baja": ("❌", "Dada de baja",     "#5F5E5A", "#F1EFE8"),
}

# ============ PROPIEDADES ============
with tab1:
    if listings.empty:
        st.info("No hay casas en esta vista.")
    else:
        with st.container(border=False):
            cc = st.columns([3, 1.3, 1.3, 1.6])
            buscar = cc[0].text_input("Buscar", "", placeholder="🔎 calle, barrio…",
                                      label_visibility="collapsed")
            fopts = sorted(listings["source"].dropna().unique().tolist())
            fsel = cc[1].multiselect("Fuente", fopts,
                                     format_func=lambda s: SRC.get(s, (s,))[0],
                                     placeholder="Fuente", label_visibility="collapsed")
            msel = cc[2].multiselect("Moneda", ["USD", "ARS"],
                                     placeholder="Moneda", label_visibility="collapsed")
            orden = cc[3].selectbox("Orden", ["Más recientes", "Menor precio", "Mayor precio"],
                                    label_visibility="collapsed")

        df = listings.copy()
        if buscar:
            m = (df["address"].fillna("").str.contains(buscar, case=False)
                 | df["title"].fillna("").str.contains(buscar, case=False))
            df = df[m]
        if fsel:
            df = df[df["source"].isin(fsel)]
        if msel:
            df = df[df["currency"].isin(msel)]

        if orden == "Más recientes":
            df = df.sort_values("first_seen", ascending=False)
        else:
            df = df.sort_values("price", ascending=(orden == "Menor precio"),
                                na_position="last")

        total = len(df)
        if "n_show" not in st.session_state:
            st.session_state.n_show = 24
        n = min(st.session_state.n_show, total)
        st.caption(f"Mostrando {n} de {total} casas")

        cols = st.columns(3)
        for i, (_, r) in enumerate(df.head(n).iterrows()):
            nombre, fg, bg = SRC.get(r["source"], (r["source"], "#444", "#eee"))
            with cols[i % 3].container(border=True):
                st.markdown(
                    f"<span class='card-tag'></span>"
                    f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"<span class='price'>{plata(r['price'], r['currency'])}</span>"
                    f"{tag(nombre, fg, bg)}</div>", unsafe_allow_html=True)
                amb = f"🛏 {int(r['bedrooms'])} amb · " if pd.notna(r["bedrooms"]) and r["bedrooms"] else ""
                inmo = r["agency_name"] if pd.notna(r["agency_name"]) else ""
                st.markdown(f"<div class='addr'>📍 {r['address'] or '—'}</div>"
                            f"<div class='muted'>{amb}{inmo}</div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"<a class='verlink' href='{r['url']}' target='_blank'>Ver aviso ↗</a>"
                    f"<span class='muted'>{relativo(r['first_seen'])}</span></div>",
                    unsafe_allow_html=True)

        if total > n:
            if st.button(f"Ver más  ({total - n} restantes)", use_container_width=True):
                st.session_state.n_show += 24
                st.rerun()

# ============ NOVEDADES ============
with tab2:
    if events.empty:
        st.info("Sin novedades todavía. Cuando aparezca algo nuevo, lo vas a ver acá.")
    else:
        sel = st.pills("Tipo", list(EVENTOS.keys()), selection_mode="multi",
                       format_func=lambda k: f"{EVENTOS[k][0]} {EVENTOS[k][1]}",
                       label_visibility="collapsed")
        ev = events[events["type"].isin(sel)] if sel else events
        ev = ev.head(200)
        st.caption(f"{len(ev)} novedades" + ("" if sel else "  ·  todas"))

        for _, r in ev.iterrows():
            d = json.loads(r["detail"]) if r["detail"] else {}
            ic, nom, fg, bg = EVENTOS.get(r["type"], ("•", r["type"], "#444", "#eee"))
            with st.container(border=True):
                st.markdown(
                    f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                    f"{tag(ic + ' ' + nom, fg, bg)}"
                    f"<span class='muted'>{relativo(r['created_at'])}</span></div>"
                    f"<div style='font-weight:600;margin-top:4px'>{r['title'] or 'Propiedad'}</div>",
                    unsafe_allow_html=True)
                if r["type"] in ("baja_precio", "suba_precio"):
                    st.markdown(f"<span class='muted' style='text-decoration:line-through'>"
                                f"{plata(d.get('old_price'), d.get('currency',''))}</span> &nbsp;"
                                f"<b>{plata(d.get('new_price'), d.get('currency',''))}</b>",
                                unsafe_allow_html=True)
                elif d.get("price"):
                    st.markdown(f"<b>{plata(d.get('price'), d.get('currency',''))}</b>",
                                unsafe_allow_html=True)
                bits = []
                if d.get("address"):
                    bits.append(f"📍 {d['address']}")
                if d.get("url"):
                    bits.append(f"<a class='verlink' href='{d['url']}' target='_blank'>Ver aviso ↗</a>")
                if bits:
                    st.markdown(f"<div class='muted'>{'  ·  '.join(bits)}</div>",
                                unsafe_allow_html=True)

# ============ INMOBILIARIAS ============
with tab3:
    if agencies.empty:
        st.info("Sin inmobiliarias.")
    else:
        counts = listings.groupby("agency_id").size().rename("Casas")
        ag = agencies.merge(counts, left_on="agency_id", right_index=True, how="left")
        ag["Casas"] = ag["Casas"].fillna(0).astype(int)
        if zone_active:
            ag = ag[ag["Casas"] > 0]
        ag["Inmobiliaria"] = ag["name"].fillna("(sin nombre)")
        ag["Fuente"] = ag["source"].map(lambda s: SRC.get(s, (s,))[0])
        ag = ag.sort_values("Casas", ascending=False)
        st.caption(f"{len(ag)} inmobiliarias con casas en esta vista")
        st.dataframe(
            ag[["Inmobiliaria", "Fuente", "Casas"]],
            hide_index=True, use_container_width=True, height=560,
            column_config={"Casas": st.column_config.ProgressColumn(
                "Casas", format="%d", min_value=0,
                max_value=int(ag["Casas"].max() or 1))},
        )
