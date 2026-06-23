"""
Scraper GENÉRICO de sitios de inmobiliarias con navegador (Playwright).

Sirve para sitios que arman las propiedades por JavaScript (SPA) y no se pueden
leer por HTTP: Puente, Brusi, etc. Renderiza la página y detecta cada tarjeta
buscando un link de ficha que tenga cerca un precio; de ahí saca precio,
dirección, tipo y localidad. Solo corre local (gated por RADAR_BROWSER).
"""
import re

from .base import Listing, parse_price, find_address

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# localidades de la zona sur (para ubicar el aviso con su localidad real)
LOCS = ["banfield", "lomas de zamora", "temperley", "llavallol", "turdera",
        "adrogue", "burzaco", "canning", "monte grande", "longchamps", "claypole",
        "glew", "rafael calzada", "remedios de escalada", "lanus", "lavallol",
        "villa centenario", "villa fiorito", "ingeniero budge"]

# JS que detecta tarjetas: links a fichas que tengan un precio cerca.
CARD_JS = r"""() => {
  const out=[], seen=new Set();
  const links=[...document.querySelectorAll('a[href]')].filter(a=>{
    const h=a.getAttribute('href')||''; return /\/(propiedad|propiedades|p|ficha|inmueble|detalle)\//i.test(h) || /\-\d{5,}/.test(h);
  });
  for(const a of links){
    let n=a, card=null;
    for(let i=0;i<6&&n;i++){ n=n.parentElement; if(n && /USD|U\$S|\$\s?\d/.test(n.innerText||'')){card=n;break;} }
    if(!card) continue;
    const href=a.getAttribute('href'); if(!href||seen.has(href))continue;
    if(/wa\.me|whatsapp|mapa|\/propiedades(\?|$)/.test(href))continue;
    seen.add(href);
    out.push({href, text:(card.innerText||'').replace(/\s*\n\s*/g,' | ').slice(0,300)});
  }
  return out;
}"""


def _detect_loc(text):
    t = text.lower()
    for l in LOCS:
        if l in t:
            return l.title()
    return "Lomas de Zamora"


def _parse(href, text, agency, base):
    m = re.search(r"(\d{5,})", href)
    if not m:
        return None, False
    sid = m.group(1)
    low = (href + " " + text).lower()
    is_casa = ("casa" in low and not re.search(
        r"departamento|\bph\b|\blote\b|terreno|\blocal\b|cochera|fondo de comercio|"
        r"galpon|oficina|duplex|monoambiente", low))
    price, cur = parse_price(text)
    segs = [s.strip() for s in text.split("|")]
    addr = find_address(segs)
    loc = _detect_loc(text + " " + href)
    url = href if href.startswith("http") else base.rstrip("/") + (
        href if href.startswith("/") else "/" + href)
    return Listing(
        source="web", source_id=f"{agency}:{sid}", url=url,
        title=f"Casa en {loc}", address=addr, price=price, currency=cur,
        agency_id=agency, agency_name=agency,
        raw={"locality": loc}), is_casa


def scrape_sites(sites, solo_casas=True, wait_ms=5500):
    """sites: lista de {name, url}. Devuelve todas las casas detectadas."""
    from playwright.sync_api import sync_playwright
    listings = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-sandbox"])
        ctx = browser.new_context(locale="es-AR", user_agent=UA,
                                  viewport={"width": 1366, "height": 1000})
        page = ctx.new_page()
        try:
            for site in sites:
                name, url = site["name"], site["url"]
                base = re.match(r"https?://[^/]+", url).group(0)
                try:
                    page.goto(url, timeout=40000, wait_until="domcontentloaded")
                    page.wait_for_timeout(wait_ms)
                    cards = page.evaluate(CARD_JS)
                except Exception as e:
                    print(f"  [web:{name}] error: {str(e)[:50]}")
                    continue
                seen, n = set(), 0
                for c in cards:
                    lst, is_casa = _parse(c["href"], c["text"], name, base)
                    if not lst or lst.source_id in seen:
                        continue
                    if solo_casas and not is_casa:
                        continue
                    seen.add(lst.source_id)
                    listings.append(lst)
                    n += 1
                print(f"  [web:{name}] {n} casas")
        finally:
            browser.close()
    return listings
