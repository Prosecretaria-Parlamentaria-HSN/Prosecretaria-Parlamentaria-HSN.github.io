# Páginas por bloque — Prosecretaría Parlamentaria

Una página informativa por bloque, sólo con los datos de ese bloque. Se publican en
`https://prosecretaria-parlamentaria-hsn.github.io/<bloque>/` (por ejemplo `/frente-pro/`).

## Piezas
- `scripts/generar_bloques.py` — arma las 14 páginas desde los datos del sistema legislativo.
- `scripts/plantilla_bloque.html` — diseño de la página (identidad sin logo, Poppins embebida).
- `scripts/scraper_votaciones.py` — lee las actas de votación del Senado (sólo votaciones en general) y guarda `data/votaciones.json`. Incremental, con pausa de 3 s, tope de 25 detalles por corrida y corte si el sitio limita el acceso.
- `.github/workflows/actualizar-bloques.yml` — corre 40 minutos después de cada actualización del sistema (12:40 y 01:40 UTC).
- `tests/` — prueba del lector de votaciones y generador de datos de desarrollo.

## Uso local
    HSN_SOURCE=ruta/al/repo/hsn-sistema-legislativo python scripts/generar_bloques.py [slug]
