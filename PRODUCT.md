# PRODUCT.md

**Producto:** Radar Inmobiliario — herramienta personal que vigila las casas en venta
de una zona delimitada (Banfield Oeste, partido de Lomas de Zamora) y avisa de
novedades: propiedades nuevas, bajas de precio e inmobiliarias nuevas.

**Register:** product (el diseño SIRVE a la tarea; no es marketing). La vara es
"familiaridad ganada": la herramienta desaparece en la tarea, como Linear/Stripe.

**Usuario / escena:** una persona buscando casa, que entra todos los días —seguido
desde el celular, de noche— a chequear si entró algo nuevo en sus manzanas exactas.
Ánimo: concentrado, expectante. Necesita escanear precios y direcciones rápido y
confiar en el dato. Luz ambiente normal → interfaz clara (no oscura).

**Identidad:** monocromo (blanco / negro / grises), tipografía fuerte, mucho aire.
Sin color decorativo. La jerarquía la cargan tipografía y espacio, no las cajas.

**Fuentes de datos:** ArgenProp (portal), RE/MAX (API) y sitios Tokko (inmobiliarias).
Stack del dashboard: datos desde SQLite (`db.py`) renderizados como UI propia
(HTML/CSS/JS) embebida en Streamlit, que solo oficia de host.
