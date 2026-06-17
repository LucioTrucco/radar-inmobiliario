# Design System — Radar Inmobiliario

Fuente única de verdad del dashboard. Registro **product** (la herramienta sirve a
la tarea; vara = familiaridad ganada, tipo Linear/Stripe). Identidad **monocromo**:
la jerarquía la cargan tipografía, peso y espacio — no el color ni las cajas.

## Principios
1. Sin color decorativo. Blanco, negro y grises. (Restrained product palette.)
2. Jerarquía por tamaño + peso + color + espacio, nunca por uppercase-en-todo.
3. Listas separadas por líneas finas, no tarjetas con sombra (las cards son la respuesta vaga).
4. Densidad legible: escanear precios y direcciones rápido.
5. La tipografía es el diseño.

## Tokens de color (verificados contra #fff, WCAG AA)
| Token | Valor | Uso | Contraste s/ blanco |
|---|---|---|---|
| `--bg` | `#ffffff` | fondo | — |
| `--surface` | `#f6f6f7` | hover de fila, panel sutil | — |
| `--ink` | `#14171a` | texto principal, precios, títulos | ~16:1 |
| `--ink-2` | `#555a61` | texto secundario, meta, timestamps | ~6.7:1 ✓ |
| `--line` | `#e7e8eb` | líneas finas (separadores) | — |
| `--rule` | `#14171a` | regla fuerte (bajo header) | — |
| `--focus` | `#14171a` | anillo de foco (2px, offset 2px) | ≥3:1 ✓ |

Prohibido texto en gris < 4.5:1. Nada de cream/beige como fondo.

## Tipografía
- **Familia única:** `Hanken Grotesk` (grotesca humanista, con carácter, no en banlist),
  con fallback `system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial`.
  `font-display: swap`. Pesos: 400 / 500 / 600 / 700 / 800.
- **Escala rem fija** (product, no fluida), ratio ~1.2:
  `--t-xs .75rem` · `--t-sm .8125rem` · `--t-base 1rem` · `--t-md 1.0625rem`
  · `--t-lg 1.5rem` (precio) · `--t-xl 1.5rem` (h1).
- Números (precios, conteos): `font-variant-numeric: tabular-nums`.
- Display letter-spacing piso **-0.04em**; uso -0.02/-0.03em.
- `text-wrap: balance` en títulos. `font-kerning: normal`.
- **Sentence case** salvo wordmark. Sin eyebrows en mayúscula con tracking.

## Espacio
Base 8px. Ritmo variado (no todo igual). Línea de texto ≤ 70ch.

## Motion (product: estado, no decoración)
- Transiciones 150–200ms, easing `cubic-bezier(.16,1,.3,1)` (ease-out-expo). Sin bounce.
- Solo hover/focus/active. **Sin coreografía de carga** (la herramienta carga en la tarea).
- `@media (prefers-reduced-motion: reduce)` → sin transiciones.

## Componentes (estados explícitos)
- **Tab/zona/chip/link/input**: default · hover · focus-visible · active · (chip) selected.
- **Chip**: borde 1px ink; selected = relleno ink + texto blanco; `aria-pressed`.
- **Tabs**: `role=tablist/tab`, `aria-selected`; activos por peso + subrayado.
- **Fila de propiedad**: hover = fondo `--surface`; foco visible; flecha del link +2px.
- **Empty state** que enseña, no "no hay nada".

## Accesibilidad (AA, no negociable)
- Contraste verificado (tabla arriba). Foco visible en todo lo interactivo.
- `skip-link` al contenido. Landmarks: `header` / `nav[aria-label]` / `main`.
- Input de búsqueda con `aria-label`; chips `aria-pressed`; tabs `aria-selected`.
- Flechas/íconos decorativos `aria-hidden`. `prefers-reduced-motion` respetado.
- Targets táctiles ≥ 44px. Zoom no deshabilitado. Tamaños en rem.

## Bans (de impeccable) que NO aparecen acá
side-stripe borders · gradient text · glassmorphism · hero-metric template ·
grillas de cards idénticas · eyebrows uppercase por sección · radios 24px+ ·
border 1px + box-shadow ≥16px juntos · fondo cream/beige.
