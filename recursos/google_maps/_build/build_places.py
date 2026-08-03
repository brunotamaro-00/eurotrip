#!/usr/bin/env python3
"""
Construye `places.json`: la fuente de verdad única de los 1243 lugares.

Por qué existe
--------------
Hasta ahora los CSV eran el artefacto final Y el único registro. Cada vez que
se regeneraban se perdía el trabajo hecho a mano encima (por eso hay 92 filas
con `manual_fix` sin ninguna traza de su origen). A partir de acá:

    actividades.md ─┐
                    ├─> places.json ──> los 4 CSV (salida generada)
    notas-katia.md ─┘        ▲
                             └── overrides.json, pase web, correcciones

El CSV manda en QUÉ filas existen y en la coordenada; el markdown manda en el
contenido. Ninguna fila se crea ni se pierde acá: si el CSV tiene 976 filas
propias, salen 976.

Uso:
    python3 build_places.py            # reconcilia y escribe places.json
    python3 build_places.py --report   # además detalla los no reconciliados
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPORTS = HERE / "reports"

CSVS = {
    "europa_occidental.csv": "occidental",
    "europa_central.csv": "central",
    "europa_del_sur.csv": "sur",
    "europa_katia.csv": "katia",
}

CAMPOS_ENRIQUECIDOS = ("precio", "descripcion", "url", "reserva", "mejor_momento")

# Pares que el matching automático no cierra y que se revisaron a mano contra
# el .md, uno por uno: (ciudad, nombre_en_csv) -> nombre_en_markdown.
#
# No son errores del matcher: son casos donde el CSV guardó el nombre corto o
# uno de los dos lugares de una entrada doble, y adivinarlos automáticamente
# habría requerido bajar el umbral hasta empezar a producir falsos positivos.
ALIAS_MANUAL: dict[tuple[str, str], str] = {
    ("Londres", "Royal Albert Hall"): "BBC Proms en Royal Albert Hall",
    ("Highlands", "Nevis Range Gondola"): "Nevis Range Mountain Gondola",
    ("Ámsterdam", "Magere Brug"): "Ruta Keizersgracht → Magere Brug (Puente Delgado)",
    ("Ámsterdam", "OBA Biblioteca Central"): "OBA (Biblioteca Central)",
    ("Estrasburgo", "MAMCS - Arte Moderno"): "MAMCS — Musée d'Art Moderne et Contemporain",
    ("Friburgo", "Schwabentor"): "Martinstor y Schwabentor",
    ("Grindelwald", "First Flieger / Glider"): "First Flieger / First Glider",
    ("Grindelwald", "Grindelwald pueblo"): "Callejear el pueblo",
    ("Grindelwald", "Faulhorn"): "First → Faulhorn → Schynige Platte",
    # estos dos solo existen en la tabla de trekkings del .md
    ("Grindelwald", "Kleine Scheidegg"): "Panoramaweg: Männlichen → Kleine Scheidegg",
    ("Grindelwald", "Grosse Scheidegg"): "Grindelwald → Grosse Scheidegg",
    # el .md los describe de a pares; las dos filas del CSV comparten la línea
    ("Interlaken", "Iseltwald (Lago de Brienz)"): "Lago de Brienz + Iseltwald",
    ("Interlaken", "Giessbachfälle"): "Lago de Brienz + Iseltwald",
    ("Interlaken", "Spiez (Lago de Thun)"): "Lago de Thun + Spiez",
    ("Lauterbrunnen", "Valle de Lauterbrunnen"): "El valle en sí",
    ("Lauterbrunnen", "Stechelberg"): "Paseo del valle Lauterbrunnen → Trümmelbach → Stechelberg",
    ("Lucerna", "Altstadt de Lucerna"): "Casco medieval (Altstadt)",
    ("Lucerna", "Paseo del lago"): "Paseo por el lago (Vierwaldstättersee)",
    ("Porto", "Museu Soares dos Reis"): "Museu Nacional Soares dos Reis",
    ("Porto", "Serralves"): "Museu de Arte Contemporânea de Serralves",
}


def norm(s: str) -> str:
    """Clave de join: sin acentos, sin paréntesis, sin puntuación."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\(.*?\)", " ", s)
    s = s.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def cargar_csvs() -> list[dict]:
    filas: list[dict] = []
    for nombre, region in CSVS.items():
        with (OUT / nombre).open(encoding="utf-8") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):
                r["_csv"] = nombre
                r["_line"] = i
                r["_region"] = region
                filas.append(r)
    return filas


