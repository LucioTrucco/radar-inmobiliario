"""
Configuración del radar inmobiliario.

Acá definís QUÉ querés vigilar: las zonas y las fuentes.
Para agregar zonas o fuentes nuevas, editás las listas de abajo.
No hace falta tocar el resto del código.
"""

# Cuántas páginas como máximo recorrer por fuente/zona en cada corrida.
# Cada página de ArgenProp trae ~20 propiedades.
# Subilo para cubrir más mercado (118 páginas ≈ todo Lomas). Para pruebas, dejalo bajo.
MAX_PAGES = 120

# Segundos de espera entre página y página (para no golpear los sitios).
DELAY_SECONDS = 1.2

# --- ZONAS A VIGILAR ---------------------------------------------------------
# Cada zona usa el "slug" que la fuente entiende en su URL.
# Podés sumar partidos/localidades nuevos acá.
ZONES = [
    {
        "name": "Lomas de Zamora (partido)",
        "argenprop_slug": "lomas-de-zamora",
    },
    # Ejemplo para más adelante:
    # {"name": "Banfield", "argenprop_slug": "banfield"},
    # {"name": "Temperley", "argenprop_slug": "temperley"},
]

# --- TIPOS DE OPERACIÓN / PROPIEDAD ------------------------------------------
# ArgenProp arma la URL como: /{tipo}/{operacion}/{zona}
OPERATION = "venta"          # venta | alquiler
PROPERTY_PATH = "casas"      # casas | departamentos | casas-y-departamentos

# --- ZONAS DELIMITADAS (polígonos a medida) ----------------------------------
# Marcan qué propiedades caen en un área específica definida por calles.
# Cada propiedad de las localidades en `geocode_localidades` se geolocaliza
# (una sola vez, queda cacheada) y se marca si cae dentro del polígono.
# El polígono es la lista de esquinas [lat, lon] en orden.
# --- FUENTES ADICIONALES: inmobiliarias y portales ---------------------------
# RE/MAX: una API cubre TODAS las oficinas. Filtramos por localidad (mismos
# códigos que ArgenProp: 1175=Banfield). Trae coordenadas GPS reales.
REMAX_LOCATIONS = [
    {"code": "1175", "name": "banfield"},
]

# Sitios Tokko Broker (inmobiliarias con web propia en esa plataforma).
# Para sumar una: agregás {"name", "url"} y, si hace falta, "listing_path".
TOKKO_SITES = [
    {"name": "Pitton", "url": "https://www.pitton.net", "listing_path": "/Venta"},
    {"name": "Pilares", "url": "https://www.pilarespropiedades.com.ar", "listing_path": "/Venta"},
    {"name": "Alem Propiedades", "url": "https://www.alemprop.com", "listing_path": "/Venta"},
    {"name": "Cabrera", "url": "https://www.cabrerapropiedades.com.ar", "listing_path": "/Venta"},
    {"name": "Juan Barrozo", "url": "https://www.juanbarrozopropiedades.com.ar", "listing_path": "/Venta"},
    {"name": "Lesza", "url": "https://www.lesza.com.ar", "listing_path": "/Venta"},
]

WATCH_ZONES = [
    {
        "name": "Banfield Oeste (Alem/Croce/Uriarte/Portela)",
        # idlocalidad de ArgenProp a geolocalizar (1175 = Banfield).
        "geocode_localidades": ["1175"],
        # contexto para mejorar la geolocalización de las direcciones:
        "geocode_context": "Banfield, Buenos Aires",
        "geocode_bias": [-34.745, -58.40],   # [lat, lon] centro aproximado
        # esquinas del rectángulo Alem–Uriarte–Croce–Portela:
        "polygon": [
            [-34.7357582, -58.3947051],   # Alem ∩ Uriarte
            [-34.7572482, -58.3989175],   # Alem ∩ Portela
            [-34.7557981, -58.4090970],   # Croce ∩ Portela
            [-34.7341342, -58.4045200],   # Croce ∩ Uriarte
        ],
    },
]
