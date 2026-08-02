#!/usr/bin/env python3
"""
Saca de europa_katia.csv lo que ya quedó cubierto por los CSV regionales.

Los `notas-katia.md` y los `actividades.md` propios describen los mismos
destinos, así que al sumar Eslovenia, Italia y España a los CSV regionales
aparecen duplicados. La fila que se conserva es la de los CSV regionales,
porque su descripción y su precio salen de las notas propias.

Uso:
    python3 limpiar_katia.py            # dry-run + reporte
    python3 limpiar_katia.py --apply
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from geoutil import haversine_m, name_sim, normalize, token_key

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPORTS = HERE / "reports"
KATIA = OUT / "europa_katia.csv"
REGIONALES = ["europa_occidental.csv", "europa_central.csv", "europa_del_sur.csv"]
FIELDS = ["ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo", "precio", "notas"]

PROX_M = 120.0        # mismo punto, en la misma ciudad
SIM_NOMBRE = 0.80


def cargar(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    katia = cargar(KATIA)
    regionales: dict[str, list[dict]] = {}
    for n in REGIONALES:
        for r in cargar(OUT / n):
            regionales.setdefault(r["ciudad"], []).append({**r, "_file": n})

    quitar, motivos = [], []
    for k in katia:
        cands = regionales.get(k["ciudad"], [])
        if not cands:
            continue
        kn, kt = normalize(k["nombre"]), token_key(k["nombre"])
        klb = normalize(k["lugar_busqueda"].split(",")[0])
        for r in cands:
            rn, rt = normalize(r["nombre"]), token_key(r["nombre"])
            rlb = normalize(r["lugar_busqueda"].split(",")[0])
            motivo = ""
            if kn == rn or kt == rt:
                motivo = "mismo nombre"
            elif klb and klb == rlb:
                motivo = "mismo lugar_busqueda"
            else:
                d = haversine_m(float(k["lat"]), float(k["lng"]),
                                float(r["lat"]), float(r["lng"]))
                if d <= PROX_M and max(name_sim(k["nombre"], r["nombre"]),
                                       name_sim(k["lugar_busqueda"].split(",")[0],
                                                r["lugar_busqueda"].split(",")[0])) >= SIM_NOMBRE:
                    motivo = f"mismo punto ({d:.0f} m) y nombre parecido"
            if motivo:
                quitar.append(k)
                motivos.append({"ciudad": k["ciudad"], "katia": k["nombre"],
                                "regional": r["nombre"], "archivo": r["_file"],
                                "motivo": motivo})
                break

    ids = {id(x) for x in quitar}
    quedan = [k for k in katia if id(k) not in ids]

    import collections
    print(f"europa_katia.csv: {len(katia)} -> {len(quedan)} ({len(quitar)} quitadas)")
    print("por ciudad:", dict(collections.Counter(m["ciudad"] for m in motivos)))
    print("por motivo:", dict(collections.Counter(m["motivo"].split(" (")[0] for m in motivos)))
    for m in motivos[:15]:
        print(f"    {m['ciudad']:16s} {m['katia'][:32]:34s} ~= {m['regional'][:32]:34s} [{m['motivo']}]")

    REPORTS.mkdir(parents=True, exist_ok=True)
    if motivos:
        with (REPORTS / "katia_quitados.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(motivos[0].keys()))
            w.writeheader()
            w.writerows(motivos)

    if args.apply:
        with KATIA.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            w.writerows([{k: v for k, v in r.items() if k in FIELDS} for r in quedan])
        print("\naplicado")
    else:
        print("\n(dry-run: correr con --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
