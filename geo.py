"""
Geolocalización de direcciones + pertenencia a zonas delimitadas.

- Geocoder: Photon (OpenStreetMap), gratis y sin límite estricto. Nivel de calle.
- Caché: las coordenadas se guardan en la base, así una dirección se geolocaliza
  una sola vez (las corridas siguientes no la vuelven a pedir).
- Pertenencia: algoritmo ray-casting (punto en polígono), sin dependencias.
"""
import time
import httpx

import config

PHOTON = "https://photon.komoot.io/api/"
HEADERS = {"User-Agent": "radar-inmobiliario/1.0 (busqueda casa personal)"}


def geocode(address, context="Buenos Aires", bias=None, client=None):
    """Devuelve (lat, lon) o None. `bias` = [lat, lon] para priorizar la zona."""
    if not address:
        return None
    own = client is None
    if own:
        client = httpx.Client(timeout=20, headers=HEADERS)
    try:
        q = address.split(",")[0].strip()
        if context:
            q = f"{q}, {context}"
        params = {"q": q, "limit": 1}
        if bias:
            params["lat"], params["lon"] = bias[0], bias[1]
        r = client.get(PHOTON, params=params)
        feats = r.json().get("features")
        if not feats:
            return None
        lon, lat = feats[0]["geometry"]["coordinates"]
        return (lat, lon)
    except Exception:
        return None
    finally:
        if own:
            client.close()


def point_in_polygon(lat, lon, polygon):
    """ray-casting. polygon = lista de [lat, lon]."""
    x, y = lon, lat
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        if ((xi > x) != (xj > x)) and (y < (yj - yi) * (x - xi) / (xj - xi) + yi):
            inside = not inside
        j = i
    return inside


def zones_for_point(lat, lon, zones=None):
    """Nombres de las WATCH_ZONES que contienen el punto."""
    zones = zones if zones is not None else config.WATCH_ZONES
    out = []
    for z in zones:
        if point_in_polygon(lat, lon, z["polygon"]):
            out.append(z["name"])
    return out


def localidades_a_geocodificar(zones=None):
    """Conjunto de idlocalidad que hace falta geolocalizar para las zonas."""
    zones = zones if zones is not None else config.WATCH_ZONES
    s = set()
    for z in zones:
        s.update(z.get("geocode_localidades", []))
    return s


def enrich(conn, zones=None, delay=0.12, verbose=True):
    """
    Geolocaliza las propiedades pendientes que pertenecen a las localidades de
    las zonas, guarda lat/lon y marca a qué zona(s) pertenecen.
    Devuelve un dict con el resumen.
    """
    import json
    zones = zones if zones is not None else config.WATCH_ZONES
    locs = localidades_a_geocodificar(zones)
    if not locs:
        return {"geocoded": 0, "in_zone": 0, "failed": 0}

    # contexto/bias por localidad (uso el de la primera zona que la incluya)
    ctx_by_loc = {}
    for z in zones:
        for l in z.get("geocode_localidades", []):
            ctx_by_loc.setdefault(l, (z.get("geocode_context", "Buenos Aires"),
                                      z.get("geocode_bias")))

    default_ctx = (zones[0].get("geocode_context", "Buenos Aires"),
                   zones[0].get("geocode_bias")) if zones else ("Buenos Aires", None)

    placeholders = ",".join("?" for _ in locs)
    # Geolocalizamos: (a) propiedades de ArgenProp en las localidades de interés,
    # y (b) propiedades de otras fuentes (RE/MAX, Tokko) que llegan ya filtradas a
    # la zona y traen dirección pero no coordenadas.
    rows = conn.execute(
        f"SELECT uid, address, json_extract(raw,'$.idlocalidad') idl, source "
        f"FROM listings WHERE geocoded IS NULL AND ("
        f"json_extract(raw,'$.idlocalidad') IN ({placeholders}) "
        f"OR source <> 'argenprop')",
        tuple(locs),
    ).fetchall()

    client = httpx.Client(timeout=20, headers=HEADERS)
    geocoded = failed = in_zone = 0
    try:
        for i, r in enumerate(rows):
            ctx, bias = ctx_by_loc.get(str(r["idl"]), default_ctx)
            coord = geocode(r["address"], context=ctx, bias=bias, client=client)
            if coord:
                lat, lon = coord
                names = zones_for_point(lat, lon, zones)
                conn.execute(
                    "UPDATE listings SET lat=?, lon=?, geocoded=1, zones=? WHERE uid=?",
                    (lat, lon, json.dumps(names, ensure_ascii=False), r["uid"]),
                )
                geocoded += 1
                if names:
                    in_zone += 1
            else:
                conn.execute(
                    "UPDATE listings SET geocoded=-1 WHERE uid=?", (r["uid"],))
                failed += 1
            if verbose and i and i % 80 == 0:
                print(f"    geolocalizando {i}/{len(rows)}...")
            conn.commit()
            time.sleep(delay)
    finally:
        client.close()

    return {"geocoded": geocoded, "in_zone": in_zone, "failed": failed,
            "pendientes": len(rows)}
