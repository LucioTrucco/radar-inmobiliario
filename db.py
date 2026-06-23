"""
Almacenamiento + detección de cambios.

Usa SQLite (un solo archivo, sin instalar nada) para la versión local.
En la Fase 2 (nube) se reemplaza por Supabase/Postgres manteniendo la misma idea.

Tablas:
  listings       -> estado actual de cada propiedad (una fila por propiedad)
  price_history  -> cada precio observado en el tiempo
  agencies       -> inmobiliarias detectadas
  events         -> novedades para mostrar en el dashboard
                    (propiedad_nueva, baja_precio, suba_precio,
                     inmobiliaria_nueva, propiedad_dada_de_baja)
"""
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import geo


def addr_key(addr):
    """Clave de dirección para deduplicar la MISMA casa publicada en varias
    fuentes (mismas 7 primeras letras de la calle + altura). Igual al dashboard."""
    m = re.search(r"(\d{2,5})", addr or "")
    if not m:
        return None
    street = re.sub(r"[^a-záéíóúñ]", "", addr.split(m.group(1))[0].lower())[:7]
    return f"{street}|{m.group(1)}" if street else None

DB_PATH = Path(__file__).parent / "data" / "radar.db"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    uid           TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    source_id     TEXT NOT NULL,
    url           TEXT,
    title         TEXT,
    address       TEXT,
    price         REAL,
    currency      TEXT,
    bedrooms      INTEGER,
    rooms         INTEGER,
    zone          TEXT,
    agency_id     TEXT,
    agency_name   TEXT,
    raw           TEXT,
    first_seen    TEXT,
    last_seen     TEXT,
    active        INTEGER DEFAULT 1,
    lat           REAL,
    lon           REAL,
    geocoded      INTEGER,            -- NULL=pendiente, 1=ok, -1=falló
    zones         TEXT,               -- JSON con los nombres de zona que contienen la propiedad
    dkey          TEXT                -- clave de dirección para deduplicar entre fuentes
);

CREATE TABLE IF NOT EXISTS price_history (
    uid         TEXT,
    price       REAL,
    currency    TEXT,
    observed_at TEXT
);