def cargar_secundarias() -> dict[tuple[str, str], dict]:
    """Fuentes de enriquecimiento de último recurso, indexadas por (ciudad, nombre).

    Son dos: las filas de tabla y los ítems que el parser descarta por sección
    o por nombre. Ninguna de las dos puede CREAR un lugar —muchas no son puntos
    del mapa (variedades de trufa, opciones de góndola, eventos)— pero cuando
    el CSV ya tiene la fila, son la única fuente del dato: el precio de las
    termas de Budapest vive en una tabla bajo "Comparativa 2026", y el
    "Marché Bastille" vive bajo la sección "Eventos".
    """
    idx: dict[tuple[str, str], dict] = {}
    for nombre_archivo, campo_texto in (("propios_tablas.json", "texto"),
                                        ("propios_skipped.json", "texto")):
        p = HERE / nombre_archivo
        if not p.exists():
            continue
        for t in json.loads(p.read_text(encoding="utf-8")):
            if not t.get("ciudad") or not t.get(campo_texto):
                continue
            for k in claves_de(t["nombre"]):
                idx.setdefault((norm(t["ciudad"]), k), t)
    return idx


def desde_secundaria(fila: dict, secundarias: dict) -> dict | None:
    """Construye un ítem enriquecido desde una tabla o un ítem descartado."""
    import campos

    ciudad = norm(fila["ciudad"])
    # El alias manual también vale acá: "Kleine Scheidegg" y "Grosse Scheidegg"
    # solo existen en la tabla de trekkings, no como ítem de checkbox.
    nombres = [fila["nombre"]]
    alias = ALIAS_MANUAL.get((fila["ciudad"], fila["nombre"]))
    if alias:
        nombres.insert(0, alias)

    t = None
    for n in nombres:
        for k in claves_de(n):
            t = secundarias.get((ciudad, k))
            if t:
                break
        if t:
            break
    if not t:
        # el nombre del CSV puede ser un prefijo del de la fuente secundaria
        nombre = norm(fila["nombre"])
        for (c, k), cand in secundarias.items():
            if c == ciudad and len(nombre) >= 8 and (k.startswith(nombre) or nombre.startswith(k)):
                t = cand
                break
    if not t:
        return None

    texto = t["texto"]
    pre = campos.extraer_precio(texto)
    url = campos.extraer_url(texto)
    res = campos.extraer_reserva(texto)
    mom = campos.extraer_momento(texto)
    return {
        "src_file": t.get("src_file", t.get("file", "")),
        "src_lines": t.get("src_lines", [t.get("line", 0), t.get("line", 0)]),
        "precio": pre["precio"],
        "descripcion": campos.extraer_descripcion(texto, precio=pre["precio"], momento=mom["mejor_momento"]),
        "url": url["url"], "reserva": res["reserva"], "mejor_momento": mom["mejor_momento"],
        "precio_ambiguo": pre["ambiguo"], "url_ticketing": url["ticketing"],
        "linea_md": texto,
        "origen": {"precio": pre["origen"], "descripcion": "md" if texto else "",
                   "url": "md" if url["url"] else "", "reserva": res["origen"],
                   "mejor_momento": mom["origen"]},
    }


