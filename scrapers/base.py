"""Estructura común de una propiedad, independiente de la fuente."""
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

PRICE_RE = re.compile(r'(USD|U\$S|US\$|\$)\s?([\d.]{3,})', re.I)
# dirección tipo "Calle 1234" (con altura), evitando textos de ambientes/superficie
_NOISE = re.compile(r'(USD|U\$S|\$|hab|baño|amb|m²|m2|dormitor|cocher)', re.I)


def parse_price(text):
    """Devuelve (price, currency) del primer match en el texto, o (None, '?')."""
    m = PRICE_RE.search(text)
    if not m:
        return None, "?"
    cur = "USD" if m.group(1).upper() in ("USD", "U$S", "US$") else "ARS"
    return float(m.group(2).replace(".", "")), cur


def find_address(segments):
    """Elige el segmento que parece una dirección (calle + altura)."""
    best = None
    for s in segments:
        s = s.strip()
        if not (4 <= len(s) <= 50 and re.search(r'\d', s) and not _NOISE.search(s)):
            continue
        # una dirección real tiene letras + espacio + número (no un código tipo BHO123)
        if re.search(r'[A-Za-zÁÉÍÓÚáéíóúñ]\.?\s+.*\d', s):
            if "," in s or re.search(r'[A-Za-zÁÉÍÓÚáéíóúñ]\.?\s+\d', s):
                return s
            best = best or s
    return best or ""


def find_card(link_el, max_up=7, ficha_sel="a[href*='/propiedad/']"):
    """Sube desde el link de ficha hasta el contenedor de SU tarjeta: el primer
    ancestro que tiene precio y contiene una sola ficha (para no mezclar con las
    tarjetas vecinas)."""
    node = link_el
    candidate = link_el.parent
    for _ in range(max_up):
        node = node.parent
        if node is None:
            break
        has_price = bool(PRICE_RE.search(node.get_text(" ", strip=True)))
        n_fichas = len(node.select(ficha_sel))
        if has_price and n_fichas <= 1:
            return node
        if n_fichas > 1:
            # nos pasamos: el nivel anterior era el bueno
            return candidate
        candidate = node
    return candidate


@dataclass
class Listing:
    source: str                       # "argenprop", "zonaprop", "tokko:fandino", ...
    source_id: str                    # id único de la propiedad EN esa fuente
    url: str
    title: str = ""
    address: str = ""
    price: Optional[float] = None
    currency: str = "?"               # "USD" | "ARS" | "?"
    bedrooms: Optional[int] = None
    rooms: Optional[int] = None
    zone: str = ""                    # nombre legible de la zona vigilada
    agency_id: Optional[str] = None
    agency_name: Optional[str] = None
    lat: Optional[float] = None       # si la fuente ya trae coordenadas (ej: RE/MAX)
    lon: Optional[float] = None
    raw: dict = field(default_factory=dict)

    @property
    def uid(self) -> str:
        """Identificador global y estable de la propiedad."""
        return f"{self.source}:{self.source_id}"

    def as_dict(self) -> dict:
        return asdict(self)
