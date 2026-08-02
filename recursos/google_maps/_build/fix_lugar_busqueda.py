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
from areas import AREAS, HIGHLANDS_KEYS, LABEL_TO_KEYS
from geoutil import name_sim, normalize
from validate_csvs import GENERIC_NAMES, validate_lugar_busqueda

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPORTS = HERE / "reports"
CSVS = ["europa_occidental.csv", "europa_central.csv", "europa_del_sur.csv"]
FIELDS = ["ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo", "precio", "notas"]

REGION_HINT = {"Highlands": "Scotland, UK", "Edimburgo": "Scotland, UK"}

# "Nombre (Aclaración)" -> se prefiere lo de adentro del paréntesis cuando es el
# topónimo local, y se descarta cuando es una nota para el viajero.
_PAREN = re.compile(r"\s*\(([^)]*)\)")
_NOTA_RE = re.compile(r"no confundir|farmacia|iglesia del|cine|tejadillo|3 museos|\bs\.\s?X", re.I)


def strip_paren(term: str) -> str:
    """Saca los paréntesis. Si adentro hay un topónimo local (no una nota), se
    queda con ese; si es una aclaración en español, la descarta."""
    m = _PAREN.search(term)
    if not m:
        return term.strip()
    inner = m.group(1).strip()
    outer = _PAREN.sub("", term).strip()
    if inner and not _NOTA_RE.search(inner) and not inner.lower().startswith(("el ", "la ", "los ")):
        # el paréntesis suele traer el nombre local: Orloj, Rynek Główny, Josefov
        return inner
    return outer


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


def build(row: dict, cache: dict) -> tuple[str, str]:
    """Devuelve (lugar_busqueda nuevo, modo)."""
    area = area_for(row)
    if area is None:
        return row["lugar_busqueda"], "sin_area"

    head = clean_term(row["lugar_busqueda"].split(",")[0])
    res = geo.resolve(head, area, row["tipo"], query_extra=f"{area.locality}, {area.country_en}",
                      cache=cache)

    modo = "mecanico"
    term, loc = head, area.locality
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
                new, modo = build(r, cache)
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
