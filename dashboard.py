"""
Dashboard web del radar inmobiliario.

Streamlit se usa solo como "host": carga los datos de la base y renderiza una
interfaz propia (HTML/CSS/JS a medida) con control total del diseño.

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
#MainMenu, footer, header[data-testid="stHeader"] {display:none;}
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
    "cur": r.currency, "addr": r.address or "", "beds": None if pd.isna(r.bedrooms) else int(r.bedrooms),
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
:root{
  --bg:#f4f5f7; --card:#fff; --text:#16191f; --muted:#6b7280; --line:#e7e9ee;
  --accent:#2563eb; --accentBg:#eaf0fe; --shadow:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.05);
}
@media (prefers-color-scheme: dark){:root{
  --bg:#0f1115; --card:#181b22; --text:#e8eaed; --muted:#9aa1ad; --line:#272b34;
  --accent:#6ea8fe; --accentBg:#1b2740; --shadow:0 1px 3px rgba(0,0,0,.4);}}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  background:var(--bg); color:var(--text); -webkit-font-smoothing:antialiased; font-size:15px;}
.wrap{max-width:1080px; margin:0 auto; padding:0 16px 60px;}
header{position:sticky;top:0;z-index:20;background:var(--bg);padding:18px 0 10px;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.brand h1{font-size:1.35rem;font-weight:700;letter-spacing:-.01em}
.upd{color:var(--muted);font-size:.8rem;margin-left:auto}
.stats{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 14px;box-shadow:var(--shadow)}
.stat b{font-size:1.15rem;display:block}.stat span{color:var(--muted);font-size:.75rem}
.seg{display:inline-flex;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:3px;margin-top:12px}
.seg button{border:0;background:transparent;color:var(--muted);padding:7px 16px;border-radius:8px;cursor:pointer;font-size:.9rem;font-weight:600}
.seg button.on{background:var(--accent);color:#fff}
nav{display:flex;gap:4px;margin-top:14px}
nav button{border:0;background:transparent;color:var(--muted);padding:9px 4px;margin-right:18px;cursor:pointer;font-size:1rem;font-weight:600;border-bottom:2.5px solid transparent}
nav button.on{color:var(--text);border-color:var(--accent)}
.controls{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:16px 0}
.search{flex:1;min-width:180px;display:flex;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:9px 12px;box-shadow:var(--shadow)}
.search input{border:0;outline:0;background:transparent;color:var(--text);width:100%;font-size:.92rem}
.chip{border:1px solid var(--line);background:var(--card);color:var(--muted);border-radius:20px;padding:6px 13px;cursor:pointer;font-size:.82rem;font-weight:600}
.chip.on{background:var(--accentBg);color:var(--accent);border-color:var(--accent)}
select{border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:10px;padding:8px 12px;font-size:.85rem;cursor:pointer}
.count{color:var(--muted);font-size:.82rem;margin-bottom:10px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;box-shadow:var(--shadow);transition:transform .12s,box-shadow .12s}
.card:hover{transform:translateY(-2px);box-shadow:0 6px 18px rgba(16,24,40,.10)}
.crow{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.price{font-size:1.3rem;font-weight:800;letter-spacing:-.02em}
.badge{font-size:.68rem;font-weight:700;padding:3px 9px;border-radius:20px;white-space:nowrap}
.addr{margin-top:8px;font-size:.95rem;font-weight:600}
.meta{color:var(--muted);font-size:.82rem;margin-top:3px}
.cfoot{display:flex;justify-content:space-between;align-items:center;margin-top:12px;padding-top:11px;border-top:1px solid var(--line)}
.cfoot a{color:var(--accent);text-decoration:none;font-weight:700;font-size:.85rem}
.cfoot span{color:var(--muted);font-size:.78rem}
.ev{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--muted);border-radius:12px;padding:14px 16px;margin-bottom:10px;box-shadow:var(--shadow)}
.ev .top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.ev .t{font-weight:700;margin-top:6px}
.ev .strike{text-decoration:line-through;color:var(--muted)}
.more{display:block;width:100%;margin:18px 0;padding:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;color:var(--accent);font-weight:700;cursor:pointer;font-size:.9rem}
.empty{text-align:center;color:var(--muted);padding:50px 20px}
.agrow{display:flex;align-items:center;gap:12px;padding:11px 4px;border-bottom:1px solid var(--line)}
.agrow .nm{font-weight:600;flex:1}
.bar{height:7px;border-radius:6px;background:var(--accent);min-width:7px}
.barwrap{width:130px;background:var(--line);border-radius:6px;overflow:hidden}
</style></head><body><div class="wrap">
<header>
 <div class="brand"><h1>🏠 Radar Inmobiliario</h1><div class="upd" id="upd"></div></div>
 <div class="seg" id="zoneseg"></div>
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
const SRC = {argenprop:["ArgenProp","#1d4ed8","#e7eefe"], remax:["RE/MAX","#b91c1c","#fde8e8"], tokko:["Inmobiliaria","#6d28d9","#efe9fd"]};
const EV = {
 propiedad_nueva:["🆕 Nueva","#15803d"], baja_precio:["📉 Bajó de precio","#1d4ed8"],
 suba_precio:["📈 Subió","#b45309"], inmobiliaria_nueva:["🏢 Inmobiliaria nueva","#6d28d9"],
 propiedad_dada_de_baja:["❌ Dada de baja","#6b7280"]};
const st = {zone: D.zones[0]||null, tab:"props", q:"", srcs:new Set(), sort:"recent", types:new Set(), show:24};

function money(p,c){ if(p==null) return "Consultar"; return (c||"")+" "+Math.round(p).toLocaleString("es-AR"); }
function rel(iso){ if(!iso) return ""; const d=new Date(iso), s=(Date.now()-d)/1000;
 if(s<0) return "recién"; if(s<3600) return "hace "+Math.max(1,Math.floor(s/60))+" min";
 if(s<86400) return "hace "+Math.floor(s/3600)+" h"; const dd=Math.floor(s/86400);
 if(dd==1) return "ayer"; if(dd<30) return "hace "+dd+" días";
 return d.toLocaleDateString("es-AR",{day:"numeric",month:"short"}); }
function inZone(zones){ return st.zone? (zones||[]).includes(st.zone) : true; }

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
  `<div class="stat"><b>${ls.length}</b><span>casas activas</span></div>
   <div class="stat"><b>${ags}</b><span>inmobiliarias</span></div>
   <div class="stat"><b>${nw}</b><span>novedades · 7 días</span></div>`; }

function card(x){ const s=SRC[x.src]||[x.src,"#555","#eee"];
 return `<div class="card"><div class="crow"><div class="price">${money(x.price,x.cur)}</div>
   <span class="badge" style="color:${s[1]};background:${s[2]}">${s[0]}</span></div>
   <div class="addr">📍 ${x.addr||"—"}</div>
   <div class="meta">${x.beds?("🛏 "+x.beds+" amb"):""}${x.beds&&x.ag?" · ":""}${x.ag||""}</div>
   <div class="cfoot"><a href="${x.url}" target="_blank" rel="noopener">Ver aviso ↗</a><span>${rel(x.ts)}</span></div></div>`; }

function viewProps(){ const a=fListings(); const v=a.slice(0,st.show);
 const chips=Object.keys(SRC).map(k=>`<span class="chip ${st.srcs.has(k)?'on':''}" data-src="${k}">${SRC[k][0]}</span>`).join("");
 let h=`<div class="controls">
   <div class="search">🔎<input id="q" placeholder="Buscar por calle, barrio o inmobiliaria…" value="${st.q.replace(/"/g,'&quot;')}"></div>
   ${chips}
   <select id="sort"><option value="recent">Más recientes</option><option value="asc">Menor precio</option><option value="desc">Mayor precio</option></select>
 </div><div class="count">${a.length} casas${st.srcs.size||st.q?" (filtrado)":""}</div>`;
 h += a.length? `<div class="grid">${v.map(card).join("")}</div>` : `<div class="empty">No hay casas con esos filtros.</div>`;
 if(a.length>st.show) h+=`<button class="more" id="more">Ver más (${a.length-st.show} restantes)</button>`;
 return h; }

function viewNews(){ const a=fEvents();
 const chips=Object.keys(EV).map(k=>`<span class="chip ${st.types.has(k)?'on':''}" data-type="${k}">${EV[k][0]}</span>`).join("");
 let h=`<div class="controls">${chips}</div><div class="count">${a.length} novedades${st.types.size?" (filtrado)":" · todas"}</div>`;
 if(!a.length) return h+`<div class="empty">Sin novedades en esta vista.</div>`;
 h+=a.map(x=>{const e=EV[x.type]||["•","#666"]; let body="";
   if(x.type=="baja_precio"||x.type=="suba_precio") body=`<span class="strike">${money(x.old,x.cur)}</span> &nbsp;<b>${money(x.new,x.cur)}</b>`;
   else if(x.price!=null) body=`<b>${money(x.price,x.cur)}</b>`;
   const foot=[x.addr?("📍 "+x.addr):"", x.url?`<a href="${x.url}" target="_blank" style="color:var(--accent);font-weight:700;text-decoration:none">Ver aviso ↗</a>`:""].filter(Boolean).join(" · ");
   return `<div class="ev" style="border-left-color:${e[1]}"><div class="top"><b style="color:${e[1]}">${e[0]}</b><span style="color:var(--muted);font-size:.8rem">${rel(x.ts)}</span></div>
    <div class="t">${x.title||"Propiedad"}</div>${body?`<div style="margin-top:4px">${body}</div>`:""}
    ${foot?`<div class="meta" style="margin-top:6px">${foot}</div>`:""}</div>`;}).join("");
 return h; }

function viewAg(){ const ls=D.listings.filter(x=>inZone(x.zones)); const m={};
 ls.forEach(x=>{const k=(x.ag||"(sin nombre)")+"||"+x.src; m[k]=(m[k]||0)+1;});
 const rows=Object.entries(m).map(([k,n])=>({nm:k.split("||")[0],src:k.split("||")[1],n})).sort((a,b)=>b.n-a.n);
 const mx=rows.length?rows[0].n:1;
 let h=`<div class="count">${rows.length} inmobiliarias con casas en esta vista</div>`;
 h+=rows.map(r=>{const s=SRC[r.src]||[r.src,"#555","#eee"];
   return `<div class="agrow"><span class="nm">${r.nm}</span>
    <span class="badge" style="color:${s[1]};background:${s[2]}">${s[0]}</span>
    <div class="barwrap"><div class="bar" style="width:${Math.round(r.n/mx*100)}%"></div></div>
    <b style="width:28px;text-align:right">${r.n}</b></div>`;}).join("");
 return h; }

function render(){
 document.getElementById("upd").textContent = D.updated? "actualizado "+rel(D.updated):"";
 renderStats();
 const v=document.getElementById("view");
 v.innerHTML = st.tab=="props"?viewProps(): st.tab=="news"?viewNews(): viewAg();
 wire();
}
function wire(){
 const q=document.getElementById("q"); if(q) q.oninput=e=>{st.q=e.target.value;st.show=24;const p=e.target.selectionStart;render();const n=document.getElementById("q");if(n){n.focus();n.setSelectionRange(p,p);}};
 const so=document.getElementById("sort"); if(so){so.value=st.sort;so.onchange=e=>{st.sort=e.target.value;render();};}
 const mo=document.getElementById("more"); if(mo) mo.onclick=()=>{st.show+=24;render();};
 document.querySelectorAll("[data-src]").forEach(c=>c.onclick=()=>{const k=c.dataset.src;st.srcs.has(k)?st.srcs.delete(k):st.srcs.add(k);st.show=24;render();});
 document.querySelectorAll("[data-type]").forEach(c=>c.onclick=()=>{const k=c.dataset.type;st.types.has(k)?st.types.delete(k):st.types.add(k);render();});
}
// zona
const zs=document.getElementById("zoneseg");
const zopts=[...D.zoneShort.map((s,i)=>({lbl:s,val:D.zones[i]})),{lbl:"Toda la zona",val:null}];
zs.innerHTML=zopts.map((o,i)=>`<button data-z="${i}" class="${(o.val===st.zone)?'on':''}">${o.lbl}</button>`).join("");
zs.querySelectorAll("button").forEach(b=>b.onclick=()=>{st.zone=zopts[b.dataset.z].val;st.show=24;
  zs.querySelectorAll("button").forEach(x=>x.classList.remove("on"));b.classList.add("on");render();});
// tabs
document.querySelectorAll("#tabs button").forEach(b=>b.onclick=()=>{st.tab=b.dataset.tab;
  document.querySelectorAll("#tabs button").forEach(x=>x.classList.remove("on"));b.classList.add("on");render();});
render();
</script></body></html>
"""

components.html(HTML.replace("__DATA__", json.dumps(DATA, ensure_ascii=False)),
                height=1400, scrolling=True)
