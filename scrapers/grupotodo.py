"""
Scraper genérico de sitios en la plataforma grupotodo / BuscadorProp.

Muchísimas inmobiliarias de la zona usan esta plataforma (Cassia Alfano, Palumbo,
Di Paola, Sortino, Fabián Foce, etc.). Sus sitios cargan el listado por JS, pero
la FICHA de cada propiedad trae los datos en el HTML (server-side): título con
tipo + localidad, "price": N, y la dirección. Así sacamos sus avisos DIRECTO de
cada inmobiliaria — incluso los que no estén en ArgenProp / ZonaProp / el portal.

Un scraper sirve para todas: solo cambia el dominio y el nombre.
"""
import re
import httpx
from bs4 import BeautifulSoup

from .base import Listing

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}


def _detail(client, base_url, pid, agency_name):
    try:
        html = client.get(f"{base_url}/propiedad/{pid}").text
    except Exception:
        return None, None
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text() if soup.title else "")
    parts = [p.strip() for p in title.split(" - ")]
    tipo = parts[0].lower() if parts else ""
    localidad = parts[1] if len(parts) > 1 else ""

    pm = re.search(r'"price"\s*:\s*"?([\d.]+)', html)
    price = float(pm.group(1).replace(".", "")) if pm else None
    cur = "USD" if re.search(r'(USD|U\$S|US\$)', html) else ("ARS" if price else "?")

    # dirección + localidad: "Calle 1234, Localidad" en el encabezado de la ficha
    addr = ""
    LOC = (r'(Banfield Oeste|Banfield Este|Banfield|Lomas de Zamora|Temperley|'
           r'Llavallol|Turdera|Lan[uú]s\s?\w*|Remedios de Escalada|Monte Chingolo|'
           r'Monte Grande|Saran[dí]\w*|Ingeniero Budge|Villa\s\w+)')
    am = re.search(r'([A-ZÁÉÍÓÚ][\wÁÉÍÓÚáéíóúñ.\'’ ]{2,30}\s\d{1,5})\s*,\s*' + LOC, html)
    if am:
        addr = am.group(1).strip()
        localidad = am.group(2).strip()  # localidad REAL (más confiable que el título)

    bm = re.search(r'(\d+)\s*[Dd]ormitorio', html) or re.search(r'(\d+)\s*[Aa]mbiente', html)
    beds = int(bm.group(1)) if bm else None

    return Listing(
        source="grupotodo",
        source_id=f"{agency_name}:{pid}",
        url=f"{base_url}/propiedad/{pid}",
        title=f"{tipo.title()} en {localidad}".strip() or "Propiedad",
        address=addr,
        price=price, currency=cur, bedrooms=beds,
        agency_id=agency_name, agency_name=agency_name,
        raw={"locality": localidad, "tipo": tipo}), tipo


def _enumerar_ids(base_url, max_scrolls=60):
    """El listado es scroll infinito por JS: usamos el navegador para bajar todos
    los IDs de propiedad. (Las fichas después se bajan rápido con httpx.)"""
    from playwright.sync_api import sync_playwright
    ids = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        pg = b.new_context(locale="es-AR", user_agent=HEADERS["User-Agent"],
                           viewport={"width": 1366, "height": 1000}).new_page()
        try:
            pg.goto(base_url + "/propiedades", timeout=45000, wait_until="domcontentloaded")
            pg.wait_for_timeout(2500)
            prev = -1
            for i in range(max_scrolls):
                pg.mouse.wheel(0, 5000)
                pg.wait_for_timeout(650)
                cur = pg.content()
                n = len(set(re.findall(r'/propiedad/(\d+)', cur)))
                if n == prev and i > 3:
                    break
                prev = n
            ids = list(dict.fromkeys(re.findall(r'/propiedad/(\d+)', pg.content())))
        except Exception as e:
            print(f"  [grupotodo] error enumerando ({str(e)[:50]})")
        finally:
            b.close()
    return ids


def scrape_site(base_url, agency_name, solo_casas=True, client=None, max_props=400):
    base_url = base_url.rstrip("/")
    own = client is None
    if own:
        client = httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
    listings = []
    try:
        ids = _enumerar_ids(base_url)[:max_props]
        for pid in ids:
            lst, tipo = _detail(client, base_url, pid, agency_name)
            if not lst:
                continue
            if solo_casas and tipo and "casa" not in tipo:
                continue
            listings.append(lst)
        print(f"  [grupotodo:{agency_name}] {len(listings)} casas (de {len(ids)} propiedades)")
    finally:
        if own:
            client.close()
    return listings
