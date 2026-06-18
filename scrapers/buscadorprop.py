"""
Scraper del portal BuscadorProp (buscadorprop.com.ar).

Es un portal/agregador (como ArgenProp): junta propiedades de muchas
inmobiliarias. La página de casas en venta de Banfield está renderizada en el
HTML (precio, dirección con calle+altura, tipo), así que es scrapeable directo.
Filtramos a casas y geolocalizamos la dirección para saber si caen en la zona.
"""
import re
import httpx
from bs4 import BeautifulSoup

from .base import Listing, parse_price, find_card

BASE = "https://www.buscadorprop.com.ar"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept-Language": "es-AR,es;q=0.9"}
# tipos que NO son casa -> los descartamos
NO_CASA = re.compile(r'\bdepartamento\b|\bdpto\b|monoambiente|\bph\b|\blocal\b|'
                     r'\bterreno\b|\blote\b|\boficina\b|\bcochera\b|fondo de comercio', re.I)
# dirección "Calle 123, Banfield, GBA Sur"
ADDR = re.compile(r',\s*(banfield|lomas|temperley|llavallol|turdera|remedios|lan[uú]s)', re.I)


def _address(segs):
    for s in segs:
        if ADDR.search(s) and re.search(r'\d', s):
            return s.split(", GBA")[0].split(", Buenos")[0].strip()
    return ""


def scrape(zone_name, listing_path="/casas-en-venta-en-banfield",
           max_pages=35, delay=0.6, client=None):
    own = client is None
    if own:
        client = httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
    listings, seen = [], set()
    try:
        for page in range(1, max_pages + 1):
            url = f"{BASE}{listing_path}" + (f"?pagina={page}" if page > 1 else "")
            r = client.get(url)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "lxml")
            new = 0
            for a in soup.select("a[href*='/propiedad/']"):
                m = re.search(r"/propiedad/(\d+)", a.get("href", ""))
                if not m or m.group(1) in seen:
                    continue
                sid = m.group(1)
                card = find_card(a)
                segs = [s for s in card.stripped_strings if s and s != "Destacada"]
                full = " ".join(segs)
                if NO_CASA.search(full):          # solo casas
                    seen.add(sid)
                    continue
                price, cur = parse_price(full)
                addr = _address(segs)
                if not addr:                       # sin dirección no podemos ubicarla
                    continue
                seen.add(sid)
                listings.append(Listing(
                    source="buscadorprop",
                    source_id=sid,
                    url=BASE + a.get("href"),
                    title=segs[1] if len(segs) > 1 else "Casa",
                    address=addr,
                    price=price, currency=cur,
                    zone=zone_name,
                    raw={"locality": "Banfield", "operation": "venta"}))
                new += 1
            print(f"  [buscadorprop] pág {page}: {new} casas")
            if new == 0:
                break
    finally:
        if own:
            client.close()
    return listings
