"""
Resuelve el NOMBRE de las inmobiliarias de ArgenProp (que en los listados vienen
solo como un ID). El nombre figura en el logo del anunciante dentro de la ficha
de cada propiedad (atributo alt de la imagen).

Estrategia: por cada inmobiliaria sin nombre, abrimos UNA de sus fichas y leemos
el nombre. Queda cacheado (no se vuelve a pedir).
"""
import re
import time
import httpx
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
SKIP = {"google play", "app store"}
AGENCY_WORDS = re.compile(
    r"propiedades|inmobiliaria|negocios inmobiliarios|bienes|ra[ií]ces|broker|estate",
    re.I)


def extract_name(html):
    soup = BeautifulSoup(html, "lxml")
    cands = []
    for img in soup.select("img[alt]"):
        a = (img.get("alt") or "").strip()
        if a and a.lower() not in SKIP and "argenprop" not in a.lower():
            cands.append(a)
    # preferimos un alt que parezca nombre de inmobiliaria
    for a in cands:
        if AGENCY_WORDS.search(a):
            return a.title()
    return cands[0].title() if cands else None


def agency_names(conn, only_in_zone=True, delay=1.0, verbose=True, client=None):
    """Completa agencies.name (y listings.agency_name) de las inmobiliarias de
    ArgenProp que todavía no tienen nombre."""
    zone_filter = "AND l.zones IS NOT NULL AND l.zones != '[]'" if only_in_zone else ""
    rows = conn.execute(
        f"""SELECT l.agency_id, MIN(l.url) AS url
            FROM listings l
            LEFT JOIN agencies a ON a.aid = 'argenprop:' || l.agency_id
            WHERE l.source='argenprop' AND l.agency_id IS NOT NULL
              AND (a.name IS NULL OR a.name='') {zone_filter}
            GROUP BY l.agency_id"""
    ).fetchall()

    own = client is None
    if own:
        client = httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)
    resolved = 0
    try:
        for i, r in enumerate(rows):
            try:
                html = client.get(r["url"]).text
                name = extract_name(html)
            except Exception:
                name = None
            if name:
                conn.execute("UPDATE agencies SET name=? WHERE aid=?",
                             (name, f"argenprop:{r['agency_id']}"))
                conn.execute("UPDATE listings SET agency_name=? "
                             "WHERE source='argenprop' AND agency_id=?",
                             (name, r["agency_id"]))
                resolved += 1
            conn.commit()
            if verbose and i and i % 15 == 0:
                print(f"    nombrando inmobiliarias {i}/{len(rows)}...")
            time.sleep(delay)
    finally:
        if own:
            client.close()
    return {"pendientes": len(rows), "resueltas": resolved}
