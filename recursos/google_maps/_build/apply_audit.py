#!/usr/bin/env python3
"""
Aplica a los CSV las coordenadas resueltas por audit_existing.py.

Criterio: se toma la coordenada del resolver cuando su confianza es `high`.
La coordenada que hay en el CSV nunca gana por defecto —92 de las 585 filas son
`manual_fix` sin procedencia—, pero tampoco se pisa nada con una resolución
dudosa: lo que queda en `review`/`unresolved` se deja como está y sale listado
para resolverlo a mano con fuente citable en overrides.json.

Uso:
    python3 apply_audit.py reports/audit_highlands.csv           # dry-run
    python3 apply_audit.py reports/audit_highlands.csv --apply
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
FIELDS = ["ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo", "precio", "notas"]

# Veredictos cuya coordenada se reemplaza si la confianza es `high`.
APPLY_VERDICTS = {"error", "warn", "baja_precision", "override"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    audit = list(csv.DictReader(open(args.report, encoding="utf-8")))
    # (file, ciudad, nombre) -> fila de auditoría
    idx = {(a["file"], a["ciudad"], a["nombre"]): a for a in audit}

    by_file: dict[str, list[dict]] = {}
    for a in audit:
        by_file.setdefault(a["file"], []).append(a)

    applied = skipped = 0
    pendientes: list[dict] = []

    for fname in by_file:
        p = OUT / fname
        with p.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            a = idx.get((fname, r["ciudad"], r["nombre"]))
            if a is None:
                continue
            if a["veredicto"] not in APPLY_VERDICTS:
                continue
            if a["confianza"] != "high" or not a["lat_res"]:
                pendientes.append(a)
                skipped += 1
                continue
            print(f"  {r['ciudad']:12s} {r['nombre'][:34]:36s} "
                  f"{r['lat']},{r['lng']} -> {a['lat_res']},{a['lng_res']}  "
                  f"d={a['dist_m']}m [{a['veredicto']}]")
            r["lat"], r["lng"] = a["lat_res"], a["lng_res"]
            applied += 1
        if args.apply:
            with p.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
                w.writeheader()
                w.writerows(rows)

    print(f"\naplicadas {applied} · pendientes de resolución manual {skipped}")
    for a in pendientes:
        print(f"  [{a['veredicto']}/{a['confianza'] or '-'}] {a['ciudad']} / {a['nombre']} "
              f"({a['buscado']}) csv={a['lat_csv']},{a['lng_csv']} res={a['lat_res']},{a['lng_res']}")
    if not args.apply:
        print("\n(dry-run: correr con --apply para escribir)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