CREATE TABLE IF NOT EXISTS agencies (
    aid         TEXT PRIMARY KEY,   -- source:agency_id
    source      TEXT,
    agency_id   TEXT,
    name        TEXT,
    first_seen  TEXT,
    last_seen   TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT NOT NULL,
    uid        TEXT,
    zone       TEXT,
    title      TEXT,
    detail     TEXT,
    created_at TEXT,
    seen       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,
    finished_at TEXT,
    summary     TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_listings_zone ON listings(zone);
"""


def _migrate(conn):
    """Agrega columnas nuevas a bases ya existentes (sin perder datos)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(listings)")}
    for name, decl in [("lat", "REAL"), ("lon", "REAL"),
                       ("geocoded", "INTEGER"), ("zones", "TEXT"), ("dkey", "TEXT")]:
        if name not in cols:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {name} {decl}")
    conn.commit()


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _add_event(conn, type_, uid, zone, title, detail):
    conn.execute(
        "INSERT INTO events (type, uid, zone, title, detail, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (type_, uid, zone, title, json.dumps(detail, ensure_ascii=False), now_iso()),
    )


def process_listing(conn, lst):
    """Inserta o actualiza una propiedad y genera los eventos correspondientes.
    Devuelve la lista de tipos de evento generados."""
    ts = now_iso()
    events = []
    row = conn.execute("SELECT * FROM listings WHERE uid=?", (lst.uid,)).fetchone()

    # --- inmobiliaria nueva ---
    if lst.agency_id:
        aid = f"{lst.source}:{lst.agency_id}"
        arow = conn.execute("SELECT aid FROM agencies WHERE aid=?", (aid,)).fetchone()
        if arow is None:
            conn.execute(
                "INSERT INTO agencies (aid, source, agency_id, name, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?)",
                (aid, lst.source, lst.agency_id, lst.agency_name, ts, ts),
            )
            _add_event(conn, "inmobiliaria_nueva", lst.uid, lst.zone,
                       lst.agency_name or f"Inmobiliaria #{lst.agency_id} ({lst.source})",
                       {"agency_id": lst.agency_id, "source": lst.source})
            events.append("inmobiliaria_nueva")
        else:
            conn.execute("UPDATE agencies SET last_seen=? WHERE aid=?", (ts, aid))

    if row is None:
        # --- propiedad nueva ---
        dkey = addr_key(lst.address)
        # Si la MISMA casa ya está (activa) por otra fuente, la guardamos igual
        # pero NO la marcamos como novedad (evita el doble aviso entre fuentes).
        es_dupe = bool(dkey and conn.execute(
            "SELECT 1 FROM listings WHERE dkey=? AND active=1 LIMIT 1", (dkey,)).fetchone())
        conn.execute(
            "INSERT INTO listings (uid, source, source_id, url, title, address, price, "
            "currency, bedrooms, rooms, zone, agency_id, agency_name, raw, first_seen, "
            "last_seen, active) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)",
            (lst.uid, lst.source, lst.source_id, lst.url, lst.title, lst.address,
             lst.price, lst.currency, lst.bedrooms, lst.rooms, lst.zone,
             lst.agency_id, lst.agency_name, json.dumps(lst.raw, ensure_ascii=False),
             ts, ts),
        )
        conn.execute("UPDATE listings SET dkey=? WHERE uid=?", (dkey, lst.uid))
        conn.execute("INSERT INTO price_history VALUES (?,?,?,?)",
                     (lst.uid, lst.price, lst.currency, ts))
        if not es_dupe:
            _add_event(conn, "propiedad_nueva", lst.uid, lst.zone,
                       lst.title or lst.address,
                       {"price": lst.price, "currency": lst.currency,
                        "address": lst.address, "url": lst.url})
            events.append("propiedad_nueva")
    else:
        # --- propiedad existente: ¿cambió el precio? ---
        old_price = row["price"]
        if (lst.price is not None and old_price is not None
                and lst.currency == row["currency"] and lst.price != old_price):
            kind = "baja_precio" if lst.price < old_price else "suba_precio"
            conn.execute("INSERT INTO price_history VALUES (?,?,?,?)",
                         (lst.uid, lst.price, lst.currency, ts))
            _add_event(conn, kind, lst.uid, lst.zone, lst.title or lst.address,
                       {"old_price": old_price, "new_price": lst.price,
                        "currency": lst.currency,
                        "diff": lst.price - old_price, "url": lst.url})
            events.append(kind)

        conn.execute(
            "UPDATE listings SET url=?, title=?, address=?, price=?, currency=?, "
            "bedrooms=?, rooms=?, agency_id=?, agency_name=?, raw=?, last_seen=?, active=1 "
            "WHERE uid=?",
            (lst.url, lst.title, lst.address, lst.price, lst.currency, lst.bedrooms,
             lst.rooms, lst.agency_id, lst.agency_name,
             json.dumps(lst.raw, ensure_ascii=False), ts, lst.uid),
        )

    # Si la fuente ya trae coordenadas (ej: RE/MAX), guardamos y marcamos zona
    # sin necesidad de geolocalizar.
    if lst.lat is not None and lst.lon is not None:
        znames = geo.zones_for_point(lst.lat, lst.lon)
        conn.execute(
            "UPDATE listings SET lat=?, lon=?, geocoded=1, zones=? WHERE uid=?",
            (lst.lat, lst.lon, json.dumps(znames, ensure_ascii=False), lst.uid),
        )
    return events


def mark_delisted(conn, source, zone, run_started_at):
    """Marca como dadas de baja las propiedades activas de esta fuente/zona
    que NO aparecieron en la corrida actual. Solo se llama tras un crawl completo."""
    rows = conn.execute(
        "SELECT uid, title, address FROM listings "
        "WHERE source=? AND zone=? AND active=1 AND last_seen < ?",
        (source, zone, run_started_at),
    ).fetchall()
    for r in rows:
        conn.execute("UPDATE listings SET active=0 WHERE uid=?", (r["uid"],))
        _add_event(conn, "propiedad_dada_de_baja", r["uid"], zone,
                   r["title"] or r["address"], {})
    return len(rows)
