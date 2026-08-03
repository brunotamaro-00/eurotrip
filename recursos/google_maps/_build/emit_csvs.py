#!/usr/bin/env python3
"""
Regenera los 4 CSV desde `places.json`.

Los CSV son salida generada: no se editan a mano. El conteo por archivo tiene
que quedar idéntico al de places.json (regla dura del plan).

Uso:
    python3 emit_csvs.py
    python3 emit_csvs.py --check   # solo verifica conteos, no escribe
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent

FIELDS = [
    "ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo",
    "precio", "descripcion", "url", "reserva", "mejor_momento",
]

CSVS = [
    "europa_occidental.csv",
    "europa_central.csv",
    "europa_del_sur.csv",
    "europa_katia.csv",
]


def fila_csv(p: dict) -> dict:
    """Proyecta un registro de places.json a las 12 columnas del CSV.

    `url` solo sale si es de ticketing real: una homepage informativa no sirve
    en la ficha del pin (el plan lo marca como no-goal).
    """
    url = p.get("url", "") if p.get("url_ticketing") else ""
    return {
        "ciudad": p["ciudad"],
        "nombre": p["nombre"],
        "prioridad": p["prioridad"],
        "lat": f"{float(p['lat']):.6f}",
        "lng": f"{float(p['lng']):.6f}",
        "lugar_busqueda": p["lugar_busqueda"],
        "tipo": p["tipo"],
        "precio": p.get("precio", ""),
        "descripcion": p.get("descripcion", ""),
        "url": url,
        "reserva": p.get("reserva", ""),
        "mejor_momento": p.get("mejor_momento", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    places = json.loads((HERE / "places.json").read_text(encoding="utf-8"))
    por_csv: dict[str, list[dict]] = {n: [] for n in CSVS}
    for p in places:
        por_csv[p["csv"]].append(p)

    esperado = Counter(p["csv"] for p in places)
    print("conteos places.json:", dict(esperado))

    if args.check:
        for n in CSVS:
            with (OUT / n).open(encoding="utf-8") as f:
                n_csv = sum(1 for _ in csv.DictReader(f))
            ok = "✓" if n_csv == esperado[n] else "✗"
            print(f"  {ok} {n}: csv={n_csv} places={esperado[n]}")
        return 0

    for n in CSVS:
        rows = [fila_csv(p) for p in sorted(por_csv[n], key=lambda x: x["csv_line"])]
        path = OUT / n
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            w.writerows(rows)
        print(f"  {n}: {len(rows)} filas")

    assert sum(esperado.values()) == 1243, esperado
    assert all(esperado[n] == len(por_csv[n]) for n in CSVS)
    print(f"total {sum(esperado.values())} ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
