"""
Scraper genérico de sitios Tokko Broker ("tfw" = Tokko Front Web).

Muchísimas inmobiliarias locales usan esta plataforma (Pitton, etc.). Todas
comparten la misma estructura de HTML, así que UN scraper sirve para todas:
solo cambia el dominio y el nombre de la inmobiliaria (ver config.TOKKO_SITES).

Las propiedades vienen renderizadas en el HTML, ordenadas de más nueva a más
vieja. Leemos la primera página (las más recientes) — que es lo que importa
para detectar publicaciones nuevas. La dirección se geolocaliza después para
saber si cae en la zona.
"""
import re
import httpx
from bs4 import BeautifulSoup

from .base import Listing

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

PRICE_RE = re.compile(r'(USD|U\$S|\$)\s?([\d.]+)', re.I)
TYPEOP_RE = re.compile(r'(.+?)\s+en\s+(Venta|Alquiler|Alquiler-Temp)\s+en\s+(.+)', re.I)


def _parse_card(cont, base_url, agency_name):
    a = cont.select_one("a[href*='/p/']")
    if not a:
        return None
    href = a.get("href", "")
    m = re.search(r"/p/(\d+)-", href)
    if not m:
        return None
    sid = m.group(1)

    parts = [s.strip() for s in cont.stripped_strings if s.strip()]
    full = " | ".join(parts)

    # precio
    price, currency = None, "?"
    pm = PRICE_RE.search(full)
    if pm:
        currency = "USD" if pm.group(1).upper().startswith(("USD", "U$S")) else "ARS"
        price = float(pm.group(2).replace(".", ""))

    # tipo / operación / localidad + dirección: están en los segmentos previos al precio
    tipo, operation, locality, address = "", "", "", ""
    for i, seg in enumerate(parts):
        tm = TYPEOP_RE.search(seg)
        if tm:
            tipo = tm.group(1).strip().lower()
            operation = tm.group(2).lower()
            locality = tm.group(3).split(",")[0].strip()
            if i + 1 < len(parts):
                address = parts[i + 1]
            break

    return Listing(
        source=f"tokko",
        source_id=f"{agency_name}:{sid}",
        url=base_url.rstrip("/") + href if href.startswith("/") else href,
        title=f"{tipo.title()} en {locality}".strip() or "Propiedad",
        address=address,
        price=price,
        currency=currency,
        agency_id=agency_name,
        agency_name=agency_name,
        raw={"locality": locality, "operation": operation, "tipo": tipo},
    ), operation, tipo


def scrape_site(base_url, agency_name, listing_path="/Venta",
                only_operation="venta", solo_casas=True, client=None):
    """Lee las propiedades de la página principal de listados de un sitio Tokko."""
    own = client is None
    if own:
        client = httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
    listings = []
    try:
        r = client.get(base_url.rstrip("/") + listing_path)
        if r.status_code != 200:
            print(f"  [tokko:{agency_name}] HTTP {r.status_code}, salteo")
            return listings
        soup = BeautifulSoup(r.text, "lxml")
        seen = set()
        for a in soup.select("a[href*='/p/']"):
            cont = a
            for _ in range(6):
                cont = cont.parent
                if cont and cont.select_one(".prop-data") and cont.select_one(".prop-img"):
                    break
            else:
                continue
            res = _parse_card(cont, base_url, agency_name)
            if not res:
                continue
            lst, op, tipo = res
            if lst.source_id in seen:
                continue
            if only_operation and op and only_operation not in op:
                continue
            if solo_casas and tipo and "casa" not in tipo:
                continue
            seen.add(lst.source_id)
            listings.append(lst)
        print(f"  [tokko:{agency_name}] {len(listings)} propiedades (más recientes)")
    finally:
        if own:
            client.close()
    return listings
