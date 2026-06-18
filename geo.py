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

# Nombre de localidad de ArgenProp según idlocalidad (para geolocalizar con la
# localidad REAL del aviso y no ubicar todo en Banfield por error).
AP_LOCALIDADES = {
    "1175": "Banfield", "1177": "Lomas de Zamora", "1178": "Temperley",
    "1176": "Llavallol", "1179": "Turdera", "2035": "Ingeniero Budge",
}


def localidad_de(source, idlocalidad, raw_locality):
    """Localidad real del aviso, para usar como contexto de geolocalización."""
    if source == "argenprop":
        return AP_LOCALIDADES.get(str(idlocalidad), "Lomas de Zamora")
    return (raw_locality or "Banfield").strip()


# ============================================================================
# Geolocalización POR ALTURA usando direcciones de OpenStreetMap (Overpass).
# Photon es solo a nivel de calle (mete una "Acevedo 2744" en la Acevedo de la
# zona). Con las direcciones exactas de OSM interpolamos la altura sobre la calle
# y ubicamos cada propiedad de verdad. Es lo que decide bien dentro/fuera de zona.
# ============================================================================
import re
import unicodedata

OVERPASS = "https://overpass-api.de/api/interpreter"
_OSM_CACHE = {}


def _norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\bgral\b", "general", s)
    s = re.sub(r"\bav(da)?\b", "avenida", s)
    s = re.sub(r"\b(al|n|nro|piso|pb|depto|dpto|de|del|la|las|los|el|y|e)\b", " ", s)
    return " ".join(s.split())


def _parse_addr(a):
    m = re.search(r"(\d{2,5})", a or "")
    num = int(m.group(1)) if m else None
    street = _norm(a.split(m.group(1))[0]) if num else _norm(a)
    return street, num


def osm_streets(poly):
    """Descarga (una vez) las direcciones de OSM en el área y arma un índice
    {calle_normalizada: [(altura, lat, lon), ...]}. Devuelve (streets, centroide)."""
    key = tuple(round(c, 3) for p in poly for c in p)
    if key in _OSM_CACHE:
        return _OSM_CACHE[key]
    lats = [p[0] for p in poly]
    lons = [p[1] for p in poly]
    cen = (sum(lats) / len(lats), sum(lons) / len(lons))
    S, W = min(lats) - 0.02, min(lons) - 0.02
    N, E = max(lats) + 0.02, max(lons) + 0.02
    q = (f'[out:json][timeout:90];'
         f'node["addr:housenumber"]["addr:street"]({S},{W},{N},{E});out tags center;')
    streets = {}
    try:
        r = httpx.post(OVERPASS, data={"data": q}, timeout=120,
                       headers={"User-Agent": "radar-inmobiliario/1.0"})
        from collections import defaultdict
        acc = defaultdict(list)
        for e in r.json().get("elements", []):
            m = re.match(r"(\d+)", e["tags"].get("addr:housenumber", ""))
            if not m:
                continue
            lat = e.get("lat") or (e.get("center") or {}).get("lat")
            lon = e.get("lon") or (e.get("center") or {}).get("lon")
            if lat is not None:
                acc[_norm(e["tags"]["addr:street"])].append((int(m.group(1)), lat, lon))
        streets = {k: sorted(v) for k, v in acc.items()}
    except Exception as e:
        print(f"  [osm] no se pudo bajar direcciones ({str(e)[:60]}); uso solo Photon")
    _OSM_CACHE[key] = (streets, cen)
    return streets, cen


def _interp(samp, num):
    if num <= samp[0][0]:
        return samp[0][1], samp[0][2]
    if num >= samp[-1][0]:
        return samp[-1][1], samp[-1][2]
    for i in range(len(samp) - 1):
        if samp[i][0] <= num <= samp[i + 1][0]:
            n0, a0, o0 = samp[i]
            n1, a1, o1 = samp[i + 1]
            t = (num - n0) / (n1 - n0) if n1 != n0 else 0
            return a0 + t * (a1 - a0), o0 + t * (o1 - o0)
    return samp[-1][1], samp[-1][2]


def resolve_osm(address, streets, centroid):
    """Coordenada precisa (por altura) de una dirección, o None si OSM no la tiene.
    Ante calles homónimas, elige la instancia más cercana a la zona."""
    st, num = _parse_addr(address)
    if num is None or not st or not streets:
        return None
    toks = [t for t in st.split() if len(t) >= 4] or st.split()
    cands = [s for s in streets if all(t in s for t in toks)]
    if not cands:
        cands = [s for s in streets if any((" " + t + " ") in (" " + s + " ") for t in toks)]
    if not cands:
        return None
    best, bd = None, 9.0
    for s in cands:
        pt = _interp(streets[s], num)
        d = (pt[0] - centroid[0]) ** 2 + (pt[1] - centroid[1]) ** 2
        if d < bd:
            bd, best = d, pt
    return best


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

    bias = zones[0].get("geocode_bias") if zones else None

    placeholders = ",".join("?" for _ in locs)
    # Geolocalizamos: (a) propiedades de ArgenProp en las localidades de interés,
    # y (b) propiedades de otras fuentes (RE/MAX, Tokko) que llegan ya filtradas a
    # la zona y traen dirección pero no coordenadas.
    rows = conn.execute(
        f"SELECT uid, address, json_extract(raw,'$.idlocalidad') idl, source, "
        f"json_extract(raw,'$.locality') rawloc "
        f"FROM listings WHERE geocoded IS NULL AND ("
        f"json_extract(raw,'$.idlocalidad') IN ({placeholders}) "
        f"OR source <> 'argenprop')",
        tuple(locs),
    ).fetchall()

    # índice de direcciones de OSM (una sola descarga) para ubicar por altura
    osm_streets_idx, osm_cen = osm_streets(zones[0]["polygon"]) if zones else ({}, (0, 0))

    client = httpx.Client(timeout=20, headers=HEADERS)
    geocoded = failed = in_zone = 0
    try:
        for i, r in enumerate(rows):
            loc = localidad_de(r["source"], r["idl"], r["rawloc"])
            if "banfield" in loc.lower():
                # En Banfield ubicamos por ALTURA con OSM (preciso). Si OSM no
                # tiene la dirección, caemos a Photon (nivel de calle).
                coord = (resolve_osm(r["address"], osm_streets_idx, osm_cen)
                         or geocode(r["address"], context="Banfield, Buenos Aires",
                                    bias=bias, client=client))
            else:
                # Otra localidad (Remedios, Temperley, Lomas...): Photon con su
                # localidad real -> cae afuera de la zona, como corresponde.
                coord = geocode(r["address"], context=f"{loc}, Buenos Aires",
                                bias=None, client=client)
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
