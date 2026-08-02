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

from destinos import DESTINOS

ROOT = Path("/Users/brunotamaro/Desktop/Trip/Itinerary")
HERE = Path(__file__).resolve().parent
OUT_JSON = HERE / "propios_places.json"

ITEM_RE = re.compile(r"^\s*-\s*\[([ x?~])\]\s*\*\*(.+?)\*\*\s*(.*)$")
HEADING_RE = re.compile(r"^##\s*(.+?)\s*$")

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

# `**€26**` / `**GRATIS**` / `**desde €29**`
PRECIO_RE = re.compile(r"\*\*(GRATIS|Gratis|gratis|[^*]{0,28}?[€$£]\s?[\d.,]+[^*]{0,18})\*\*")
URL_RE = re.compile(r"`?https?://\S+`?")
TAG_RE = re.compile(r"^\s*\[[^\]]{0,30}\]\s*")
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


def extract_precio(resto: str) -> str:
    m = PRECIO_RE.search(resto)
    if not m:
        return ""
    p = m.group(1).strip()
    return "Gratis" if p.lower() == "gratis" else p


def clean_notas(resto: str) -> str:
    t = TAG_RE.sub("", resto)
    t = URL_RE.sub("", t)
    t = MD_LINK_RE.sub(r"\1", t)
    t = t.replace("**", "").replace("`", "")
    # algunos archivos usan ⭐/⭐⭐ como ranking delante de la descripción
    t = re.sub(r"^[\s\-–—]*[⭐★☆]+[\s\-–—]*", "", t)
    t = re.sub(r"^\s*[-–—]\s*", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ;·-–—,")
    return t


def clean_nombre(nombre: str) -> str:
    n = MD_LINK_RE.sub(r"\1", nombre).replace("**", "").strip()
    # "Nombre (aclaración larga)" -> se conserva; el paréntesis corto suele ser
    # el nombre local y lo aprovecha la normalización de lugar_busqueda
    return re.sub(r"\s{2,}", " ", n).strip(" .,;")


def parse_file(md: Path, area_key: str, label: str, region: str) -> tuple[list[dict], list[dict]]:
    places: list[dict] = []
    skipped: list[dict] = []
    section = ""
    skipping = False
    seen: set[str] = set()

    for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), start=1):
        h = HEADING_RE.match(line)
        if h:
            section = h.group(1)
            skipping = should_skip_section(section)
            continue

        m = ITEM_RE.match(line)
        if not m:
            continue
        mark, nombre_raw, resto = m.group(1), m.group(2), m.group(3)
        nombre = clean_nombre(nombre_raw)

        if skipping:
            skipped.append({"file": str(md), "line": i, "nombre": nombre,
                            "motivo": f"seccion:{section}"})
            continue
        if not nombre or SKIP_NAME_RE.search(nombre) and SKIP_NAME_RE.search(nombre).group(1):
            skipped.append({"file": str(md), "line": i, "nombre": nombre,
                            "motivo": "nombre no mapeable"})
            continue
        key = strip_accents(nombre).lower()
        if key in seen:
            skipped.append({"file": str(md), "line": i, "nombre": nombre,
                            "motivo": "duplicado en el archivo"})
            continue
        seen.add(key)

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
            "precio": extract_precio(resto),
            "notas": clean_notas(resto)[:190],
            "descartado": False,
        })
    return places, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    todos: list[dict] = []
    saltados: list[dict] = []
    for d in DESTINOS:
        p, s = parse_file(ROOT / d.md, d.area_key, d.label, d.region)
        todos += p
        saltados += s
        print(f"  {d.label:18s} {len(p):3d} lugares · {len(s):3d} salteados")

    # ids únicos
    vistos: dict[str, int] = {}
    for x in todos:
        vistos[x["id"]] = vistos.get(x["id"], 0) + 1
        if vistos[x["id"]] > 1:
            x["id"] = f"{x['id']}-{vistos[x['id']]}"

    OUT_JSON.write_text(json.dumps(todos, ensure_ascii=False, indent=1), encoding="utf-8")
    (HERE / "propios_skipped.json").write_text(
        json.dumps(saltados, ensure_ascii=False, indent=1), encoding="utf-8")

    import collections
    print(f"\nTOTAL {len(todos)} lugares · {len(saltados)} salteados")
    print("por región:", dict(collections.Counter(x["region"] for x in todos)))
    print("por prioridad:", dict(collections.Counter(x["prioridad"] for x in todos)))
    if args.stats:
        print("por tipo:", dict(collections.Counter(x["tipo"] for x in todos).most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