def cargar_md() -> list[dict]:
    """Ítems de los .md: los propios (con los 5 campos) y los de Katia."""
    items: list[dict] = []
    items += json.loads((HERE / "propios_places.json").read_text(encoding="utf-8"))
    for k in json.loads((HERE / "katia_places.json").read_text(encoding="utf-8")):
        # Katia no pasa por campos.py: sus notas son prosa, no líneas con
        # formato. Solo aporta descripción; el resto sale del pase web.
        k.setdefault("descripcion", k.get("notas", ""))
        for c in CAMPOS_ENRIQUECIDOS:
            k.setdefault(c, "")
        k.setdefault("origen", {"descripcion": "md" if k.get("notas") else ""})
        items.append(k)
    return items


PARENTESIS_RE = re.compile(r"\(([^)]{3,60})\)")


def claves_de(nombre: str) -> list[str]:
    """Todas las formas por las que un ítem se puede nombrar.

    Los .md escriben `Puente de la Capilla (Kapellbrücke)` y el CSV guardó solo
    `Kapellbrücke`. Como `norm()` descarta el paréntesis para poder comparar,
    el nombre local se perdía y el join fallaba. Acá se indexan las dos formas:
    el nombre sin paréntesis y el contenido del paréntesis por separado.
    """
    claves = [norm(nombre)]
    for m in PARENTESIS_RE.finditer(nombre or ""):
        interno = m.group(1).strip()
        # descarta aclaraciones que no son nombres: "(~25km este)", "(3 museos)"
        if re.search(r"(?i)\d\s*(km|min|h\b|museos?|noches?)|^~", interno):
            continue
        claves.append(norm(interno))
    return [k for k in claves if k]


def indexar(items: list[dict]) -> tuple[dict, dict]:
    exacto: dict[tuple[str, str], dict] = {}
    por_ciudad: dict[str, list[dict]] = {}
    for it in items:
        c = norm(it["ciudad"])
        for k in claves_de(it["nombre"]):
            exacto.setdefault((c, k), it)
        for al in it.get("alias_es") or []:
            exacto.setdefault((c, norm(al)), it)
        if it.get("nombre_local"):
            for k in claves_de(it["nombre_local"]):
                exacto.setdefault((c, k), it)
        por_ciudad.setdefault(c, []).append(it)
    return exacto, por_ciudad


def emparejar(fila: dict, exacto: dict, por_ciudad: dict) -> tuple[dict | None, str]:
    ciudad, nombre = norm(fila["ciudad"]), norm(fila["nombre"])

    it = exacto.get((ciudad, nombre))
    if it:
        return it, "exacto"

    alias = ALIAS_MANUAL.get((fila["ciudad"], fila["nombre"]))
    if alias:
        it = exacto.get((ciudad, norm(alias)))
        if it:
            return it, "alias"

    # Difuso, solo dentro de la misma ciudad. El umbral es alto a propósito:
    # un falso positivo mete la descripción de otro lugar en el pin, que es
    # peor que dejar el campo vacío.
    mejor, mejor_score = None, 0.0
    for cand in por_ciudad.get(ciudad, []):
        cn = norm(cand["nombre"])
        if not cn or not nombre:
            continue
        # Un nombre contenido en el otro es el caso típico: "Greenwich
        # Observatory" vs "Greenwich Observatory y Meridiano 0". El prefijo
        # tiene que terminar en límite de palabra para que "Bari" no matchee
        # "Barisano"; con eso, siglas cortas como "MAAT" son seguras.
        corto, largo = (nombre, cn) if len(nombre) <= len(cn) else (cn, nombre)
        if len(corto) >= 4 and largo.startswith(corto) and (len(corto) == len(largo) or largo[len(corto)] == " "):
            score = 0.95
        else:
            score = similar(nombre, cn)
        if score > mejor_score:
            mejor, mejor_score = cand, score
    if mejor is not None and mejor_score >= 0.88:
        return mejor, f"difuso:{mejor_score:.2f}"
    return None, "sin_match"


