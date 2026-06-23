"""
Dashboard web del radar inmobiliario.

Streamlit oficia solo de host: carga los datos de la base y renderiza una
interfaz propia (HTML/CSS/JS a medida). Registro product, identidad monocromo
con sistema de temas conmutable (claro/tintado/oscuro/color × 4 acentos).
Sistema de diseño: design-system/MASTER.md.

Correr local:   streamlit run dashboard.py
En la nube:     Streamlit Community Cloud.
"""
import json
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import config

DB_PATH = Path(__file__).parent / "data" / "radar.db"
AR_TZ = timezone(timedelta(hours=-3))

st.set_page_config(page_title="Radar Inmobiliario", page_icon="🏠", layout="wide")
st.markdown("""<style>
#MainMenu, footer, header[data-testid="stHeader"],
[data-testid="stDecoration"], [data-testid="stToolbar"], [data-testid="stStatusWidget"] {display:none !important;}
.block-container {padding:0 !important; max-width:100% !important;}
[data-testid="stAppViewContainer"]>.main {padding:0;}
iframe {border:none;}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load(query):
    if not DB_PATH.exists():
        return pd.DataFrame()
    con = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(query, con)
    finally:
        con.close()


def to_iso_ar(iso):
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso))
        d = d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        return d.astimezone(AR_TZ).isoformat()
    except Exception:
        return None


if not DB_PATH.exists():
    st.error("Todavía no hay datos. Corré `python run.py` primero.")
    st.stop()

listings = load("SELECT uid,price,currency,address,bedrooms,source,agency_name,url,"
                "first_seen,zones,title,lat,lon FROM listings WHERE active=1")

# Tope de precio: ocultamos las casas que cuesten más que el máximo (en USD).
TOPE = getattr(config, "MAX_PRICE_USD", None)
if TOPE and not listings.empty:
    caras = (listings["currency"] == "USD") & (listings["price"] > TOPE)
    listings = listings[~caras]


# Dedup por dirección (misma casa publicada en varias fuentes / por varias
# inmobiliarias = una sola tarjeta). Prioridad: RE/MAX (GPS) > ArgenProp > resto.
def _addr_key(addr):
    m = re.search(r"(\d{2,5})", addr or "")
    if not m:
        return None
    street = re.sub(r"[^a-záéíóúñ]", "", addr.split(m.group(1))[0].lower())[:7]
    return f"{street}|{m.group(1)}" if street else None


if not listings.empty:
    prio = {"remax": 0, "argenprop": 1, "tokko": 2, "buscadorprop": 3}
    listings = listings.assign(
        _p=listings["source"].map(lambda s: prio.get(s, 9)),
        _k=listings["address"].map(_addr_key))
    listings = listings.sort_values("_p")
    dup = listings["_k"].notna() & listings.duplicated("_k", keep="first")
    listings = listings[~dup].drop(columns=["_p", "_k"])
events = load("SELECT e.type,e.title,e.detail,e.created_at, l.zones AS l_zones "
              "FROM events e LEFT JOIN listings l ON e.uid=l.uid "
              "ORDER BY e.created_at DESC LIMIT 400")
runs = load("SELECT finished_at FROM runs ORDER BY id DESC LIMIT 1")


def jz(s):
    try:
        return json.loads(s) if s else []
    except Exception:
        return []


L = [{
    "id": r.uid,
    "price": None if pd.isna(r.price) else float(r.price),
    "cur": r.currency, "addr": r.address or "",
    "beds": None if pd.isna(r.bedrooms) else int(r.bedrooms),
    "src": r.source, "ag": None if pd.isna(r.agency_name) else r.agency_name,
    "url": r.url, "ts": to_iso_ar(r.first_seen), "zones": jz(r.zones),
    "lat": None if pd.isna(r.lat) else float(r.lat),
    "lon": None if pd.isna(r.lon) else float(r.lon),
} for r in listings.itertuples()]

E = []
for r in events.itertuples():
    d = json.loads(r.detail) if r.detail else {}
    pr = d.get("new_price") or d.get("price")
    if TOPE and d.get("currency") == "USD" and pr and pr > TOPE:
        continue
    E.append({"type": r.type, "title": r.title or "", "ts": to_iso_ar(r.created_at),
              "zones": jz(r.l_zones), "price": d.get("price"), "cur": d.get("currency"),
              "old": d.get("old_price"), "new": d.get("new_price"),
              "addr": d.get("address"), "url": d.get("url")})

DATA = {
    "listings": L, "events": E,
    "zones": [z["name"] for z in config.WATCH_ZONES],
    "zoneShort": [z["name"].split(" (")[0] for z in config.WATCH_ZONES],
    "polys": [z.get("polygon", []) for z in config.WATCH_ZONES],
    "updated": to_iso_ar(runs.iloc[0]["finished_at"]) if not runs.empty else None,
}

HTML = r"""
<!DOCTYPE html><html lang="es" data-theme="oscuro" data-accent="grafito" data-shape="suave"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
:root{
  --t-xs:.75rem; --t-sm:.8125rem; --t-base:1rem; --t-md:1.0625rem; --t-lg:1.5rem;
  --ease:cubic-bezier(.16,1,.3,1); --z-sticky:10; --pad:28px;
  --accent:var(--accent-l);
}
/* ---- acentos ---- */
:root[data-accent=cobalto]{--accent-l:#2f5bd0;--accent-d:#83a8ff;--accent-on:#fff}
:root[data-accent=pino]{--accent-l:#1f6b4a;--accent-d:#56b88c;--accent-on:#fff}
:root[data-accent=bordo]{--accent-l:#9a2f3a;--accent-d:#e98a92;--accent-on:#fff}
:root[data-accent=grafito]{--accent-l:var(--ink);--accent-d:var(--ink);--accent-on:var(--bg)}
/* ---- temas ---- */
:root[data-theme=claro]{--bg:#fff;--surface:#f5f6f7;--ink:#14171a;--ink-2:#555a61;--line:#e7e8eb;--rule:#14171a;--focus:var(--accent)}
:root[data-theme=tintado]{--bg:#eef0f4;--surface:#fff;--ink:#16191d;--ink-2:#525862;--line:#dde0e6;--rule:#16191d;--focus:var(--accent)}
:root[data-theme=oscuro]{--bg:#0e0f12;--surface:#181b21;--ink:#e9ebee;--ink-2:#a3a9b1;--line:#262a31;--rule:#e9ebee;--focus:var(--accent);--accent:var(--accent-d)}
:root[data-theme=color]{--bg:#fff;--surface:#f5f6f7;--ink:#14171a;--ink-2:#555a61;--line:#e7e8eb;--rule:transparent;--focus:var(--accent)}
*{box-sizing:border-box;margin:0;padding:0}
html{font-size:100%}
body{background:var(--bg);color:var(--ink);
  font-family:"Hanken Grotesk",system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:var(--t-base);line-height:1.5;-webkit-font-smoothing:antialiased;
  font-kerning:normal;text-rendering:optimizeLegibility;transition:background .2s var(--ease),color .2s var(--ease)}
.tnum{font-variant-numeric:tabular-nums}
a{color:inherit;text-decoration:none}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px;border-radius:3px}
::selection{background:var(--accent);color:var(--accent-on)}
.skip{position:absolute;left:-9999px;top:0;background:var(--ink);color:var(--bg);padding:10px 16px;z-index:50;font-weight:600}
.skip:focus{left:16px;top:16px}
.wrap{max-width:1080px;margin:0 auto;padding:0 var(--pad) 96px}
header{position:sticky;top:0;z-index:var(--z-sticky);background:var(--bg);padding:30px 0 0;
  transition:background .2s var(--ease)}
.htop{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap}
h1{font-size:var(--t-lg);font-weight:800;letter-spacing:-.03em;text-wrap:balance}
.upd{color:var(--ink-2);font-size:var(--t-xs);white-space:nowrap}
.summary{color:var(--ink-2);font-size:var(--t-md);margin-top:10px;max-width:60ch;text-wrap:pretty;line-height:1.45}
.summary b{color:var(--ink);font-weight:700}
.zones{display:flex;gap:22px;margin-top:18px}
.zones button{font-size:var(--t-sm);font-weight:600;color:var(--ink-2);padding:2px 0;border-bottom:2px solid transparent;transition:color .15s var(--ease)}
.zones button:hover{color:var(--ink)}
.zones button[aria-pressed=true]{color:var(--accent);border-color:var(--accent)}
.rule{height:2px;background:var(--rule);margin-top:14px}
nav{display:flex;gap:30px;border-bottom:1px solid var(--line)}
nav button{font-size:var(--t-md);font-weight:600;color:var(--ink-2);padding:14px 0;margin-bottom:-1px;border-bottom:2px solid transparent;transition:color .15s var(--ease)}
nav button:hover{color:var(--ink)}
nav button[aria-selected=true]{color:var(--accent);border-color:var(--accent);font-weight:700}
.controls{display:flex;gap:14px 22px;flex-wrap:wrap;align-items:center;margin:26px 0 6px}
.search{flex:1;min-width:230px}
.search input{width:100%;border:0;border-bottom:1.5px solid var(--line);background:none;outline:0;color:var(--ink);padding:9px 0;font-size:var(--t-base);font-family:inherit;transition:border-color .15s var(--ease)}
.search input::placeholder{color:var(--ink-2)}
.search input:focus{border-color:var(--accent)}
.toggles{display:flex;gap:8px;flex-wrap:wrap}
.chip{border:1px solid var(--line);color:var(--ink);padding:7px 15px;border-radius:999px;font-size:var(--t-sm);font-weight:600;min-height:36px;transition:background .15s var(--ease),color .15s var(--ease),border-color .15s var(--ease)}
.chip:hover{border-color:var(--ink-2)}
.chip[aria-pressed=true]{background:var(--accent);color:var(--accent-on);border-color:var(--accent)}
.sortwrap{position:relative;display:flex;align-items:center}
select{border:0;border-bottom:1.5px solid var(--line);background:none;color:var(--ink);padding:9px 22px 9px 0;font-size:var(--t-sm);font-weight:600;font-family:inherit;-webkit-appearance:none;appearance:none;cursor:pointer}
select:focus{border-color:var(--accent)}
.sortwrap::after{content:"";position:absolute;right:6px;top:50%;width:7px;height:7px;border-right:1.5px solid var(--ink-2);border-bottom:1.5px solid var(--ink-2);transform:translateY(-70%) rotate(45deg);pointer-events:none}
.barrow{display:flex;justify-content:space-between;align-items:center;gap:14px 28px;flex-wrap:wrap;margin-top:16px}
.sortbar{display:flex;align-items:center;gap:2px}
.sortbar .lbl{font-size:var(--t-sm);color:var(--ink-2);margin-right:8px}
.sortbar button{padding:5px 11px;border-radius:999px;font-size:var(--t-sm);font-weight:600;color:var(--ink-2);
  transition:color .15s var(--ease),background .15s var(--ease)}
.sortbar button:hover{color:var(--ink)}
.sortbar button[aria-pressed=true]{color:var(--accent-on);background:var(--accent)}
.count{color:var(--ink-2);font-size:var(--t-sm);margin:18px 0 2px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 44px}
@media(max-width:680px){.grid{grid-template-columns:1fr}.wrap{padding:0 20px 80px;--pad:20px}}
.item{display:block;border-top:1px solid var(--line);padding:18px 14px;margin:0 -14px;transition:background .15s var(--ease)}
.item:hover{background:var(--surface)}
.item .price{font-size:var(--t-lg);font-weight:800;letter-spacing:-.02em;line-height:1.05}
.item .addr{font-size:var(--t-md);font-weight:600;margin-top:8px}
.item .meta{color:var(--ink-2);font-size:var(--t-sm);margin-top:5px}
.item .foot{display:flex;justify-content:space-between;align-items:baseline;margin-top:13px}
.item .cta{font-size:var(--t-sm);font-weight:600;color:var(--accent)}
.item .cta .arr{display:inline-block;transition:transform .15s var(--ease)}
.item:hover .cta .arr{transform:translateX(3px)}
.item:hover .cta{text-decoration:underline;text-underline-offset:3px}
.item .when{color:var(--ink-2);font-size:var(--t-xs)}
.ev{border-top:1px solid var(--line);padding:18px 0}
.ev:first-child{border-top:0}
.ev .top{display:flex;justify-content:space-between;align-items:baseline;gap:10px}
.ev .tag{font-size:var(--t-sm);font-weight:700}
.ev .when{color:var(--ink-2);font-size:var(--t-xs);white-space:nowrap}
.ev .t{font-weight:600;font-size:var(--t-md);margin-top:7px}
.ev .strike{text-decoration:line-through;color:var(--ink-2)}
.ev .efoot{color:var(--ink-2);font-size:var(--t-sm);margin-top:8px}
.ev .efoot a{font-weight:600;color:var(--accent)}
.ev .efoot a:hover{text-decoration:underline;text-underline-offset:3px}
.more{display:block;width:100%;margin:30px 0 0;padding:15px;border-top:1.5px solid var(--ink);border-bottom:1.5px solid var(--ink);color:var(--ink);font-weight:700;font-size:var(--t-sm);transition:background .15s var(--ease)}
.more:hover{background:var(--surface)}
.empty{border-top:1px solid var(--line);padding:60px 0 20px;color:var(--ink-2);max-width:46ch}
.empty b{color:var(--ink);font-weight:700;display:block;margin-bottom:6px;font-size:var(--t-md)}
.agrow{display:grid;grid-template-columns:1fr auto;align-items:baseline;gap:18px;border-top:1px solid var(--line);padding:15px 0}
.agrow .nm{font-weight:600;font-size:var(--t-md)}
.agrow .sub{color:var(--ink-2);font-size:var(--t-sm);margin-top:2px}
.agrow .n{font-weight:800;font-size:var(--t-lg);letter-spacing:-.02em}
/* ---- tema "color": franja de header con el acento ---- */
:root[data-theme=color] header{background:var(--accent);margin:0 calc(-1*var(--pad));padding:22px var(--pad) 0}
:root[data-theme=color] header h1,:root[data-theme=color] header .summary b,:root[data-theme=color] header .upd{color:var(--accent-on)}
:root[data-theme=color] header .summary{color:var(--accent-on);opacity:.88}
:root[data-theme=color] .zones button{color:rgba(255,255,255,.72)}
:root[data-theme=color] .zones button[aria-pressed=true]{color:#fff;border-color:#fff}
:root[data-theme=color] nav{border-bottom-color:rgba(255,255,255,.28)}
:root[data-theme=color] nav button{color:rgba(255,255,255,.72)}
:root[data-theme=color] nav button[aria-selected=true]{color:#fff;border-color:#fff}
:root[data-theme=color][data-accent=grafito] .zones button,:root[data-theme=color][data-accent=grafito] nav button{color:rgba(255,255,255,.72)}
/* ---- forma "suave": tarjetas blandas redondeadas, menos rejilla dura ---- */
:root[data-shape=suave] .grid{gap:12px}
:root[data-shape=suave] .item{border-top:0;background:var(--surface);border-radius:16px;padding:18px 20px;margin:0;
  box-shadow:0 1px 2px rgba(20,23,26,.04)}
:root[data-shape=suave] .item:hover{background:var(--surface);transform:translateY(-2px);box-shadow:0 8px 24px rgba(20,23,26,.09)}
:root[data-shape=suave] .search input{border:1px solid var(--line);border-radius:14px;background:var(--surface);padding:12px 16px}
:root[data-shape=suave] .search input:focus{border-color:var(--accent)}
:root[data-shape=suave] .ev{border-top:0;background:var(--surface);border-radius:16px;padding:16px 20px;margin-bottom:10px;
  box-shadow:0 1px 2px rgba(20,23,26,.04)}
:root[data-shape=suave] .ev:first-child{border-top:0}
:root[data-shape=suave] .agrow{border-top:0;background:var(--surface);border-radius:14px;padding:14px 18px;margin-bottom:8px}
:root[data-shape=suave] .more{border:1px solid var(--line);border-radius:14px}
:root[data-theme=oscuro][data-shape=suave] .item,:root[data-theme=oscuro][data-shape=suave] .ev,
:root[data-theme=oscuro][data-shape=suave] .agrow{box-shadow:none;border:1px solid var(--line)}
:root[data-theme=claro][data-shape=suave] .item,:root[data-theme=claro][data-shape=suave] .ev{box-shadow:0 1px 3px rgba(20,23,26,.05)}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}
  :root[data-shape=suave] .item:hover{transform:none}}
/* ---- favoritas / descartadas ---- */
.item{position:relative}
.cardlink{display:block;color:inherit}
.item .price{padding-right:78px}
.acts{position:absolute;top:16px;right:16px;display:flex;gap:6px;z-index:2}
.act{width:33px;height:33px;border-radius:9px;border:1px solid var(--line);background:var(--bg);color:var(--ink-2);
  font-size:.95rem;line-height:1;display:grid;place-items:center;transition:color .15s var(--ease),border-color .15s var(--ease),background .15s var(--ease)}
.act:hover{color:var(--ink);border-color:var(--ink-2)}
.act.on{background:var(--accent);color:var(--accent-on);border-color:var(--accent)}
:root[data-accent=grafito] .act.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.subtabs{display:flex;gap:20px;margin:18px 0 0;border-bottom:1px solid var(--line)}
.subtabs button{font-size:var(--t-sm);font-weight:600;color:var(--ink-2);padding:10px 0;margin-bottom:-1px;
  border-bottom:2px solid transparent}
.subtabs button[aria-pressed=true]{color:var(--ink);border-color:var(--accent)}
.subtabs .b{color:var(--ink-2);font-weight:700}
.viewtoggle{display:inline-flex;border:1px solid var(--line);border-radius:11px;overflow:hidden;flex-shrink:0}
.viewtoggle button{padding:9px 16px;font-size:var(--t-sm);font-weight:600;color:var(--ink-2)}
.viewtoggle button[aria-pressed=true]{background:var(--ink);color:var(--bg)}
.searchrow{display:flex;gap:12px;align-items:center}
.searchrow .search{flex:1}
.map{height:600px;width:100%;border-radius:16px;overflow:hidden;border:1px solid var(--line);margin-top:8px;background:var(--surface)}
.leaflet-popup-content-wrapper{border-radius:12px}
.leaflet-popup-content{font-family:inherit;font-size:.9rem;line-height:1.45;margin:12px 14px}
.leaflet-popup-content b{font-size:1.05rem}
.leaflet-popup-content a{color:#1d4ed8;font-weight:700;text-decoration:none}
.popacts{display:flex;gap:6px;margin-top:9px}
.popacts button{flex:1;padding:7px 8px;border-radius:8px;border:1px solid #d2d4d8;background:#fff;
  color:#16191d;font-size:.78rem;font-weight:700;cursor:pointer}
.popacts button:hover{background:#f2f3f5}
.mk{background:var(--ink);color:var(--bg);border-radius:13px;padding:3px 8px;font-size:.74rem;font-weight:800;
  white-space:nowrap;box-shadow:0 1px 4px rgba(0,0,0,.3);border:1.5px solid var(--bg)}
.mk.fav{background:var(--accent);color:var(--accent-on)}
:root[data-accent=grafito] .mk.fav{background:#1f6b4a;color:#fff}
</style></head><body>
<a class="skip" href="#main">Saltar al contenido</a>
<div class="wrap">
<header>
 <div class="htop"><h1>Radar Inmobiliario</h1><span class="upd" id="upd"></span></div>
 <p class="summary" id="summary"></p>
 <div class="zones" id="zones" role="group" aria-label="Zona"></div>
 <div class="rule"></div>
 <nav id="tabs" role="tablist" aria-label="Secciones">
   <button role="tab" data-tab="props" aria-selected="true">Propiedades</button>
   <button role="tab" data-tab="news" aria-selected="false">Novedades</button>
   <button role="tab" data-tab="ag" aria-selected="false">Inmobiliarias</button>
 </nav>
</header>
<main id="main"><div id="view" aria-live="polite"></div></main>
</div>
<script>
const D = __DATA__;
const SRC = {argenprop:"ArgenProp", remax:"RE/MAX", tokko:"Inmobiliaria", buscadorprop:"BuscadorProp", zonaprop:"ZonaProp", web:"Inmobiliaria"};
const EV = {propiedad_nueva:"Propiedad nueva", baja_precio:"Bajó de precio",
 suba_precio:"Subió de precio", inmobiliaria_nueva:"Inmobiliaria nueva",
 propiedad_dada_de_baja:"Dada de baja"};
const st = {zone: D.zones[0]||null, tab:"props", q:"", srcs:new Set(), sort:"recent", types:new Set(), show:24, view:"activas", map:false};

// ---- Marcas (favoritas/descartadas) ----
// Por defecto se guardan en ESTE navegador (localStorage). Si querés sincronizar
// entre dispositivos, completá SUPA con tu proyecto Supabase (URL + key pública)
// y creá la tabla radar_marks: pasa solo a cambiar estas 2 líneas.
const SUPA = {url:"https://zvcledihvvfuleobgkjr.supabase.co", key:"sb_publishable_YvMVRTmYiIWSx5-dBzQ5sQ_tkMPmtxx"};
let MARKS = {};
function _lsLoad(){ try{ return JSON.parse(localStorage.getItem("radar-marks")||"{}"); }catch(e){ return {}; } }
function _lsSave(){ try{ localStorage.setItem("radar-marks", JSON.stringify(MARKS)); }catch(e){} }
async function loadMarks(){
  if(SUPA.url){ try{
    const r=await fetch(SUPA.url+"/rest/v1/radar_marks?select=uid,state",
      {headers:{apikey:SUPA.key, Authorization:"Bearer "+SUPA.key}});
    const rows=await r.json(); MARKS={}; rows.forEach(x=>MARKS[x.uid]=x.state); return;
  }catch(e){} }
  MARKS=_lsLoad();
}
async function setMark(id, state){
  if(state) MARKS[id]=state; else delete MARKS[id];
  if(SUPA.url){ try{
    const h={apikey:SUPA.key, Authorization:"Bearer "+SUPA.key, "Content-Type":"application/json"};
    if(state) await fetch(SUPA.url+"/rest/v1/radar_marks",
      {method:"POST", headers:{...h, Prefer:"resolution=merge-duplicates"}, body:JSON.stringify({uid:id,state})});
    else await fetch(SUPA.url+"/rest/v1/radar_marks?uid=eq."+encodeURIComponent(id),
      {method:"DELETE", headers:h});
  }catch(e){ _lsSave(); } }
  else _lsSave();
}
function markOf(id){ return MARKS[id]; }
async function markFromMap(id, kind){
  const cur=markOf(id);
  if(kind=="fav") await setMark(id, cur=="fav"?null:"fav");
  else await setMark(id, cur=="discard"?null:"discard");
  render();
}

function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");}
function money(p,c){ if(p==null) return "Consultar"; return (c||"")+" "+Math.round(p).toLocaleString("es-AR"); }
function rel(iso){ if(!iso) return ""; const d=new Date(iso), s=(Date.now()-d)/1000;
 if(s<0) return "recién"; if(s<3600) return "hace "+Math.max(1,Math.floor(s/60))+" min";
 if(s<86400) return "hace "+Math.floor(s/3600)+" h"; const dd=Math.floor(s/86400);
 if(dd==1) return "ayer"; if(dd<30) return "hace "+dd+" días";
 return d.toLocaleDateString("es-AR",{day:"numeric",month:"short"}); }
function inZone(z){ return st.zone? (z||[]).includes(st.zone) : true; }

function fListings(){ let a=D.listings.filter(x=>inZone(x.zones));
 if(st.q){const q=st.q.toLowerCase(); a=a.filter(x=>(x.addr+" "+(x.title||"")+" "+(x.ag||"")).toLowerCase().includes(q));}
 if(st.srcs.size) a=a.filter(x=>st.srcs.has(x.src));
 if(st.view=="fav") a=a.filter(x=>markOf(x.id)=="fav");
 else if(st.view=="descartadas") a=a.filter(x=>markOf(x.id)=="discard");
 else a=a.filter(x=>markOf(x.id)!="discard");   // activas: ocultar descartadas
 if(st.sort=="recent") a.sort((p,q)=>(q.ts||"").localeCompare(p.ts||""));
 else a.sort((p,q)=>{const pv=p.price??1e15,qv=q.price??1e15; return st.sort=="asc"?pv-qv:qv-pv;});
 return a; }
function fEvents(){ let a=D.events.filter(x=>inZone(x.zones));
 if(st.types.size) a=a.filter(x=>st.types.has(x.type)); return a.slice(0,200); }

function renderHead(){
 document.getElementById("upd").textContent = D.updated? "Actualizado "+rel(D.updated):"";
 const ls=D.listings.filter(x=>inZone(x.zones));
 const ags=new Set(ls.map(x=>x.ag||x.src)).size;
 const wk=Date.now()-7*864e5; const nw=D.events.filter(x=>inZone(x.zones)&&new Date(x.ts)>=wk).length;
 const lugar = st.zone? (D.zoneShort.find((s,i)=>D.zones[i]===st.zone)||"tu zona") : "Banfield y Lomas";
 document.getElementById("summary").innerHTML =
  `Vigilando <b class="tnum">${ls.length}</b> casas en ${esc(lugar)}, de <b class="tnum">${ags}</b> `+
  `inmobiliarias. <b class="tnum">${nw}</b> ${nw==1?"novedad":"novedades"} en los últimos 7 días.`;
}

function item(x){ const meta=[x.beds?(x.beds+" amb"):"", x.ag||"", SRC[x.src]||x.src].filter(Boolean).join("  ·  ");
 const lbl=esc(money(x.price,x.cur)+" — "+(x.addr||"propiedad")+", ver aviso");
 const mk=markOf(x.id);
 return `<div class="item" data-id="${esc(x.id)}">
   <a class="cardlink" href="${esc(x.url)}" target="_blank" rel="noopener" aria-label="${lbl}">
     <div class="price tnum">${money(x.price,x.cur)}</div>
     <div class="addr">${esc(x.addr)||"—"}</div><div class="meta">${esc(meta)}</div>
     <div class="foot"><span class="cta">Ver aviso <span class="arr" aria-hidden="true">→</span></span>
     <span class="when">${rel(x.ts)}</span></div></a>
   <div class="acts">
     <button class="act ${mk=='fav'?'on':''}" data-fav="${esc(x.id)}" aria-pressed="${mk=='fav'}" aria-label="${mk=='fav'?'Quitar de favoritas':'Marcar favorita'}" title="Favorita">★</button>
     <button class="act ${mk=='discard'?'on':''}" data-dis="${esc(x.id)}" aria-pressed="${mk=='discard'}" aria-label="${mk=='discard'?'Restaurar':'Descartar'}" title="${mk=='discard'?'Restaurar':'Descartar'}">${mk=='discard'?'↩':'✕'}</button>
   </div></div>`; }

function viewProps(){
 const zoneSet=D.listings.filter(x=>inZone(x.zones));
 const favN=zoneSet.filter(x=>markOf(x.id)=="fav").length;
 const discN=zoneSet.filter(x=>markOf(x.id)=="discard").length;
 const a=fListings(); const v=a.slice(0,st.show);
 const ch=Object.keys(SRC).map(k=>`<button class="chip" data-src="${k}" aria-pressed="${st.srcs.has(k)}">${SRC[k]}</button>`).join("");
 const so=(val,l)=>`<button data-sort="${val}" aria-pressed="${st.sort==val}">${l}</button>`;
 const sv=(val,l)=>`<button data-view="${val}" aria-pressed="${st.view==val}">${l}</button>`;
 let h=`<div class="searchrow">
   <div class="search"><input id="q" type="search" aria-label="Buscar por calle, barrio o inmobiliaria" placeholder="Buscar por calle, barrio o inmobiliaria" value="${esc(st.q)}"></div>
   <div class="viewtoggle" role="group" aria-label="Vista">
     <button data-map="0" aria-pressed="${!st.map}">Lista</button><button data-map="1" aria-pressed="${st.map}">Mapa</button>
   </div>
 </div>
 <div class="subtabs" role="group" aria-label="Mostrar">
   ${sv("activas","Activas")}${sv("fav","Favoritas <span class='b'>"+favN+"</span>")}${sv("descartadas","Descartadas <span class='b'>"+discN+"</span>")}
 </div>
 <div class="barrow">
   <div class="toggles" role="group" aria-label="Filtrar por fuente">${ch}</div>
   <div class="sortbar" role="group" aria-label="Ordenar por">
     <span class="lbl">Ordenar</span>${so("recent","Recientes")}${so("asc","Menor precio")}${so("desc","Mayor precio")}
   </div>
 </div><p class="count">${a.length} ${a.length==1?"casa":"casas"}${st.srcs.size||st.q?" · filtrado":""}</p>`;
 if(st.map){
   const conPin=a.filter(x=>x.lat&&x.lon).length;
   return h+`<div id="map" class="map" role="application" aria-label="Mapa de propiedades"></div>`+
     `<p class="count" style="margin-top:10px">${conPin} de ${a.length} con ubicación en el mapa</p>`;
 }
 if(!a.length){
   const msg = st.view=="fav" ? "Todavía no marcaste ninguna favorita. Tocá la ★ en una casa."
     : st.view=="descartadas" ? "No descartaste ninguna casa todavía."
     : "No hay casas con esos filtros. Probá quitar un filtro o cambiar la búsqueda.";
   return h+`<div class="empty"><b>Sin resultados.</b>${msg}</div>`;
 }
 h += `<div class="grid">${v.map(item).join("")}</div>`;
 if(a.length>st.show) h+=`<button class="more" id="more">Ver ${Math.min(24,a.length-st.show)} más · quedan ${a.length-st.show}</button>`;
 return h; }

function initMap(){
 const el=document.getElementById("map"); if(!el||!window.L) return;
 const a=fListings().filter(x=>x.lat&&x.lon);
 const map=L.map(el,{scrollWheelZoom:false});
 const dark = document.documentElement.getAttribute("data-theme")=="oscuro";
 L.tileLayer(dark
   ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"
   : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
   {maxZoom:20, subdomains:"abcd", attribution:"© OpenStreetMap, © CARTO"}).addTo(map);
 // límite de la zona
 const zi=D.zones.indexOf(st.zone); const poly=zi>=0?(D.polys[zi]||[]):[];
 if(poly.length){ L.polygon(poly,{color:"#56b88c",weight:2,fillColor:"#56b88c",fillOpacity:.07}).addTo(map); }
 const pts=[];
 a.forEach(x=>{ const mk=markOf(x.id);
   const m=L.circleMarker([x.lat,x.lon],{radius:7, weight:2,
     color: dark?"#0e0f12":"#fff",
     fillColor: mk=='fav'?"#56b88c":(dark?"#e9ebee":"#16191d"),
     fillOpacity:1}).addTo(map);
   m.bindPopup(`<b>${money(x.price,x.cur)}</b><br>${esc(x.addr||"")}<br>`+
     `<span style="color:#888">${esc(x.ag||SRC[x.src]||"")}</span><br>`+
     `<a href="${esc(x.url)}" target="_blank" rel="noopener">Ver aviso →</a>`+
     `<div class="popacts">`+
       `<button onclick="markFromMap('${x.id}','fav')">${mk=='fav'?'★ Favorita':'☆ Favorita'}</button>`+
       `<button onclick="markFromMap('${x.id}','discard')">${mk=='discard'?'↩ Restaurar':'✕ Descartar'}</button>`+
     `</div>`);
   pts.push([x.lat,x.lon]); });
 if(pts.length) map.fitBounds(pts,{padding:[40,40],maxZoom:16});
 else if(poly.length) map.fitBounds(poly,{padding:[20,20]});
 else map.setView([-34.745,-58.40],14);
 setTimeout(()=>map.invalidateSize(),60);
}

function viewNews(){ const a=fEvents();
 const ch=Object.keys(EV).map(k=>`<button class="chip" data-type="${k}" aria-pressed="${st.types.has(k)}">${EV[k]}</button>`).join("");
 let h=`<div class="controls"><div class="toggles" role="group" aria-label="Filtrar por tipo">${ch}</div></div>
   <p class="count">${a.length} ${a.length==1?"novedad":"novedades"}${st.types.size?" · filtrado":""}</p>`;
 if(!a.length) return h+`<div class="empty"><b>Sin novedades en esta vista.</b>Cuando entre una casa nueva, baje un precio o aparezca una inmobiliaria, lo vas a ver acá.</div>`;
 h+=`<div>`+a.map(x=>{ let body="";
   if(x.type=="baja_precio"||x.type=="suba_precio") body=`<span class="strike tnum">${money(x.old,x.cur)}</span> &nbsp; <b class="tnum">${money(x.new,x.cur)}</b>`;
   else if(x.price!=null) body=`<b class="tnum">${money(x.price,x.cur)}</b>`;
   const f=[x.addr?esc(x.addr):"", x.url?`<a href="${esc(x.url)}" target="_blank" rel="noopener">Ver aviso →</a>`:""].filter(Boolean).join("  ·  ");
   return `<div class="ev"><div class="top"><span class="tag">${EV[x.type]||x.type}</span><span class="when">${rel(x.ts)}</span></div>
    <div class="t">${esc(x.title)||"Propiedad"}</div>${body?`<div style="margin-top:5px">${body}</div>`:""}
    ${f?`<div class="efoot">${f}</div>`:""}</div>`;}).join("")+`</div>`;
 return h; }

function viewAg(){ const ls=D.listings.filter(x=>inZone(x.zones)); const m={};
 ls.forEach(x=>{const k=(x.ag||"(sin nombre)")+"||"+x.src; m[k]=(m[k]||0)+1;});
 const rows=Object.entries(m).map(([k,n])=>({nm:k.split("||")[0],src:k.split("||")[1],n})).sort((a,b)=>b.n-a.n);
 if(!rows.length) return `<div class="empty"><b>Sin inmobiliarias en esta vista.</b></div>`;
 let h=`<p class="count">${rows.length} inmobiliarias con casas en esta vista</p><div>`;
 h+=rows.map(r=>`<div class="agrow"><div><div class="nm">${esc(r.nm)}</div><div class="sub">${SRC[r.src]||r.src}</div></div>
    <div class="n tnum">${r.n}</div></div>`).join("")+`</div>`;
 return h; }

function render(){
 renderHead();
 document.getElementById("view").innerHTML = st.tab=="props"?viewProps(): st.tab=="news"?viewNews(): viewAg();
 wire();
 if(st.tab=="props" && st.map) initMap();
}
function wire(){
 const q=document.getElementById("q"); if(q) q.oninput=e=>{st.q=e.target.value;st.show=24;const p=e.target.selectionStart;render();const n=document.getElementById("q");if(n){n.focus();n.setSelectionRange(p,p);}};
 document.querySelectorAll("[data-sort]").forEach(b=>b.onclick=()=>{st.sort=b.dataset.sort;render();});
 const mo=document.getElementById("more"); if(mo) mo.onclick=()=>{st.show+=24;render();};
 document.querySelectorAll("[data-src]").forEach(c=>c.onclick=()=>{const k=c.dataset.src;st.srcs.has(k)?st.srcs.delete(k):st.srcs.add(k);st.show=24;render();});
 document.querySelectorAll("[data-type]").forEach(c=>c.onclick=()=>{const k=c.dataset.type;st.types.has(k)?st.types.delete(k):st.types.add(k);render();});
 document.querySelectorAll("[data-view]").forEach(b=>b.onclick=()=>{st.view=b.dataset.view;st.show=24;render();});
 document.querySelectorAll("[data-map]").forEach(b=>b.onclick=()=>{st.map=b.dataset.map=="1";render();});
 document.querySelectorAll("[data-fav]").forEach(b=>b.onclick=async ev=>{ev.preventDefault();ev.stopPropagation();
   const id=b.dataset.fav; await setMark(id, markOf(id)=="fav"?null:"fav"); render();});
 document.querySelectorAll("[data-dis]").forEach(b=>b.onclick=async ev=>{ev.preventDefault();ev.stopPropagation();
   const id=b.dataset.dis; await setMark(id, markOf(id)=="discard"?null:"discard"); render();});
}
const zc=document.getElementById("zones");
const zopts=[...D.zoneShort.map((s,i)=>({lbl:s,val:D.zones[i]})),{lbl:"Toda la zona",val:null}];
zc.innerHTML=zopts.map((o,i)=>`<button data-z="${i}" aria-pressed="${o.val===st.zone}">${esc(o.lbl)}</button>`).join("");
zc.querySelectorAll("button").forEach(b=>b.onclick=()=>{st.zone=zopts[b.dataset.z].val;st.show=24;
  zc.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed", x===b));render();});
document.querySelectorAll("#tabs button").forEach(b=>b.onclick=()=>{st.tab=b.dataset.tab;
  document.querySelectorAll("#tabs button").forEach(x=>x.setAttribute("aria-selected", x===b));render();});

loadMarks().then(render);
</script></body></html>
"""

components.html(HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False)),
                height=1500, scrolling=True)
