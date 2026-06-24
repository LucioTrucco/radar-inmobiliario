"""
Orquestador: corre todos los scrapers, guarda y detecta novedades.

Uso:
    python run.py              # corrida normal (usa config.py)
    python run.py --pages 3    # limita páginas (prueba rápida)

Esto es lo que va a ejecutar la nube (GitHub Actions) cada X horas en la Fase 2.
"""
import argparse
import json
import os
from collections import Counter

import config
import geo
import enrich
from db import connect, process_listing, mark_delisted, now_iso
from scrapers import argenprop, remax, tokko, buscadorprop


def run(max_pages=None):
    max_pages = max_pages or config.MAX_PAGES
    conn = connect()
    run_started = now_iso()
    totals = Counter()

    print(f"== Corrida iniciada {run_started} (máx {max_pages} páginas/zona) ==\n")

    for zone in config.ZONES:
        name = zone["name"]
        print(f"# Zona: {name}")

        # ---- ArgenProp ----
        listings, complete = argenprop.scrape_zone(
            argenprop_slug=zone["argenprop_slug"],
            zone_name=name,
            property_path=config.PROPERTY_PATH,
            operation=config.OPERATION,
            max_pages=max_pages,
            delay=config.DELAY_SECONDS,
        )
        print(f"  [argenprop] total: {len(listings)} propiedades "
              f"(crawl {'completo' if complete else 'parcial'})")

        for lst in listings:
            for ev in process_listing(conn, lst):
                totals[ev] += 1
        conn.commit()

        if complete:
            n = mark_delisted(conn, "argenprop", name, run_started)
            totals["propiedad_dada_de_baja"] += n
            conn.commit()

        print()

    # ---- Fuentes adicionales: inmobiliarias (RE/MAX, Tokko) ----
    extra = []
    if config.REMAX_LOCATIONS:
        print("# RE/MAX (todas las oficinas)")
        for loc in config.REMAX_LOCATIONS:
            extra += remax.scrape_location(loc["code"], loc["name"],
                                           zone_name=loc["name"].title())
        print()
    if config.TOKKO_SITES:
        print("# Inmobiliarias (Tokko)")
        for site in config.TOKKO_SITES:
            extra += tokko.scrape_site(site["url"], site["name"],
                                       site.get("listing_path", "/Venta"))
        print()
    if getattr(config, "BUSCADORPROP", {}).get("enabled"):
        print("# Portal BuscadorProp")
        zname = config.WATCH_ZONES[0]["name"] if config.WATCH_ZONES else "Banfield"
        extra += buscadorprop.scrape(zname, config.BUSCADORPROP.get(
            "path", "/casas-en-venta-en-banfield"))
        print()

    # ---- Fuentes con navegador (Playwright): SOLO local (gated por env) ----
    # ZonaProp bloquea servidores de datacenter, así que esto corre solo cuando
    # se setea RADAR_BROWSER=1 (lo hace el actualizar.command / auto-update local).
    if os.environ.get("RADAR_BROWSER"):
        print("# ZonaProp (navegador headless — solo local)")
        try:
            from scrapers import zonaprop
            extra += zonaprop.scrape(max_pages=getattr(config, "ZONAPROP_PAGES", 45))
        except Exception as e:
            print(f"  [zonaprop] error: {str(e)[:90]}")
        print()

        if getattr(config, "BROWSER_SITES", None):
            print("# Inmobiliarias SPA (navegador — solo local)")
            try:
                from scrapers import browser_site
                extra += browser_site.scrape_sites(config.BROWSER_SITES)
            except Exception as e:
                print(f"  [web] error: {str(e)[:90]}")
            print()

    for lst in extra:
        for ev in process_listing(conn, lst):
            totals[ev] += 1
    conn.commit()

    # ---- geolocalizar y marcar zonas (solo lo pendiente) ----
    if config.WATCH_ZONES:
        print("# Geolocalizando propiedades nuevas y marcando zonas...")
        g = geo.enrich(conn)
        if g.get("pendientes"):
            print(f"  geolocalizadas: {g['geocoded']} | en zona: {g['in_zone']} | "
                  f"fallidas: {g['failed']}")
        else:
            print("  nada pendiente.")
        print()

    # ---- nombrar inmobiliarias de ArgenProp que falten (queda cacheado) ----
    if config.WATCH_ZONES:
        print("# Resolviendo nombres de inmobiliarias...")
        a = enrich.agency_names(conn, only_in_zone=True)
        print(f"  nombradas: {a['resueltas']}/{a['pendientes']}\n")

    summary = dict(totals)

    # Cuántas novedades de ESTA corrida caen en TU zona + presupuesto (lo que
    # realmente vas a ver en el dashboard), para no confundir con el total del
    # partido entero.
    cap = getattr(config, "MAX_PRICE_USD", None)
    q = ("SELECT e.type, COUNT(*) FROM events e JOIN listings l ON e.uid=l.uid "
         "WHERE e.created_at >= ? AND l.zones IS NOT NULL AND l.zones != '[]'")
    params = [run_started]
    if cap:
        q += " AND NOT (l.currency='USD' AND l.price > ?)"
        params.append(cap)
    q += " GROUP BY e.type"
    en_zona = dict(conn.execute(q, params).fetchall())

    conn.execute(
        "INSERT INTO runs (started_at, finished_at, summary) VALUES (?,?,?)",
        (run_started, now_iso(), json.dumps(summary, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()

    zname = (config.WATCH_ZONES[0]["name"].split(" (")[0]
             if config.WATCH_ZONES else "tu zona")
    labels = {
        "propiedad_nueva": "🆕 Propiedades nuevas",
        "baja_precio": "📉 Bajas de precio",
        "suba_precio": "📈 Subas de precio",
        "propiedad_dada_de_baja": "❌ Dadas de baja",
    }
    print("== Resumen de novedades (todo el partido · EN TU ZONA ≤ tope) ==")
    hubo = False
    for key, label in labels.items():
        if summary.get(key):
            hubo = True
            print(f"  {label}: {summary[key]} en total · "
                  f"**{en_zona.get(key, 0)} en {zname}**")
    if not hubo:
        print("  Sin novedades.")
    elif not any(en_zona.get(k) for k in labels):
        print(f"  (Hoy no entró nada nuevo en {zname} dentro de tu presupuesto.)")
    return summary


def geocode_only():
    conn = connect()
    print("# Geolocalizando propiedades pendientes...")
    g = geo.enrich(conn)
    conn.close()
    print(f"  geolocalizadas: {g.get('geocoded',0)} | en zona: {g.get('in_zone',0)} | "
          f"fallidas: {g.get('failed',0)} | pendientes: {g.get('pendientes',0)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=None, help="máx. páginas por zona")
    ap.add_argument("--geocode-only", action="store_true",
                    help="solo geolocalizar lo pendiente, sin scrapear")
    ap.add_argument("--agency-names", action="store_true",
                    help="solo resolver nombres de inmobiliarias de ArgenProp")
    args = ap.parse_args()
    if args.geocode_only:
        geocode_only()
    elif args.agency_names:
        conn = connect()
        print("# Resolviendo nombres de inmobiliarias...")
        a = enrich.agency_names(conn, only_in_zone=True)
        conn.close()
        print(f"  nombradas: {a['resueltas']}/{a['pendientes']}")
    else:
        run(max_pages=args.pages)