def construir() -> tuple[list[dict], list[dict]]:
    filas = cargar_csvs()
    items = cargar_md()
    exacto, por_ciudad = indexar(items)
    secundarias = cargar_secundarias()

    places: list[dict] = []
    huerfanas: list[dict] = []

    for f in filas:
        it, como = emparejar(f, exacto, por_ciudad)
        if it is None:
            it = desde_secundaria(f, secundarias)
            if it is not None:
                como = "secundaria"

        origen_md = (it or {}).get("origen", {})
        reg = {
            "id": (it or {}).get("id") or f"{norm(f['ciudad']).replace(' ', '-')}--{norm(f['nombre']).replace(' ', '-')[:60]}",
            "csv": f["_csv"],
            "csv_line": f["_line"],
            "region": f["_region"],
            "ciudad": f["ciudad"],
            "nombre": f["nombre"],
            "prioridad": f["prioridad"],
            "tipo": f["tipo"],
            "lat": float(f["lat"]),
            "lng": float(f["lng"]),
            "lugar_busqueda": f["lugar_busqueda"],
            # provenance hacia el markdown
            "src_file": (it or {}).get("src_file", ""),
            "src_lines": (it or {}).get("src_lines", []),
            "match": como,
            # los 5 campos + de dónde salió cada uno
            "precio": (it or {}).get("precio", "") or f.get("precio", ""),
            "descripcion": (it or {}).get("descripcion", "") or f.get("notas", ""),
            "url": (it or {}).get("url", ""),
            "reserva": (it or {}).get("reserva", ""),
            "mejor_momento": (it or {}).get("mejor_momento", ""),
            "origen": {},
            "precio_ambiguo": (it or {}).get("precio_ambiguo", False),
            "url_ticketing": (it or {}).get("url_ticketing", False),
            "linea_md": (it or {}).get("linea_md", ""),
        }
        # Si el markdown no aportó el campo pero el CSV viejo tenía algo, ese
        # valor se conserva y se marca como `csv_legacy`: es dato real, aunque
        # sin traza de origen.
        for c in CAMPOS_ENRIQUECIDOS:
            if origen_md.get(c):
                reg["origen"][c] = "md"
            elif reg[c]:
                reg["origen"][c] = "csv_legacy"
            else:
                reg["origen"][c] = ""
        places.append(reg)

        if it is None:
            huerfanas.append({"csv": f["_csv"], "line": f["_line"], "ciudad": f["ciudad"],
                              "nombre": f["nombre"], "tipo": f["tipo"],
                              "motivo": "sin item de markdown"})

    return places, huerfanas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    places, huerfanas = construir()

    esperado = {n: sum(1 for _ in csv.DictReader((OUT / n).open(encoding="utf-8"))) for n in CSVS}
    real: dict[str, int] = {}
    for p in places:
        real[p["csv"]] = real.get(p["csv"], 0) + 1
    assert esperado == real, f"se perdieron o duplicaron filas: {esperado} != {real}"

    (HERE / "places.json").write_text(
        json.dumps(places, ensure_ascii=False, indent=1), encoding="utf-8")

    REPORTS.mkdir(parents=True, exist_ok=True)
    if huerfanas:
        with (REPORTS / "reconciliacion.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(huerfanas[0].keys()))
            w.writeheader()
            w.writerows(huerfanas)

    import collections
    print(f"places.json: {len(places)} filas · {sum(esperado.values())} esperadas ✓")
    print("match:", dict(collections.Counter(
        p["match"].split(":")[0] for p in places).most_common()))
    n = len(places)
    print("\ncobertura por campo:")
    for c in CAMPOS_ENRIQUECIDOS:
        k = sum(1 for p in places if p[c])
        print(f"  {c:15} {k:4}/{n}  ({100 * k // n}%)")
    print("\norigen de los datos:")
    for c in CAMPOS_ENRIQUECIDOS:
        o = collections.Counter(p["origen"][c] for p in places if p["origen"][c])
        print(f"  {c:15} {dict(o)}")
    print(f"\nsin item de markdown: {len(huerfanas)}  -> reports/reconciliacion.csv")

    if args.report:
        for h in huerfanas[:60]:
            print(f"  {h['ciudad']:16} {h['nombre'][:44]:46} {h['csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
