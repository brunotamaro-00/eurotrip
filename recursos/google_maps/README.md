# Google My Maps — CSVs de actividades por región

4 CSVs listos para importar en [Google My Maps](https://www.google.com/mymaps). Los 3 primeros salen de los `actividades.md` de cada ciudad (**Londres → Madrid**); el cuarto, de los `notas-katia.md`.

Cada fila trae **`lat` / `lng`**, un **`lugar_busqueda` en idioma local**, y la ficha enriquecida (precio, descripción, link de tickets, reserva, mejor momento).

| Archivo | Región | Ciudades | Lugares |
|---|---|---|---|
| `europa_occidental.csv` | Occidental | Londres, York, Edimburgo, Highlands, Ámsterdam, París, Colmar, Estrasburgo | 319 |
| `europa_central.csv` | Central | Friburgo, Grindelwald, Interlaken, Lauterbrunnen, Lucerna, Innsbruck, Viena, Praga, Cracovia, Budapest + Eslovenia | 262 |
| `europa_del_sur.csv` | Sur | Lisboa, Porto + Italia + España (Barcelona, Madrid) | 395 |
| `europa_katia.csv` | Notas de Katia | lo que aportan los `notas-katia.md` y no está en los otros tres | 267 |

**Total: 1243 lugares** con coordenadas.

Los 3 CSV regionales salen de los `actividades.md`; `europa_katia.csv` solo trae lo que **no** está en ellos. Cuando un lugar aparece en los dos lados gana la fila regional.

Todas las filas de Katia van con `prioridad = Solo mapeado`.

## Columnas

```
ciudad, nombre, prioridad, lat, lng, lugar_busqueda, tipo,
precio, descripcion, url, reserva, mejor_momento
```

| Columna | Qué es |
|---|---|
| `ciudad` | a qué ciudad pertenece el punto |
| `nombre` | título del marcador |
| `prioridad` | color: `Quiero ir` / `Quizás` / `Solo mapeado` (mapea `[x]` / `[?]` / `[ ]`) |
| `lat`, `lng` | coordenadas WGS84 |
| `lugar_busqueda` | `Nombre local, Localidad, País` — siempre en idioma local |
| `tipo` | Museo, Plaza, Iglesia, … |
| `precio` | moneda local + `≈EUR` cuando aplica (`Gratis`, `£31 (≈€36)`, `CHF 32 (≈€34)`) |
| `descripcion` | 200–400 chars desde el markdown propio (sin truncar a mitad de palabra) |
| `url` | solo si sirve para **reservar o comprar entrada**; homepages informativas van vacías |
| `reserva` | vocabulario cerrado: `Obligatoria` · `Recomendada` · `No necesaria` |
| `mejor_momento` | corto y accionable (`Martes-jueves, 10am apertura`) |

### Qué columnas mostrar en la ficha del pin

Al importar en My Maps, en **Estilo uniforme → Campos a mostrar** conviene marcar: `precio`, `descripcion`, `url`, `reserva`, `mejor_momento`. El resto (`tipo`, `lugar_busqueda`) es ruido en la ficha.

## Cómo importar cada CSV

1. Crear un mapa nuevo por región → **Importar** → subir el CSV.
2. Columna a ubicar: **`lugar_busqueda`** *o* **`lat` + `lng`**. Título: **`nombre`**.
3. **Estilo uniforme** → agrupar por **`prioridad`** o **`ciudad`**.

| | `lugar_busqueda` | `lat` + `lng` |
|---|---|---|
| Qué hace | My Maps busca el texto y pincha lo que encuentra | pincha la coordenada exacta |
| Ventaja | el pin queda enlazado a la ficha real del lugar | no depende del buscador |
| Riesgo | si el nombre es ambiguo puede caer en otro lado | ninguno |

> Cada CSV importado = **1 capa**.

## Fuente de verdad: `_build/places.json`

Los CSV son **salida generada**. No se editan a mano.

```
actividades.md ─┐
                ├─> places.json ──> emit_csvs.py ──> los 4 CSV
notas-katia.md ─┘        ▲
                         └── overrides.json, derivar_reglas, pase web, auditoría
```

| Archivo | Qué hace |
|---|---|
| `places.json` | fuente de verdad de los 1243 lugares (coordenada + 5 campos + provenance) |
| `build_places.py` | reconcilia CSV ↔ markdown (1243/1243) |
| `campos.py` / `parse_actividades.py` | extrae precio, descripción, url, reserva, mejor momento del `.md` |
| `derivar_reglas.py` | reglas baratas: plazas/calles/parques → Gratis + No necesaria; museos UK gratis |
| `emit_csvs.py` | regenera los 4 CSV desde `places.json` |
| `audit_coords.py` | auditoría 4 señales (resolver + reverse + decimales + encuadre) |
| `geo.py` | Wikidata → Overpass → Nominatim → Photon; incluye `reverse()` |
| `validate_csvs.py` | chequeos estructurales del esquema de 12 columnas |
| `overrides.json` | coordenadas fijadas a mano (`source` + `url` + `checked_at` obligatorios) |

### Regenerar

```bash
cd recursos/google_maps/_build
python3 build_places.py      # si cambió el markdown
python3 derivar_reglas.py    # rellena Gratis / No necesaria por tipo
python3 emit_csvs.py         # escribe los 4 CSV
python3 validate_csvs.py
```

## Notas

- Se excluyó lo no geolocalizable (platos, transporte, nightlife, fauna genérica, eventos temporales).
- Los day trips (Route des Vins, Highlands, Sintra, Auschwitz, …) caen fuera de la ciudad base a propósito.
- **Nightlife no incluido**: se puede sumar como capa aparte.
- Fuera de alcance (anotados para no perderlos): ~138 lugares propios y ~23 de Katia que nunca se geocodificaron. El pedido actual es enriquecer lo mapeado, no ampliarlo.

## Pendiente

- **Pase web** sobre las filas con entrada paga que siguen sin precio (sobre todo `europa_katia.csv`, cuyas notas no mencionan montos).
- **Auditoría de coordenadas** al 100% (`audit_coords.py` → `reports/auditoria.csv`). Corre en background; veredicto `verificado` / `revisar` / `no_verificable`.
- ~30 `lugar_busqueda` todavía en español → `fix_lugar_busqueda.py --apply`.
- Round-trip de `verify_search.py` tras la auditoría.
