"""
Dashboard web del radar inmobiliario.

Streamlit se usa solo como "host": carga los datos de la base y renderiza una
interfaz propia (HTML/CSS/JS a medida) con control total del diseño.
Estética: minimalista monocromo (blanco/negro, tipografía fuerte, grilla).

Correr local:   streamlit run dashboard.py
En la nube:     Streamlit Community Cloud.
"""
import json
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
[data-testid="stApp"] {background:#fff;}
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

listings = load("SELECT price,currency,address,bedrooms,source,agency_name,url,"
                "first_seen,zones,title FROM listings WHERE active=1")
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
    "price": None if pd.isna(r.price) else float(r.price),
    "cur": r.currency, "addr": r.address or "",
    "beds": None if pd.isna(r.bedrooms) else int(r.bedrooms),
    "src": r.source, "ag": None if pd.isna(r.agency_name) else r.agency_name,
    "url": r.url, "ts": to_iso_ar(r.first_seen), "zones": jz(r.zones),
} for r in listings.itertuples()]

E = []
for r in events.itertuples():
    d = json.loads(r.detail) if r.detail else {}
    E.append({"type": r.type, "title": r.title or "", "ts": to_iso_ar(r.created_at),
              "zones": jz(r.l_zones), "price": d.get("price"), "cur": d.get("currency"),
              "old": d.get("old_price"), "new": d.get("new_price"),
              "addr": d.get("address"), "url": d.get("url")})

DATA = {
    "listings": L, "events": E,
    "zones": [z["name"] for z in config.WATCH_ZONES],
    "zoneShort": [z["name"].split(" (")[0] for z in config.WATCH_ZONES],
    "updated": to_iso_ar(runs.iloc[0]["finished_at"]) if not runs.empty else None,
}

