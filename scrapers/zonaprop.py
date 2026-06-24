"""
Scraper de ZonaProp con navegador automatizado (Playwright).

ZonaProp bloquea los pedidos HTTP normales (403) y arma la página con
JavaScript, así que usamos un navegador real headless. Funciona desde una IP
residencial (la compu del usuario); desde servidores de datacenter bloquea, por
eso solo corre localmente (gated por la variable de entorno RADAR_BROWSER).
"""
import re

from .base import Listing

BASE = "https://www.zonaprop.com.ar"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _parse_card(card, zone_name):
    did = card.get_attribute("data-id")
    if not did:
        return None
    a = card.query_selector('a[href*="/propiedades/"]')
    href = a.get_attribute("href") if a else ""

    pr = card.query_selector('[data-qa="POSTING_CARD_PRICE"]')
    ptxt = pr.inner_text() if pr else ""
    m = re.search(r'(USD|U\$S|\$)\s?([\d.]+)', ptxt)
    price = float(m.group(2).replace(".", "")) if m else None
    cur = "USD" if (m and m.group(1).upper().startswith("U")) else ("ARS" if m else "?")

    # dirección: el bloque de ubicación trae "Calle 1234\nLocalidad, Partido"
    addr, locality = "", ""
    loc = card.query_selector('[data-qa="POSTING_CARD_LOCATION"]')
    if loc:
        locality = loc.inner_text().split("\n")[0].strip()
    locblock = card.query_selector('div[class*="location-address"], div[class*="LocationAddress"]')
    if not locblock:
        for el in card.query_selector_all('div[class*="location"]'):
            t = el.inner_text()
            if re.search(r'\d', t):
                locblock = el
                break
    if locblock:
        for line in locblock.inner_text().split("\n"):
            line = line.strip()
            if re.search(r'\d', line) and "," not in line:
                addr = line
                break

    desc_el = card.query_selector('[data-qa="POSTING_CARD_DESCRIPTION"]')
    desc = desc_el.inner_text() if desc_el else ""
    feat_el = card.query_selector('[data-qa="POSTING_CARD_FEATURES"]')
    feats = feat_el.inner_text() if feat_el else ""
    dorm = re.search(r'(\d+)\s*dorm', feats)
    amb = re.search(r'(\d+)\s*amb', feats)

    # tipo: solo casas (la categoría ya es casas, pero filtramos PH/depto colados)
    tipo = "casa"
    low = (desc + " " + href).lower()
    if re.search(r'\bdepartamento\b|\bph\b|\blote\b|\bterreno\b|\blocal\b|\bcochera\b', low) \
            and "casa" not in low:
        tipo = "otro"

    return Listing(
        source="zonaprop",
        source_id=str(did),
        url=BASE + href if href.startswith("/") else href,
        title=desc[:80] or f"Casa en {locality}",
        address=addr,
        price=price, currency=cur,
        bedrooms=int(dorm.group(1)) if dorm else None,
        rooms=int(amb.group(1)) if amb else None,
        zone=zone_name,
        agency_id=None, agency_name=None,
        raw={"locality": locality.split(",")[0], "tipo": tipo}), tipo


STEALTH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'languages', {get: () => ['es-AR','es']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.chrome = {runtime: {}};
"""


def _load(page, url, delay_ms):
    """Carga una página manejando el desafío 'Un momento…' de Cloudflare.
    No recarga (eso re-gatilla el desafío): espera a que Cloudflare se resuelva
    solo en la misma página. Devuelve True si aparecieron las tarjetas."""
    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
    except Exception:
        return False
    for _ in range(4):
        try:
            page.wait_for_selector('[data-qa="posting PROPERTY"]', timeout=12000)
            page.wait_for_timeout(delay_ms)
            return True
        except Exception:
            t = page.title().lower()
            if "moment" in t or "momento" in t or "robot" in t or "verif" in t:
                page.wait_for_timeout(7000)   # dejar que Cloudflare resuelva en el lugar
                continue
            return False
    return False


def scrape(zone_slug="casas-venta-banfield", zone_name="Banfield",
           max_pages=45, delay_ms=2200, solo_casas=True, headful=False):
    """headful=True muestra el navegador (para ver cómo trabaja); por defecto va
    invisible (más rápido y no tapa la pantalla)."""
    import os
    import random
    from playwright.sync_api import sync_playwright
    headful = headful or bool(os.environ.get("RADAR_HEADFUL"))
    listings, seen = [], set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful, args=[
            "--disable-blink-features=AutomationControlled", "--no-sandbox"])
        ctx = browser.new_context(
            locale="es-AR", timezone_id="America/Argentina/Buenos_Aires",
            user_agent=UA, viewport={"width": 1366, "height": 900})
        ctx.add_init_script(STEALTH)
        page = ctx.new_page()
        try:
            for n in range(1, max_pages + 1):
                url = (f"{BASE}/{zone_slug}.html" if n == 1
                       else f"{BASE}/{zone_slug}-pagina-{n}.html")
                if not _load(page, url, delay_ms):
                    print(f"  [zonaprop] pág {n}: bloqueada/sin tarjetas, corto acá")
                    break
                cards = page.query_selector_all('[data-qa="posting PROPERTY"]')
                if not cards:
                    break
                new = 0
                for card in cards:
                    res = _parse_card(card, zone_name)
                    if not res:
                        continue
                    lst, tipo = res
                    if lst.source_id in seen:
                        continue
                    if solo_casas and tipo != "casa":
                        continue
                    seen.add(lst.source_id)
                    listings.append(lst)
                    new += 1
                print(f"  [zonaprop] {zone_name} pág {n}: {new} casas")
                if new == 0:
                    break
                page.wait_for_timeout(random.randint(3500, 6000))
        finally:
            browser.close()
    return listings
