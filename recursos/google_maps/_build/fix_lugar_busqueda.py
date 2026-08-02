#!/usr/bin/env python3
"""
Normaliza `lugar_busqueda` en los 3 CSV existentes.

Regla canónica:  {nombre_local}, {localidad}, {país en inglés}

Por qué en idioma local: el usuario importa en My Maps por esta columna, y una
búsqueda por texto resuelve mucho mejor `Karlův most` que `Puente de Carlos`.
Hoy hay ~30 filas en español dentro de países que no lo hablan, 211 sin país,
38 sin ninguna coma y 21 con caracteres que rompen la búsqueda —incluida
`Kazinczy utca (no confundir con Kazimierz), Budapest`, donde una nota personal
quedó dentro del término de búsqueda—.

Dos modos, según cuánta confianza haya en la resolución:

- **reescritura completa**: si el resolver devolvió `high` y el nombre matchea,
  se usa su `name` (idioma local) y su `locality` reales. Eso arregla
  `Mina de Sal de Wieliczka, Kraków` -> `Kopalnia Soli Wieliczka, Wieliczka`
  (que además ni siquiera está en Kraków).
- **arreglo mecánico**: si no, se conserva el término que ya había y solo se
  sacan paréntesis y separadores, y se completa localidad/país.

Nunca se toca `nombre` (lo que se ve en el mapa) ni `lat`/`lng`.

Uso:
    python3 fix_lugar_busqueda.py            # dry-run, escribe el reporte
    python3 fix_lugar_busqueda.py --apply
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import geo
from areas import AREAS, COUNTRIES_EN, HIGHLANDS_KEYS, LABEL_TO_KEYS
from geoutil import name_sim, normalize
from validate_csvs import GENERIC_NAMES, validate_lugar_busqueda

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPORTS = HERE / "reports"
CSVS = ["europa_occidental.csv", "europa_central.csv", "europa_del_sur.csv"]
FIELDS = ["ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo", "precio", "notas"]

REGION_HINT = {"Highlands": "Scotland, UK", "Edimburgo": "Scotland, UK"}

# Nombres alternativos de las localidades (inglés / español). Sin esto, el
# segmento intermedio "Prague" se conservaría junto a la localidad "Praha" y
# saldría `Karlův most, Prague, Praha, Czechia`.
_ALIAS_LOCALIDAD: dict[str, set[str]] = {
    "praha": {"prague", "praga"},
    "wien": {"vienna", "viena"},
    "krakow": {"cracow", "cracovia"},
    "firenze": {"florence", "florencia"},
    "napoli": {"naples", "napoles"},
    "roma": {"rome"},
    "lisboa": {"lisbon"},
    "london": {"londres"},
    "paris": {"paris"},
    "luzern": {"lucerne", "lucerna"},
    "ljubljana": {"liubliana"},
    "bern": {"berna", "berne"},
    "munchen": {"munich"},
    "koln": {"cologne", "colonia"},
    "edinburgh": {"edimburgo"},
    "amsterdam": {"amsterdam"},
    "budapest": {"budapest"},
}


def _misma_localidad(a: str, b: str) -> bool:
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return True
    return nb in _ALIAS_LOCALIDAD.get(na, set()) or na in _ALIAS_LOCALIDAD.get(nb, set())

# "Nombre (Aclaración)" -> se prefiere lo de adentro del paréntesis cuando es el
# topónimo local, y se descarta cuando es una nota para el viajero.
_PAREN = re.compile(r"\s*\(([^)]*)\)")

# Sustantivos genéricos en español: si el término de afuera empieza por uno,
# es una traducción y el paréntesis trae el topónimo local
# ("Puente de Carlos (Karlův most)" -> Karlův most).
_ES_GENERICO = {
    "puente", "plaza", "castillo", "catedral", "iglesia", "basilica", "basílica",
    "barrio", "mina", "fabrica", "fábrica", "colina", "torre", "casa", "museo",
    "ciudad", "reloj", "monte", "isla", "palacio", "jardin", "jardín", "mercado",
    "parque", "avenida", "calle", "cementerio", "biblioteca", "farmacia",
    "monasterio", "sinagoga", "muralla", "bosque", "lago", "valle", "cueva",
    "teatro", "estacion", "estación", "ayuntamiento", "cripta", "opera", "ópera",
}


def strip_paren(term: str) -> str:
    """Saca los paréntesis.

    Se queda con lo de adentro solo si lo de afuera es una traducción al
    español. Si no, conserva lo de afuera: en
    `Swarovski Kristallwelten (Wattens)` el paréntesis es la localidad, no el
    nombre, y quedarse con `Wattens` apuntaría al pueblo en vez del museo.
    """
    m = _PAREN.search(term)
    if not m:
        return term.strip()
    inner = m.group(1).strip()
    outer = _PAREN.sub("", term).strip()
    if not inner:
        return outer
    primera = normalize(outer).split(" ")[0] if outer else ""
    return inner if primera in _ES_GENERICO else outer


def clean_term(term: str) -> str:
    t = strip_paren(term)
    t = t.replace(" & ", " ").replace(" + ", " ")
    t = t.replace("/", " ").replace("[", "").replace("]", "")
    return re.sub(r"\s{2,}", " ", t).strip(" ,")


def area_for(row: dict):
    keys = LABEL_TO_KEYS.get(row["ciudad"], [])
    if not keys:
        return None
    if row["ciudad"] == "Highlands":
        from areas import covering_areas
        cov = covering_areas(float(row["lat"]), float(row["lng"]), HIGHLANDS_KEYS)
        return cov[0] if cov else AREAS[keys[0]]
    return AREAS[keys[0]]


def build(row: dict, cache: dict, sin_red: bool = False) -> tuple[str, str]:
    """Devuelve (lugar_busqueda nuevo, modo)."""
    area = area_for(row)
    if area is None:
        return row["lugar_busqueda"], "sin_area"

    partes_orig = [p.strip() for p in row["lugar_busqueda"].split(",")]
    head = clean_term(partes_orig[0])
    modo = "mecanico"
    term, loc = head, area.locality

    # Si la fila ya estaba bien formada y traía un segmento intermedio más
    # específico que la localidad del área (`Broadway Market, Hackney, London`),
    # se conserva: acota la búsqueda en vez de ensancharla.
    if len(partes_orig) >= 3 and partes_orig[-1] in COUNTRIES_EN:
        medio = clean_term(partes_orig[1])
        if (medio and not _misma_localidad(medio, area.locality)
                and normalize(medio) != normalize(head)):
            loc = f"{medio}, {area.locality}"

    if not sin_red:
        res = geo.resolve(head, area, row["tipo"],
                          query_extra=f"{area.locality}, {area.country_en}", cache=cache)
        if res.ok and res.confidence == "high" and res.name and name_sim(head, res.name) >= 0.55:
            term, modo = res.name, "resuelto"
            if res.locality:
                loc = res.locality

    term = clean_term(term)
    parts = [term]
    if loc and normalize(loc) != normalize(term):
        parts.append(loc)
    # los genéricos ("Altstadt") exigen localidad Y país; si la localidad se cayó
    # por ser igual al término, se usa la del área
    if normalize(term) in GENERIC_NAMES and len(parts) == 1:
        parts.append(area.locality)
    parts.append(area.country_en)
    return ", ".join(parts), modo


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--ciudad")
    ap.add_argument("--sin-red", action="store_true",
                    help="solo el arreglo mecánico (paréntesis, separadores, país), sin consultar")
    args = ap.parse_args()

    cache = geo.load_cache()
    report = []
    try:
        for name in CSVS:
            p = OUT / name
            with p.open(encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            changed = 0
            for i, r in enumerate(rows, 1):
                if args.ciudad and r["ciudad"] != args.ciudad:
                    continue
                old = r["lugar_busqueda"]
                new, modo = build(r, cache, sin_red=args.sin_red)
                errs = validate_lugar_busqueda(new, r["nombre"])
                if new != old:
                    changed += 1
                report.append({
                    "file": name, "ciudad": r["ciudad"], "nombre": r["nombre"],
                    "antes": old, "despues": new, "modo": modo,
                    "problemas": "; ".join(errs),
                })
                r["lugar_busqueda"] = new
                if i % 25 == 0:
                    geo.save_cache(cache)
                    print(f"  {name} {i}/{len(rows)}", flush=True)
            print(f"{name}: {changed}/{len(rows)} cambiadas")
            if args.apply:
                with p.open("w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
                    w.writeheader()
                    w.writerows(rows)
    finally:
        geo.save_cache(cache)
        if report:
            REPORTS.mkdir(parents=True, exist_ok=True)
            with (REPORTS / "lugar_busqueda.csv").open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(report[0].keys()))
                w.writeheader()
                w.writerows(report)

    import collections
    print("\nmodos:", dict(collections.Counter(r["modo"] for r in report)))
    prob = [r for r in report if r["problemas"]]
    print(f"con problemas restantes: {len(prob)}")
    for r in prob[:20]:
        print(f"  {r['ciudad']} / {r['nombre']}: {r['despues']!r} -> {r['problemas']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
