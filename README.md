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

## Reglas de atribución de proyectos a los bloques
Las aplica `generar_bloques.py` (función `bloques_de_proyecto`) a los 14 bloques.

- **Año del proyecto**: el del número de expediente (campo `anio`), nunca el de la fecha de ingreso. Un
  S-2126/25 que ingresó en enero de 2026 es un proyecto de 2025 (si es de ley, entra en «Por caducar»).
- **Autoría por la carátula**: se toma el nombre que figura antes de los dos puntos («FAMA: PROYECTO DE...»), no el
  orden de la columna AUTOR. Con varios nombres («CAPITANICH Y BAHL») el proyecto cuenta para cada senador y para el
  bloque de cada uno, una sola vez por bloque. Con «y otros» cuentan solo los nombrados. «Varios senadores» queda
  como estaba. Los datos vienen del repo del sistema (`autores_caratula` y `bloques_caratula`,
  `scripts/autoria_caratula.py`); si un proyecto no los tiene, se usa el comportamiento anterior (primer autor).
- **Proyectos del año en curso**: el bloque registrado al presentarlos. **«Por caducar», aprobados y órdenes del día
  de años anteriores**: el bloque actual de cada autor nombrado si sigue siendo senador/a vigente; si no, ese autor no
  cuenta.
- **Con reunión de comisión**: la agenda la registra o, si no, el proyecto tiene orden del día (Ayuda Memoria o
  planilla de trazabilidad), fecha de dictamen o fue aprobado por el Senado a partir de una orden del día. En ese caso
  la tarjeta no muestra fecha. Esos casos se listan en `data/reuniones_a_rastrear.json`, para buscar después en qué
  reunión se trataron.
- **Aprobados**: Boletín de Novedades; si todavía no incluye una sesión, el código AP de la planilla de
  trazabilidad (`USAR_AP_TRAZABILIDAD` en `generar_bloques.py`). Un proyecto de ley aprobado por el Senado cuenta como
  con media sanción y sale de «Por caducar».
