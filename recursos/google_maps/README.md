# 🗺️ Google My Maps — CSVs de actividades por región

3 CSVs listos para importar en [Google My Maps](https://www.google.com/mymaps), uno por región. Generados desde los `actividades.md` de cada ciudad (**Londres → Budapest**).

Cada fila incluye **`lat` / `lng` verificadas** (no solo `lugar_busqueda`), para que My Maps pinche el punto exacto sin depender del geocoding por nombre.

| Archivo | Región | Ciudades | Lugares |
|---|---|---|---|
| `europa_occidental.csv` | 🌍 Occidental | Londres, York, Edimburgo, Highlands, Ámsterdam, París, Colmar, Estrasburgo | 319 |
| `europa_central.csv` | 🏔️ Central | Friburgo, Grindelwald, Interlaken, Lauterbrunnen, Lucerna, Innsbruck, Viena, Praga, Cracovia, Budapest | 202 |
| `europa_del_sur.csv` | ☀️ Sur | Lisboa, Porto | 64 |

**Total: 585 lugares** con coordenadas.

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

`lugar_busqueda` está escrito como **`Nombre local, Localidad, País`** y **siempre en idioma local** (`Karlův most`, no `Puente de Carlos`), porque una búsqueda por texto resuelve mucho mejor el topónimo local. Cada fila pasó un *round-trip test*: se consulta el término tal cual lo haría My Maps y se verifica que caiga sobre la coordenada verificada.

> Cada CSV importado = **1 capa**. Si querés una capa por ciudad (para prender/apagar ciudades por separado), importá el mismo CSV varias veces filtrando, o pedí de vuelta los CSVs por ciudad.

## Notas

- Se excluyó lo no geolocalizable (platos, sistemas de transporte, operadores de free tours, nightlife, fauna genérica, eventos temporales).
- Los day trips y pueblos de ruta (Route des Vins, Selva Negra, Highlands, Sintra, Auschwitz, Wattens, etc.) caen fuera de la ciudad base a propósito.
- Coordenadas validadas contra centroides por ciudad + spot-check de landmarks (museos, castillos, puentes, termas, etc.).
- **Nightlife no incluido**: se puede sumar como capa/CSV aparte "Noche" (los bares/boliches ya tienen dirección en los `.md`).
