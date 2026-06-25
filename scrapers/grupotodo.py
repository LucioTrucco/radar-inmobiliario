"""
Scraper genérico de sitios en la plataforma grupotodo / BuscadorProp.

Muchísimas inmobiliarias de la zona usan esta plataforma (Cassia Alfano, Palumbo,
Di Paola, Sortino, Fabián Foce, etc.). El listado es scroll-infinito por JS, pero
una vez renderizado, CADA tarjeta ya trae todo: tipo, dirección + localidad y
precio. Así sacamos sus avisos DIRECTO de cada inmobiliaria — incluso los que no
estén en ArgenProp / ZonaProp / el portal — en una sola pasada de navegador
(sin bajar ficha por ficha).

Un scraper sirve para todas: solo cambia el dominio y el nombre.
"""
import re

from .base import Listing

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# Localidades que nos interesan (partido de Lomas de Zamora y alrededores cercanos).
# Las de otros lados (Lanús, costa, etc.) las descartamos para no inflar la base.
ZONA_LOCS = re.compile(r'banfield|lomas de zamora|temperley|llavallol|turdera|'
                       r'ingeniero budge|villa centenario|villa fiorito', re.I)
PRICE_RE = re.compile(r'(USD|U\$S|US\$|\$)\s?([\d.]{3,})')


def _parse_card(text, href, agency_name):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) < 3:
        return None, ""
    op_tipo = lines[0].lower()                 # ej: "VENTA CASAS" / "ALQUILER DEPARTAMENTOS"
    # dirección + localidad: la línea con "Calle 1234, Localidad"
    addr, localidad = "", ""
    for l in lines[1:4]:
        if "," in l and re.search(r'\d', l):
            partes = l.rsplit(",", 1)
            addr, localidad = partes[0].strip(), partes[1].strip()
            break
    price, cur = None, "?"
    for l in lines:
        m = PRICE_RE.search(l)
        if m:
            cur = "USD" if m.group(1).upper() in ("USD", "U$S", "US$") else "ARS"
            price = float(m.group(2).replace(".", ""))
            break
    bm = re.search(r'(\d+)\s*[Dd]ormitorio', text)
    tipo = "casa" if "casa" in op_tipo else ("otro" if op_tipo else "")
    venta = "venta" in op_tipo or "venta" not in op_tipo and "alquiler" not in op_tipo
    m = re.search(r'/propiedad/(\d+)', href)
    pid = m.group(1) if m else href
    return Listing(
        source="grupotodo",
        source_id=f"{agency_name}:{pid}",
        url=href if href.startswith("http") else "",
        title=f"{tipo.title()} en {localidad}".strip() or "Propiedad",
        address=addr, price=price, currency=cur,
        bedrooms=int(bm.group(1)) if bm else None,
        agency_id=agency_name, agency_name=agency_name,
        raw={"locality": localidad, "tipo": tipo, "venta": venta}), (tipo, localidad, venta)


def scrape_site(base_url, agency_name, solo_casas=True, max_scrolls=70):
    from playwright.sync_api import sync_playwright
    base_url = base_url.rstrip("/")
    listings, seen = [], set()
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        pg = b.new_context(locale="es-AR", user_agent=UA,
                           viewport={"width": 1366, "height": 1000}).new_page()
        try:
            pg.goto(base_url + "/propiedades", timeout=45000, wait_until="domcontentloaded")
            pg.wait_for_timeout(2800)
            prev = -1
            for i in range(max_scrolls):
                pg.mouse.wheel(0, 5000)
                pg.wait_for_timeout(600)
                n = len(pg.query_selector_all("a[href*='/propiedad/']"))
                if n == prev and i > 3:
                    break
                prev = n
            cards = pg.query_selector_all("a[href*='/propiedad/']")
            for card in cards:
                href = card.get_attribute("href") or ""
                if not re.search(r'/propiedad/\d+', href):
                    continue
                if href.startswith("/"):
                    href = base_url + href
                try:
                    txt = card.inner_text()
                except Exception:
                    continue
                lst, info = _parse_card(txt, href, agency_name)
                if not lst or lst.source_id in seen:
                    continue
                tipo, localidad, venta = info
                if solo_casas and tipo and tipo != "casa":
                    continue
                if not venta:
                    continue
                if localidad and not ZONA_LOCS.search(localidad):
                    continue          # de otra zona (Lanús, costa, etc.) -> descartar
                seen.add(lst.source_id)
                listings.append(lst)
            print(f"  [grupotodo:{agency_name}] {len(listings)} casas en zona (de {len(cards)} avisos)")
        except Exception as e:
            print(f"  [grupotodo:{agency_name}] error: {str(e)[:60]}")
        finally:
            b.close()
    return listings
