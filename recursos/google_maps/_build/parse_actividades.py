#!/usr/bin/env python3
"""
Extrae lugares de los `actividades.md` propios (formato con checkboxes).

A diferencia de los `notas-katia.md` —prosa libre, que hubo que leer a mano—,
este formato es regular y se parsea:

    - [x] **Nombre** [reservar] - Descripción; **€26** adulto `https://...`

Los filtros de sección y de nombre replican los de build_maps.py a propósito:
estas filas se suman a los mismos 3 CSV y tienen que quedar homogéneas con las
585 que ya están.

Uso:
    python3 parse_actividades.py            # escribe propios_places.json
    python3 parse_actividades.py --stats
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import campos
from destinos import DESTINOS

ROOT = Path("/Users/brunotamaro/Desktop/Trip/Itinerary")
HERE = Path(__file__).resolve().parent
OUT_JSON = HERE / "propios_places.json"

# El checkbox puede colgar de un guion o de una lista numerada. Lucerna usa
# numeración (`2. [ ] **Kapellbrücke + Wasserturm**`) y con el patrón viejo,
# que solo aceptaba `-`, sus 5 ítems quedaban invisibles.
ITEM_RE = re.compile(r"^\s*(?:-|\d+\.)\s*\[([ x?~])\]\s*\*\*(.+?)\*\*\s*(.*)$")
HEADING_RE = re.compile(r"^##\s*(.+?)\s*$")

# Fila de tabla cuya primera celda es un nombre en negrita:
#   | **Széchenyi** | **~13,200 HUF** semana | Neo-barroco enorme... |
# Los .md guardan acá los baños de Budapest, los mercados de Ámsterdam y los
# trekkings suizos — con su precio al lado. NO se convierten en lugares nuevos:
# se usan solo para enriquecer filas que ya existen en el CSV (ver
# build_places.py), porque muchas tablas no son lugares (variedades de trufa,
# opciones de góndola) y crearían puntos fantasma.
# El `[^|]*` después de la negrita es necesario: varias filas aclaran algo
# fuera del nombre — `| **Grindelwald → Grosse Scheidegg** (o en PostBus) |`.
FILA_TABLA_RE = re.compile(r"^\s*\|\s*\*\*([^|*]+?)\*\*[^|]*\|(.+)$")

# Secciones que no aportan puntos en el mapa. Mismo criterio que build_maps.py.
SKIP_SECTION_SUBSTR = [
    "nightlife", "gastronom", "anti-scam", "consenso", "links útiles",
    "links utiles", "precios oficiales", "city cards", "días de la semana",
    "dias de la semana", "tips", "entendiendo", "durante tus fechas",
    "vocabulario", "cómo pedir", "como pedir", "packing", "presupuesto",
    "eventos", "festival", "hacks", "trampas", "standing room", "fauna",
    "wildlife", "vida silvestre", "cómo funciona", "comparativa",
    "free walking tour", "pases y cards", "cómo leer esta lista",
    "como leer esta lista", "fuentes oficiales", "hilos y lecturas",
    "mapa mental", "selector rápido", "selector rapido", "en contexto",
    "dónde basarse", "donde basarse", "reservas y fechas clave",
    "reservas importantes", "etiqueta y seguridad", "comer en",
    "referencia de días", "referencia de dias", "notas de cande",
    "bares y noche",
]

# Nombres que no son un punto fijo del mapa.
SKIP_NAME_RE = re.compile(
    r"(?i)("
    r"free\s*tour|sandemans|civitatis|guruwalk|strawberry\s*tours|"
    r"city\s*card|museum\s*pass|travel\s*card|articket|roma\s*pass|"
    r"abono|bono\s|tarjeta\s|pase\s|combo|ticket combinado|"
    r"alquiler|rental|rent\s*a\s*|alquilar|"
    r"parapente|bungee|canyoning|rafting|kayak|snorkel|buceo|"
    r"clase de|taller de|curso de|"
    r"tour\s+(en|por|de)\s|excursión organizada|"
    r"^cómo llegar|^como llegar|^horarios|^precios|"
    r"autobús|autobus|^bus\s|^tren\s|^metro\s|^ferry\s|"
    r")"
)

# tipo según el título de la sección (primer patrón que matchea)
TYPE_FROM_SECTION = [
    (r"(?i)museo|museum|galer|pinacotec", "Museo"),
    (r"(?i)iglesia|catedral|abad|templo|sinagog|bas[ií]lica|mezquita|barroc|duomo", "Iglesia"),
    (r"(?i)mirador|panor[aá]m|vista", "Mirador"),
    (r"(?i)parque|jard[ií]n|naturaleza|verde|olivar|campo|cañón|canon|cascada|garganta", "Naturaleza"),
    (r"(?i)mercado|market", "Mercado"),
    (r"(?i)barrio|callejeo|casco|centro medieval|sassi|ortigia|ciudad (alta|baja)", "Barrio"),
    (r"(?i)puente", "Puente"),
    (r"(?i)terma|bath|balneario|spa", "Termas"),
    (r"(?i)caf[eé]|pasteler", "Café"),
    (r"(?i)teatro|espect[aá]culo|m[uú]sica|concert|[oó]pera|cine", "Teatro"),
    (r"(?i)trek|sender|hike|caminata|ruta|trail|outdoor", "Trekking"),
    (r"(?i)cementeri|cemetery", "Cementerio"),
    (r"(?i)plaza|square|piazza", "Plaza"),
    (r"(?i)palacio|palazzo|castillo|muralla|puerta|fortale", "Castillo"),
    (r"(?i)playa|costa|mar\b", "Playa"),
    (r"(?i)cueva|karst|subterr[aá]ne", "Cueva"),
    (r"(?i)lago|jezero", "Lago"),
    (r"(?i)pueblo|paradas de auto", "Pueblo"),
    (r"(?i)arqueol|romano|antigua|templi|neapolis|historia", "Sitio histórico"),
    (r"(?i)imprescindible|off the beaten|hidden gem|artesan[ií]a|cultura", "Sitio"),
]

PRIORIDAD = {"x": "Quiero ir", "?": "Quizás", " ": "Solo mapeado", "~": "Solo mapeado"}

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def should_skip_section(title: str) -> bool:
    t = strip_accents(title).lower()
    return any(strip_accents(s).lower() in t for s in SKIP_SECTION_SUBSTR)


def infer_tipo(section: str) -> str:
    for pat, tipo in TYPE_FROM_SECTION:
        if re.search(pat, section):
            return tipo
    return "Sitio"


def clean_nombre(nombre: str) -> str:
    n = MD_LINK_RE.sub(r"\1", nombre).replace("**", "").strip()
    # "Nombre (aclaración larga)" -> se conserva; el paréntesis corto suele ser
    # el nombre local y lo aprovecha la normalización de lugar_busqueda
    return re.sub(r"\s{2,}", " ", n).strip(" .,;")


def parse_tabla(linea: str) -> str:
    """Convierte una fila de tabla en un texto plano que los extractores puedan leer.

    `| **~13,200 HUF** semana | Neo-barroco enorme | Primera vez |` pasa a
    `~13,200 HUF semana; Neo-barroco enorme; Primera vez`. Se descartan las
    celdas que son solo un ranking de estrellas o están vacías.
    """
    celdas = [c.strip() for c in linea.split("|")]
    utiles = [c for c in celdas if c and not re.fullmatch(r"[⭐★☆\s]+", c)]
    return "; ".join(utiles)


def parse_file(md: Path, area_key: str, label: str, region: str) -> tuple[list[dict], list[dict], list[dict]]:
    places: list[dict] = []
    skipped: list[dict] = []
    tablas: list[dict] = []
    section = ""
    skipping = False
    seen: set[str] = set()

    for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
        h = HEADING_RE.match(line)
        if h:
            section = h.group(1)
            skipping = should_skip_section(section)
            continue

        # Las tablas se capturan incluso en secciones descartadas. El filtro de
        # secciones existe para no CREAR lugares que no son puntos del mapa, y
        # una fila de tabla nunca crea uno: solo enriquece una fila que el CSV
        # ya tiene. Respetar el filtro acá perdía los precios de las termas de
        # Budapest, que viven bajo "### Comparativa 2026".
        t = FILA_TABLA_RE.match(line)
        if t:
            tablas.append({
                "ciudad": label,
                "nombre": clean_nombre(t.group(1)),
                "src_file": str(md.relative_to(ROOT)),
                "src_lines": [i, i],
                "seccion": section,
                "texto": parse_tabla(t.group(2)),
            })

        m = ITEM_RE.match(line)
        if not m:
            continue
        mark, nombre_raw, resto = m.group(1), m.group(2), m.group(3)
        nombre = clean_nombre(nombre_raw)

        # Los descartados guardan `ciudad` y `texto` además del motivo: aunque
        # no generan un lugar nuevo, sirven para enriquecer una fila que el CSV
        # ya tiene. "Marché Bastille" está en el CSV desde el build viejo y su
        # línea vive bajo "🎉 Eventos", una sección descartada; sin esto su
        # descripción y su precio se perdían.
        def _descartar(motivo: str) -> None:
            skipped.append({"file": str(md), "line": i, "ciudad": label,
                            "nombre": nombre, "motivo": motivo, "texto": resto.strip()})

        if skipping:
            _descartar(f"seccion:{section}")
            continue
        if not nombre or SKIP_NAME_RE.search(nombre) and SKIP_NAME_RE.search(nombre).group(1):
            _descartar("nombre no mapeable")
            continue
        key = strip_accents(nombre).lower()
        if key in seen:
            _descartar("duplicado en el archivo")
            continue
        seen.add(key)

        pre = campos.extraer_precio(resto)
        url = campos.extraer_url(resto)
        res = campos.extraer_reserva(resto)
        mom = campos.extraer_momento(resto)

        places.append({
            "id": f"{area_key}--{re.sub(r'[^a-z0-9]+', '-', strip_accents(nombre).lower()).strip('-')[:60]}",
            "src_file": str(md.relative_to(ROOT)),
            "src_lines": [i, i],
            "ciudad": label,
            "area_key": area_key,
            "region": region,
            "seccion": section,
            "nombre": nombre,
            "nombre_local": nombre,
            "alias_es": [],
            "tipo": infer_tipo(section),
            "prioridad": PRIORIDAD.get(mark, "Solo mapeado"),
            # --- los 5 campos enriquecidos, con su procedencia ---
            "precio": pre["precio"],
            "descripcion": campos.extraer_descripcion(resto, precio=pre["precio"], momento=mom["mejor_momento"]),
            "url": url["url"],
            "reserva": res["reserva"],
            "mejor_momento": mom["mejor_momento"],
            "origen": {
                "precio": pre["origen"],
                "descripcion": "md" if resto.strip() else "",
                "url": "md" if url["url"] else "",
                "reserva": res["origen"],
                "mejor_momento": mom["origen"],
            },
            # banderas para el pase de investigación web
            "precio_ambiguo": pre["ambiguo"],
            "url_ticketing": url["ticketing"],
            "linea_md": resto.strip(),
            "descartado": False,
        })
    return places, skipped, tablas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    todos: list[dict] = []
    saltados: list[dict] = []
    tablas: list[dict] = []
    for d in DESTINOS:
        p, s, t = parse_file(ROOT / d.md, d.area_key, d.label, d.region)
        todos += p
        saltados += s
        tablas += t
        print(f"  {d.label:18s} {len(p):3d} lugares · {len(s):3d} salteados · {len(t):3d} filas de tabla")

    # ids únicos
    vistos: dict[str, int] = {}
    for x in todos:
        vistos[x["id"]] = vistos.get(x["id"], 0) + 1
        if vistos[x["id"]] > 1:
            x["id"] = f"{x['id']}-{vistos[x['id']]}"

    OUT_JSON.write_text(json.dumps(todos, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "propios_skipped.json").write_text(
        json.dumps(saltados, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "propios_tablas.json").write_text(
        json.dumps(tablas, ensure_ascii=False, indent=1), encoding="utf-8")

    import collections
    print(f"\nTOTAL {len(todos)} lugares · {len(saltados)} salteados")
    print("por región:", dict(collections.Counter(x["region"] for x in todos)))
    print("por prioridad:", dict(collections.Counter(x["prioridad"] for x in todos)))

    n = len(todos) or 1
    print("\ncobertura de los campos enriquecidos (lo que aporta el .md):")
    for campo in ("precio", "descripcion", "url", "reserva", "mejor_momento"):
        k = sum(1 for x in todos if x[campo])
        print(f"  {campo:15} {k:4}/{len(todos)}  ({100 * k // n}%)")
    amb = sum(1 for x in todos if x["precio_ambiguo"])
    print(f"  {'precio ambiguo':15} {amb:4}  -> resolver en el pase web")

    if args.stats:
        print("por tipo:", dict(collections.Counter(x["tipo"] for x in todos).most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
