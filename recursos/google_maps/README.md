# 🗺️ Google My Maps — CSVs de actividades por región

3 CSVs listos para importar en [Google My Maps](https://www.google.com/mymaps), uno por región. Generados desde los `actividades.md` de cada ciudad.

| Archivo | Región | Ciudades | Lugares |
|---|---|---|---|
| `europa_occidental.csv` | 🌍 Occidental | Londres, York, Edimburgo, Highlands, Ámsterdam, Colmar, Estrasburgo | 284 |
| `europa_central.csv` | 🏔️ Central | Friburgo, Grindelwald, Interlaken, Lauterbrunnen, Lucerna | 68 |
| `europa_del_sur.csv` | ☀️ Sur | Lisboa, Porto | 64 |

*(Europa del Sur se irá llenando con Italia, España, Balcanes, etc. más adelante.)*

## Columnas

- **`ciudad`** — a qué ciudad pertenece el punto.
- **`nombre`** — título del marcador.
- **`prioridad`** — categoría (color); mapea los checkboxes del `.md`:

| En el `.md` | Prioridad | Color sugerido |
|---|---|---|
| `[x]` | **Quiero ir** | Verde |
| `[?]` | **Quizás** | Amarillo/naranja |
| `[ ]` | **Solo mapeado** | Gris/neutro |

- **`lugar_busqueda`** — nombre + ciudad + país para el geocoding.
- **`tipo`**, **`precio`**, **`notas`** — info del marcador.

## Cómo importar cada CSV

1. Crear un mapa nuevo por región → **Importar** → subir el CSV.
2. Columna a ubicar en el mapa: **`lugar_busqueda`**. Título de marcadores: **`nombre`**.
3. **Estilo uniforme** → **Agrupar lugares por** → elegir **`prioridad`** (color por categoría) o **`ciudad`** (color por ciudad) → asignar colores.

> Cada CSV importado = **1 capa**. Si querés una capa por ciudad (para prender/apagar ciudades por separado), importá el mismo CSV varias veces filtrando, o pedí de vuelta los CSVs por ciudad.

## Notas

- Se excluyó lo no geolocalizable (platos, sistemas de transporte, operadores de free tours, deportes de aventura sin punto fijo).
- Los day trips y pueblos de ruta (Route des Vins, Selva Negra, Highlands, Sintra, etc.) caen fuera de la ciudad base a propósito.
- Verificar geocoding de nombres poco comunes (Château Vodou, Fort Poligone, Colombischlössle, Musée du Jouet).
- **Nightlife no incluido**: se puede sumar como capa/CSV aparte "Noche" (los bares/boliches ya tienen dirección en los `.md`).
