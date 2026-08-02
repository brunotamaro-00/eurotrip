#!/usr/bin/env python3
"""
Round-trip test: ¿`lugar_busqueda` resuelve al lugar correcto?

Es la única prueba directa del requisito real —importar en My Maps por texto—.
Simula exactamente lo que hace My Maps: consulta Nominatim con `q=lugar_busqueda`,
sin viewbox, sin countrycodes y sin bounded, y compara el primer resultado contra
la coordenada de la fila.

Un FAIL se arregla reescribiendo `lugar_busqueda`, NUNCA moviendo la coordenada.

Uso:
    python3 verify_search.py                       # los 4 CSV
    python3 verify_search.py europa_katia.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import geo
from audit_existing import tolerance
from geoutil import haversine_m

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPORTS = HERE / "reports"
CSVS = ["europa_occidental.csv", "europa_central.csv", "europa_del_sur.csv", "europa_katia.csv"]


def roundtrip(lb: str) -> tuple[float, float, str] | None:
    """Igual que My Maps: búsqueda por texto libre, sin ninguna acotación."""
    cands = geo.nominatim_search(lb, None, bounded=False, limit=1)
    if not cands:
        return None
    c = cands[0]
    return c.lat, c.lng, c.display


def main(argv: list[str]) -> int:
    names = argv[1:] or CSVS
    cache = geo.load_cache()
    rows_out = []
    counts = {"PASS": 0, "SOFT": 0, "FAIL": 0}

    for name in names:
        p = OUT / name
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        print(f"{name}: {len(rows)} filas")
        for i, r in enumerate(rows, 1):
            lb = r["lugar_busqueda"]
            key = f"__rt__::{geo.normalize(lb)}"
            if key in cache:
                hit = cache[key]
            else:
                res = roundtrip(lb)
                hit = {"lat": res[0], "lng": res[1], "display": res[2]} if res else None
                cache[key] = hit
                if i % 20 == 0:
                    geo.save_cache(cache)
                    print(f"  {i}/{len(rows)}", flush=True)

            tol = tolerance(r["tipo"])
            if hit is None:
                verdict, dist = "FAIL", ""
            else:
                d = haversine_m(float(r["lat"]), float(r["lng"]), hit["lat"], hit["lng"])
                dist = f"{d:.0f}"
                verdict = "PASS" if d <= tol else ("SOFT" if d <= 3 * tol else "FAIL")
            counts[verdict] += 1
            rows_out.append({
                "file": name, "ciudad": r["ciudad"], "nombre": r["nombre"],
                "lugar_busqueda": lb, "tipo": r["tipo"], "tolerancia_m": f"{tol:.0f}",
                "dist_m": dist, "resuelve_a": (hit or {}).get("display", "")[:110],
                "veredicto": verdict,
            })
        geo.save_cache(cache)

    REPORTS.mkdir(parents=True, exist_ok=True)
    with (REPORTS / "search_roundtrip.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        order = {"FAIL": 0, "SOFT": 1, "PASS": 2}
        w.writerows(sorted(rows_out, key=lambda x: order[x["veredicto"]]))

    total = sum(counts.values())
    print(f"\nPASS {counts['PASS']} ({counts['PASS']/total:.1%}) · "
          f"SOFT {counts['SOFT']} · FAIL {counts['FAIL']}")
    for r in rows_out:
        if r["veredicto"] == "FAIL":
            print(f"  [FAIL] {r['ciudad']} / {r['nombre']} -> {r['lugar_busqueda']!r} "
                  f"resuelve a {r['resuelve_a'][:60]!r} d={r['dist_m']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
