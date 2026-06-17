"""
Scraper de RE/MAX Argentina.

RE/MAX tiene una API JSON pública (api-ar.redremax.com) que cubre TODAS las
oficinas (Actitud, Infinit, Titanium, etc.) de una sola. Cada propiedad trae
coordenadas GPS reales, así que no hace falta geolocalizar: aplicamos el
polígono de zona directamente.
"""
import time
import httpx

from .base import Listing

API = "https://api-ar.redremax.com/remaxweb-ar/api/listings/findAllWithEntrepreneurships"
SITE = "https://www.remax.com.ar/listings/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Origin": "https://www.remax.com.ar",
    "Referer": "https://www.remax.com.ar/",
}


def _tipo(it):
    return ((it.get("type") or {}).get("value") or "").lower()


def _parse(it, zone_name):
    cur = (it.get("currency") or {}).get("value") or "?"
    assoc = it.get("associate") or {}
    loc = it.get("location") or {}
    coords = loc.get("coordinates") or [None, None]   # [lon, lat]
    lon, lat = coords[0], coords[1]
    return Listing(
        source="remax",
        source_id=str(it.get("id")),
        url=SITE + (it.get("slug") or ""),
        title=it.get("title") or "",
        address=it.get("displayAddress") or "",
        price=float(it["price"]) if it.get("price") else None,
        currency=cur,
        bedrooms=it.get("bedrooms"),
        rooms=it.get("totalRooms"),
        zone=zone_name,
        agency_id=assoc.get("officeId"),
        agency_name=assoc.get("officeName"),
        lat=lat,
        lon=lon,
        raw={"geoLabel": it.get("geoLabel"), "internalId": it.get("internalId"),
             "bathrooms": it.get("bathrooms"), "tipo": _tipo(it)},
    )


def scrape_location(location_code, location_name, zone_name,
                    operation_id=1, page_size=50, max_pages=20,
                    delay=0.4, client=None, solo_casas=True):
    """operation_id: 1=venta, 2=alquiler. Recorre todas las páginas de la API.
    Con solo_casas=True descarta departamentos, PH, terrenos, etc."""
    own = client is None
    if own:
        client = httpx.Client(headers=HEADERS, timeout=40, follow_redirects=True)
    listings = []
    try:
        for page in range(0, max_pages):
            params = {
                "page": page, "pageSize": page_size, "sort": "-createdAt",
                "in:operationId": str(operation_id),
                "locations": f"in::::{location_code}@{location_name}",
            }
            r = client.get(API, params=params)
            if r.status_code != 200:
                print(f"  [remax] página {page}: HTTP {r.status_code}, corto")
                break
            data = r.json().get("data", {})
            items = data.get("data", [])
            if not items:
                break
            for it in items:
                if solo_casas and _tipo(it) != "casa":
                    continue
                listings.append(_parse(it, zone_name))
            total_pages = data.get("totalPages", 0)
            print(f"  [remax] {location_name} pág {page + 1}/{total_pages}: "
                  f"{len(items)} propiedades")
            if page + 1 >= total_pages:
                break
            time.sleep(delay)
    finally:
        if own:
            client.close()
    return listings