HTML = r"""
<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{ --ink:#0a0a0a; --gray:#8a8a8a; --line:#e2e2e2; --rule:#0a0a0a; }
*{box-sizing:border-box;margin:0;padding:0}
html,body{background:#fff;color:var(--ink)}
body{font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;
  font-size:15px;line-height:1.4}
::selection{background:#0a0a0a;color:#fff}
a{color:inherit;text-decoration:none}
.wrap{max-width:1120px;margin:0 auto;padding:0 28px 90px}
header{position:sticky;top:0;z-index:20;background:#fff;padding:30px 0 0}
.htop{display:flex;justify-content:space-between;align-items:baseline}
h1{font-size:1.45rem;font-weight:800;letter-spacing:-.01em;text-transform:uppercase}
.upd{color:var(--gray);font-size:.66rem;text-transform:uppercase;letter-spacing:.1em}
.zones{display:flex;gap:24px;margin-top:6px}
.zones button{border:0;background:none;cursor:pointer;font-size:.72rem;font-weight:700;color:var(--gray);
  text-transform:uppercase;letter-spacing:.09em;padding:0}
.zones button.on{color:var(--ink);text-decoration:underline;text-underline-offset:5px;text-decoration-thickness:2px}
.rule{height:3px;background:var(--rule);margin-top:14px}
nav{display:flex;gap:34px;border-bottom:1px solid var(--line)}
nav button{border:0;background:none;cursor:pointer;font-size:.95rem;font-weight:700;color:var(--gray);
  padding:14px 0;margin-bottom:-1px;border-bottom:3px solid transparent;text-transform:uppercase;letter-spacing:.04em}
nav button.on{color:var(--ink);border-color:var(--ink)}
.stats{display:flex;margin:26px 0 6px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.stat{padding:16px 30px 16px 0;margin-right:30px}
.stat b{font-size:2rem;font-weight:800;letter-spacing:-.03em;display:block;line-height:1}
.stat span{color:var(--gray);font-size:.62rem;text-transform:uppercase;letter-spacing:.1em;display:block;margin-top:6px}
.controls{display:flex;gap:14px 22px;flex-wrap:wrap;align-items:center;margin:26px 0 8px}
.search{flex:1;min-width:220px}
.search input{width:100%;border:0;border-bottom:2px solid var(--ink);background:none;outline:0;color:var(--ink);
  padding:8px 0;font-size:.95rem;font-family:inherit}
.search input::placeholder{color:var(--gray);text-transform:uppercase;letter-spacing:.07em;font-size:.76rem}
.toggles{display:flex;gap:8px;flex-wrap:wrap}
.chip{border:1px solid var(--ink);background:none;color:var(--ink);padding:6px 14px;cursor:pointer;
  font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;font-family:inherit}
.chip.on{background:var(--ink);color:#fff}
select{border:0;border-bottom:2px solid var(--ink);background:none;color:var(--ink);padding:8px 16px 8px 0;
  font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;cursor:pointer;font-family:inherit;
  -webkit-appearance:none;appearance:none}
.count{color:var(--gray);font-size:.66rem;text-transform:uppercase;letter-spacing:.1em;margin:18px 0 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:0 48px;margin-top:4px}
@media(max-width:680px){.grid{grid-template-columns:1fr}.stat{padding-right:20px;margin-right:18px}.wrap{padding:0 18px 80px}}
.item{border-top:1px solid var(--line);padding:20px 0}
.item .price{font-size:1.45rem;font-weight:800;letter-spacing:-.02em;line-height:1}
.item .addr{font-size:1.02rem;font-weight:600;margin-top:9px}
.item .meta{color:var(--gray);font-size:.64rem;text-transform:uppercase;letter-spacing:.08em;margin-top:7px}
.item .foot{display:flex;justify-content:space-between;align-items:baseline;margin-top:14px}
.item .foot a{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
  text-decoration:underline;text-underline-offset:3px}
.item .foot span{color:var(--gray);font-size:.62rem;text-transform:uppercase;letter-spacing:.08em}
.ev{border-top:1px solid var(--line);padding:18px 0}
.ev .top{display:flex;justify-content:space-between;align-items:baseline}
.ev .tag{font-size:.64rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em}
.ev .when{color:var(--gray);font-size:.62rem;text-transform:uppercase;letter-spacing:.08em}
.ev .t{font-weight:600;font-size:1.05rem;margin-top:7px}
.ev .strike{text-decoration:line-through;color:var(--gray)}
.ev .efoot{color:var(--gray);font-size:.64rem;text-transform:uppercase;letter-spacing:.07em;margin-top:8px}
.ev .efoot a{text-decoration:underline;text-underline-offset:3px;font-weight:700;color:var(--ink)}
.more{display:block;width:100%;margin:32px 0 0;padding:16px;background:none;border:0;border-top:2px solid var(--ink);
  border-bottom:2px solid var(--ink);color:var(--ink);font-weight:800;cursor:pointer;font-size:.7rem;
  text-transform:uppercase;letter-spacing:.12em;font-family:inherit}
.empty{color:var(--gray);padding:70px 0;font-size:.95rem;border-top:1px solid var(--line);margin-top:4px}
.agrow{display:grid;grid-template-columns:1fr auto;align-items:baseline;gap:18px;border-top:1px solid var(--line);padding:15px 0}
.agrow .nm{font-weight:600;font-size:1.02rem}
.agrow .sub{color:var(--gray);font-size:.6rem;text-transform:uppercase;letter-spacing:.1em;margin-top:3px}
.agrow .n{font-weight:800;font-size:1.3rem;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
</style></head><body><div class="wrap">
<header>
 <div class="htop"><h1>Radar Inmobiliario</h1><span class="upd" id="upd"></span></div>
 <div class="zones" id="zones"></div>
 <div class="rule"></div>
 <nav id="tabs">
   <button data-tab="props" class="on">Propiedades</button>
   <button data-tab="news">Novedades</button>
   <button data-tab="ag">Inmobiliarias</button>
 </nav>
</header>
<div class="stats" id="stats"></div>
<div id="view"></div>
</div>
<script>
const D = __DATA__;
const SRC = {argenprop:"ArgenProp", remax:"RE/MAX", tokko:"Inmobiliaria"};
const EV = {propiedad_nueva:"Nueva", baja_precio:"Bajo de precio", suba_precio:"Subio de precio",
 inmobiliaria_nueva:"Inmobiliaria nueva", propiedad_dada_de_baja:"Dada de baja"};
const st = {zone: D.zones[0]||null, tab:"props", q:"", srcs:new Set(), sort:"recent", types:new Set(), show:24};

function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");}
function money(p,c){ if(p==null) return "Consultar"; return (c||"")+" "+Math.round(p).toLocaleString("es-AR"); }
function rel(iso){ if(!iso) return ""; const d=new Date(iso), s=(Date.now()-d)/1000;
 if(s<0) return "recien"; if(s<3600) return "hace "+Math.max(1,Math.floor(s/60))+" min";
 if(s<86400) return "hace "+Math.floor(s/3600)+" h"; const dd=Math.floor(s/86400);
 if(dd==1) return "ayer"; if(dd<30) return "hace "+dd+" dias";
 return d.toLocaleDateString("es-AR",{day:"numeric",month:"short"}); }
function inZone(z){ return st.zone? (z||[]).includes(st.zone) : true; }

function fListings(){ let a=D.listings.filter(x=>inZone(x.zones));
 if(st.q){const q=st.q.toLowerCase(); a=a.filter(x=>(x.addr+" "+(x.title||"")+" "+(x.ag||"")).toLowerCase().includes(q));}
 if(st.srcs.size) a=a.filter(x=>st.srcs.has(x.src));
 if(st.sort=="recent") a.sort((p,q)=>(q.ts||"").localeCompare(p.ts||""));
 else a.sort((p,q)=>{const pv=p.price??1e15,qv=q.price??1e15; return st.sort=="asc"?pv-qv:qv-pv;});
 return a; }
function fEvents(){ let a=D.events.filter(x=>inZone(x.zones));
 if(st.types.size) a=a.filter(x=>st.types.has(x.type)); return a.slice(0,200); }

function renderStats(){ const ls=D.listings.filter(x=>inZone(x.zones));
 const ags=new Set(ls.map(x=>x.ag||x.src+"?")).size;
 const wk=Date.now()-7*864e5; const nw=D.events.filter(x=>inZone(x.zones)&&new Date(x.ts)>=wk).length;
 document.getElementById("stats").innerHTML =
  `<div class="stat"><b>${ls.length}</b><span>Casas activas</span></div>
   <div class="stat"><b>${ags}</b><span>Inmobiliarias</span></div>
   <div class="stat"><b>${nw}</b><span>Novedades / 7 dias</span></div>`; }

function item(x){ const meta=[x.beds?(x.beds+" amb"):"", x.ag||"", SRC[x.src]||x.src].filter(Boolean).join("  /  ");
 return `<div class="item"><div class="price">${money(x.price,x.cur)}</div>
   <div class="addr">${esc(x.addr)||"—"}</div><div class="meta">${esc(meta)}</div>
   <div class="foot"><a href="${esc(x.url)}" target="_blank" rel="noopener">Ver aviso →</a><span>${rel(x.ts)}</span></div></div>`; }

function viewProps(){ const a=fListings(); const v=a.slice(0,st.show);
 const ch=Object.keys(SRC).map(k=>`<button class="chip ${st.srcs.has(k)?'on':''}" data-src="${k}">${SRC[k]}</button>`).join("");
 let h=`<div class="controls"><div class="search"><input id="q" placeholder="Buscar por calle, barrio o inmobiliaria" value="${esc(st.q)}"></div>
   <div class="toggles">${ch}</div>
   <select id="sort"><option value="recent">Mas recientes</option><option value="asc">Menor precio</option><option value="desc">Mayor precio</option></select>
 </div><div class="count">${a.length} casas${st.srcs.size||st.q?" — filtrado":""}</div>`;
 h += a.length? `<div class="grid">${v.map(item).join("")}</div>` : `<div class="empty">No hay casas con esos filtros.</div>`;
 if(a.length>st.show) h+=`<button class="more" id="more">Ver mas — ${a.length-st.show} restantes</button>`;
 return h; }

function viewNews(){ const a=fEvents();
 const ch=Object.keys(EV).map(k=>`<button class="chip ${st.types.has(k)?'on':''}" data-type="${k}">${EV[k]}</button>`).join("");
 let h=`<div class="controls"><div class="toggles">${ch}</div></div>
   <div class="count">${a.length} novedades${st.types.size?" — filtrado":" — todas"}</div>`;
 if(!a.length) return h+`<div class="empty">Sin novedades en esta vista.</div>`;
 h+=`<div style="margin-top:4px">`+a.map(x=>{ let body="";
   if(x.type=="baja_precio"||x.type=="suba_precio") body=`<span class="strike">${money(x.old,x.cur)}</span> &nbsp; <b>${money(x.new,x.cur)}</b>`;
   else if(x.price!=null) body=`<b>${money(x.price,x.cur)}</b>`;
   const f=[x.addr?esc(x.addr):"", x.url?`<a href="${esc(x.url)}" target="_blank" rel="noopener">Ver aviso →</a>`:""].filter(Boolean).join("  /  ");
   return `<div class="ev"><div class="top"><span class="tag">${EV[x.type]||x.type}</span><span class="when">${rel(x.ts)}</span></div>
    <div class="t">${esc(x.title)||"Propiedad"}</div>${body?`<div style="margin-top:5px">${body}</div>`:""}
    ${f?`<div class="efoot">${f}</div>`:""}</div>`;}).join("")+`</div>`;
 return h; }

function viewAg(){ const ls=D.listings.filter(x=>inZone(x.zones)); const m={};
 ls.forEach(x=>{const k=(x.ag||"(sin nombre)")+"||"+x.src; m[k]=(m[k]||0)+1;});
 const rows=Object.entries(m).map(([k,n])=>({nm:k.split("||")[0],src:k.split("||")[1],n})).sort((a,b)=>b.n-a.n);
 let h=`<div class="count">${rows.length} inmobiliarias con casas en esta vista</div><div style="margin-top:4px">`;
 h+=rows.map(r=>`<div class="agrow"><div><div class="nm">${esc(r.nm)}</div><div class="sub">${SRC[r.src]||r.src}</div></div>
    <div class="n">${r.n}</div></div>`).join("")+`</div>`;
 return h; }

function render(){
 document.getElementById("upd").textContent = D.updated? "Act. "+rel(D.updated):"";
 renderStats();
 document.getElementById("view").innerHTML = st.tab=="props"?viewProps(): st.tab=="news"?viewNews(): viewAg();
 wire();
}
function wire(){
 const q=document.getElementById("q"); if(q) q.oninput=e=>{st.q=e.target.value;st.show=24;const p=e.target.selectionStart;render();const n=document.getElementById("q");if(n){n.focus();n.setSelectionRange(p,p);}};
 const so=document.getElementById("sort"); if(so){so.value=st.sort;so.onchange=e=>{st.sort=e.target.value;render();};}
 const mo=document.getElementById("more"); if(mo) mo.onclick=()=>{st.show+=24;render();};
 document.querySelectorAll("[data-src]").forEach(c=>c.onclick=()=>{const k=c.dataset.src;st.srcs.has(k)?st.srcs.delete(k):st.srcs.add(k);st.show=24;render();});
 document.querySelectorAll("[data-type]").forEach(c=>c.onclick=()=>{const k=c.dataset.type;st.types.has(k)?st.types.delete(k):st.types.add(k);render();});
}
const zc=document.getElementById("zones");
const zopts=[...D.zoneShort.map((s,i)=>({lbl:s,val:D.zones[i]})),{lbl:"Toda la zona",val:null}];
zc.innerHTML=zopts.map((o,i)=>`<button data-z="${i}" class="${(o.val===st.zone)?'on':''}">${o.lbl}</button>`).join("");
zc.querySelectorAll("button").forEach(b=>b.onclick=()=>{st.zone=zopts[b.dataset.z].val;st.show=24;
  zc.querySelectorAll("button").forEach(x=>x.classList.remove("on"));b.classList.add("on");render();});
document.querySelectorAll("#tabs button").forEach(b=>b.onclick=()=>{st.tab=b.dataset.tab;
  document.querySelectorAll("#tabs button").forEach(x=>x.classList.remove("on"));b.classList.add("on");render();});
render();
</script></body></html>
"""

components.html(HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False)),
                height=1500, scrolling=True)
