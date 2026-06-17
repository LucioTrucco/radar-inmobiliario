"""
Scraper de ArgenProp.

ArgenProp entrega cada propiedad como una tarjeta <a class="card"> con un montón
de atributos estructurados (idaviso, idanunciante, montonormalizado, idmoneda,
dormitorios, ...). Eso nos da, sin adivinar:
  - id único de la propiedad      -> detectar propiedades nuevas
  - id de la inmobiliaria         -> detectar inmobiliarias nuevas
  - precio normalizado + moneda   -> detectar bajas/subas de precio
"""
import time
import httpx
from bs4 import BeautifulSoup

from .base import Listing

BASE = "https://www.argenprop.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}


def _text(card, selector):
    el = card.select_one(selector)
    return el.get_text(" ", strip=True) if el else ""


def _intval(v):
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _parse_card(card, zone_name):
    sid = card.get("idaviso") or card.get("data-item-card")
    if not sid:
        return None

    href = card.get("href", "")
    monto = card.get("montonormalizado") or card.get("montooperacion")
    moneda = card.get("idmoneda")
    currency = {"1": "ARS", "2": "USD"}.get(moneda, "?")

    price = None
    if monto and str(monto).replace(".", "").isdigit():
        price = float(str(monto).replace(".", ""))

    return Listing(
        source="argenprop",
        source_id=str(sid),
        url=BASE + href if href.startswith("/") else href,
        title=_text(card, ".card__title"),
        address=_text(card, ".card__address"),
        price=price,
        currency=currency,
        bedrooms=_intval(card.get("dormitorios")),
        rooms=_intval(card.get("ambientes")),
        zone=zone_name,
        agency_id=card.get("idanunciante") or None,
        agency_name=None,  # ArgenProp no expone el nombre en la tarjeta
        raw={
            "idlocalidad": card.get("idlocalidad"),
            "idbarrio": card.get("idbarrio"),
            "idpartido": card.get("idpartido"),
            "price_text": _text(card, ".card__price"),
        },
    )


def scrape_zone(argenprop_slug, zone_name, property_path, operation,
                max_pages=8, delay=1.2, client=None):
    """
    Devuelve (listings, complete).
    `complete` = True si recorrimos toda la zona (la última página trajo menos
    propiedades de lo normal) -> recién ahí es seguro marcar bajas/desaparecidas.
    """
    own_client = client is None
    if own_client:
        client = httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)

    listings = []
    seen_ids = set()
    complete = False
    # ArgenProp redirige el slug a su forma canónica (ej: lomas-de-zamora ->
    # partido-de-lomas-de-zamora). Tomamos esa URL final de la página 1 y
    # paginamos sobre ella con ?pagina-N, que es el formato real del sitio.
    canonical = None
    try:
        for page in range(1, max_pages + 1):
            if page == 1:
                url = f"{BASE}/{property_path}/{operation}/{argenprop_slug}"
            else:
                base = canonical or f"{BASE}/{property_path}/{operation}/{argenprop_slug}"
                url = f"{base}?pagina-{page}"

            resp = client.get(url)
            if resp.status_code != 200:
                print(f"  [argenprop] página {page}: HTTP {resp.status_code}, corto acá")
                break

            if page == 1:
                # guardamos la URL canónica (sin querystring) para paginar
                canonical = str(resp.url).split("?")[0]

            soup = BeautifulSoup(resp.text, "lxml")
            cards = soup.select(".card[data-item-card]")
            if not cards:
                complete = True
                break

            new_on_page = 0
            for card in cards:
                lst = _parse_card(card, zone_name)
                if lst and lst.source_id not in seen_ids:
                    seen_ids.add(lst.source_id)
                    listings.append(lst)
                    new_on_page += 1

            print(f"  [argenprop] {zone_name} pág {page}: {new_on_page} propiedades")

            if new_on_page == 0:       # página repetida -> ya no hay más
                complete = True
                break

            if len(cards) < 20:        # última página parcial -> recorrimos todo
                complete = True
                break

            if page < max_pages:
                time.sleep(delay)
    finally:
        if own_client:
            client.close()

    return listings, complete
