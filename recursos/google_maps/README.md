# 🗺️ Google My Maps — CSVs de actividades por región

4 CSVs listos para importar en [Google My Maps](https://www.google.com/mymaps). Los 3 primeros salen de los `actividades.md` de cada ciudad (**Londres → Budapest**); el cuarto, de los `notas-katia.md`.

Cada fila trae **`lat` / `lng` verificadas** y un **`lugar_busqueda` en idioma local**, así que se puede importar por cualquiera de los dos (ver más abajo).

| Archivo | Región | Ciudades | Lugares |
|---|---|---|---|
| `europa_occidental.csv` | 🌍 Occidental | Londres, York, Edimburgo, Highlands, Ámsterdam, París, Colmar, Estrasburgo | 319 |
| `europa_central.csv` | 🏔️ Central | Friburgo, Grindelwald, Interlaken, Lauterbrunnen, Lucerna, Innsbruck, Viena, Praga, Cracovia, Budapest | 202 |
| `europa_del_sur.csv` | ☀️ Sur | Lisboa, Porto | 64 |
| `europa_katia.csv` | 📝 Notas de Katia | 27 bases, incluidas **Roma, Nápoles, Berna, Liubliana, Lagos Alpinos, Valle del Soča, Karst, Trieste, Costa Eslovena y Kandersteg**, que no aparecen en ningún otro CSV | 326 |

**Total: 911 lugares** con coordenadas.

`europa_katia.csv` contiene solo lo que **no** estaba ya en los otros tres: se dedupica por nombre, por alias español ↔ idioma local y por coincidencia de coordenada. Todas sus filas van con `prioridad = Solo mapeado`; los lugares que Katia descartó entran igual, marcados `Katia: descartado` en `notas`.

## Columnas

- **`ciudad`** — a qué ciudad pertenece el punto.
- **`nombre`** — título del marcador.
- **`prioridad`** — categoría (color); mapea los checkboxes del `.md`:

| En el `.md` | Prioridad | Color sugerido |
|---|---|---|
| `[x]` | **Quiero ir** | Verde |
| `[?]` | **Quizás** | Amarillo/naranja |
| `[ ]` | **Solo mapeado** | Gris/neutro |

- **`lat`**, **`lng`** — coordenadas WGS84 verificadas (fuente principal de ubicación).
- **`lugar_busqueda`** — nombre + ciudad + país (backup / etiqueta).
- **`tipo`**, **`precio`**, **`notas`** — info del marcador.

## Cómo importar cada CSV

1. Crear un mapa nuevo por región → **Importar** → subir el CSV.
2. Columna a ubicar en el mapa: **`lugar_busqueda`** *o* **`lat` + `lng`** — los dos funcionan (ver abajo). Título de marcadores: **`nombre`**.
3. **Estilo uniforme** → **Agrupar lugares por** → elegir **`prioridad`** (color por categoría) o **`ciudad`** (color por ciudad) → asignar colores.

### ¿Por `lugar_busqueda` o por `lat`/`lng`?

| | `lugar_busqueda` | `lat` + `lng` |
|---|---|---|
| Qué hace | My Maps busca el texto y pincha lo que encuentra | pincha la coordenada exacta |
| Ventaja | el pin queda **enlazado a la ficha real** del lugar (horarios, fotos, reseñas, cómo llegar) | no depende del buscador |
| Riesgo | si el nombre es ambiguo puede caer en otro lado | ninguno |

`lugar_busqueda` está escrito como **`Nombre local, Localidad, País`** y **siempre en idioma local** (`Karlův most`, no `Puente de Carlos`), porque una búsqueda por texto resuelve mucho mejor el topónimo local. `_build/verify_search.py` corre el *round-trip test*: consulta el término tal cual lo haría My Maps y verifica que caiga sobre la coordenada verificada.

> Cada CSV importado = **1 capa**. Si querés una capa por ciudad (para prender/apagar ciudades por separado), importá el mismo CSV varias veces filtrando, o pedí de vuelta los CSVs por ciudad.

## Notas

- Se excluyó lo no geolocalizable (platos, sistemas de transporte, operadores de free tours, nightlife, fauna genérica, eventos temporales).
- Los day trips y pueblos de ruta (Route des Vins, Selva Negra, Highlands, Sintra, Auschwitz, Wattens, etc.) caen fuera de la ciudad base a propósito.
- Coordenadas validadas contra el ancla de cada zona + resolución por Wikidata / OpenStreetMap / Nominatim.
- **Nightlife no incluido**: se puede sumar como capa/CSV aparte "Noche" (los bares/boliches ya tienen dirección en los `.md`).

## Cómo se generan (carpeta `_build/`)

`build_maps.py` está **congelado**: generó los primeros 585 lugares pero tenía tres defectos
que dejaron coordenadas mal puestas (el peor, `Loch Cluanie` a 34 km del lago real). El detalle
está en su docstring. El reemplazo:

| Archivo | Qué hace |
|---|---|
| `areas.py` | zonas de búsqueda con radio ≤ 25 km. Highlands está partido en 19 sub-zonas |
| `geo.py` | resolver en cascada Wikidata → Nominatim → Overpass, con scoring por nombre, tipo, distancia y relevancia |
| `katia_places.json` | los 371 lugares extraídos a mano de los `notas-katia.md`, con nombre local y alias |
| `build_katia.py` | geocodifica, deduplica y escribe `europa_katia.csv` |
| `audit_existing.py` + `apply_audit.py` | auditan y corrigen las coordenadas de los CSV viejos |
| `fix_lugar_busqueda.py` | normaliza la columna de búsqueda |
| `validate_csvs.py` | chequeos estructurales, sin red |
| `verify_search.py` | round-trip test: ¿el texto resuelve al lugar correcto? |
| `overrides.json` | coordenadas fijadas a mano. **Exige `source`, `url` y `checked_at`** |

`overrides.json` tiene ese esquema a propósito: 92 de las 585 filas originales se habían
tipeado a mano sin dejar ninguna traza de dónde salieron.

### Pendiente

- Auditoría de coordenadas de las 512 filas fuera de Highlands (`audit_existing.py --out audit_full.csv`).
  Highlands ya está: 36 correcciones aplicadas.
- ~30 `lugar_busqueda` siguen en español en países que no lo hablan (entre ellos
  `Mina de Sal de Wieliczka`, que además no está en Kraków). Necesitan el resolver:
  `fix_lugar_busqueda.py --apply` sin `--sin-red`.
- 23 lugares de las notas de Katia quedaron sin geocodificar y no entraron al CSV; la lista
  está en el mensaje del commit que agregó `europa_katia.csv`.
