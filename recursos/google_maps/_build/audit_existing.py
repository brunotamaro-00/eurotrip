#!/usr/bin/env python3
"""
Auditoría de las coordenadas de los 3 CSV existentes.

Re-resuelve cada fila con el resolver nuevo y compara contra la coordenada
guardada. La coordenada del CSV NUNCA gana por defecto: 92 de las 585 filas
tienen `geo_source: "manual_fix"` en geocoded_ok.json —tipeadas a mano en un
segundo pase que no dejó script ni validación—, así que no es una fuente.

Uso:
    python3 audit_existing.py --ciudad Highlands       # un bloque
    python3 audit_existing.py                          # todo
    python3 audit_existing.py --apply                  # escribe las correcciones
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import geo
from areas import AREAS, HIGHLANDS_KEYS, LABEL_TO_KEYS, covering_areas
from geoutil import decimals, haversine_m

OUT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"
CSVS = ["europa_occidental.csv", "europa_central.csv", "europa_del_sur.csv"]
FIELDS = ["ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo", "precio", "notas"]

# Cuánto puede desviarse la coordenada del CSV respecto de la resuelta, por tipo.
# Un barrio o un valle admiten mucho más error que un museo.
TOLERANCE_M: dict[str, float] = {
    # puntual urbano
    "Museo": 150, "Iglesia": 150, "Catedral": 150, "Mirador": 150, "Teatro": 150,
    "Termas": 150, "Puente": 150, "Café": 120, "Bar": 120, "Tienda": 120,
    "Coffee shop": 120, "Smart shop": 120, "Ruin bar": 120, "Pub": 120,
    "Sitio histórico": 200, "Monumento": 200, "Escultura": 150, "Institución": 200,
    "Plaza": 250, "Fuente": 150, "Palacio": 200,
    # extenso urbano. Calles, paseos y canales son features LINEALES: el punto
    # que devuelve el geocoder puede estar a un par de km del extremo que uno
    # eligió y seguir siendo el mismo lugar (Prinsengracht mide 3 km,
    # Via Appia Antica 16, las Mura Aureliane 19).
    "Mercado": 300, "Calle": 2000, "Paseo": 2000, "Parque": 600, "Jardín": 400,
    "Cementerio": 400, "Barrio": 1500, "Casco histórico": 1500, "Ciudad": 7000,
    "Pueblo": 6000, "Pueblo Route des Vins": 6000,
    # puntual natural
    "Faro": 200, "Castillo": 250, "Fuerte": 250, "Cascada": 300, "Cueva": 300,
    "Teleférico": 300, "Destilería": 250, "Cima": 400, "Playa": 500,
    # extenso natural
    "Naturaleza": 2000, "Paisaje": 2500, "Lago": 3000, "Valle": 3000,
    "Glen": 3000, "Parque nacional": 5000, "Trekking": 3000, "Ruta": 5000,
    "Excursión": 3000, "Day trip": 3000,
}
DEFAULT_TOLERANCE_M = 300.0

REGION_HINT = {
    "Highlands": "Scotland, UK",
    "Edimburgo": "Scotland, UK",
}


def tolerance(tipo: str) -> float:
    return TOLERANCE_M.get(tipo, DEFAULT_TOLERANCE_M)


def load_rows() -> list[dict]:
    rows: list[dict] = []
    for name in CSVS:
        p = OUT / name
        with p.open(encoding="utf-8") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):
                r["_file"] = name
                r["_line"] = i
                rows.append(r)
    return rows


def area_keys_for(ciudad: str) -> list[str]:
    if ciudad == "Highlands":
        return HIGHLANDS_KEYS
    return LABEL_TO_KEYS.get(ciudad, [])


def search_name(row: dict) -> str:
    """Qué nombre se le pasa al resolver.

    Se usa el primer segmento de `lugar_busqueda` porque suele ser el nombre en
    idioma local (`Karlův most`), mientras que `nombre` está en español
    (`Puente de Carlos`). Comparar contra el español es lo que producía los 41
    falsos `name_mismatch` de build_maps.py.
    """
    head = row["lugar_busqueda"].split(",")[0].strip()
    return head or row["nombre"]


def audit(rows: list[dict], cache: dict, overrides: dict) -> list[dict]:
    out: list[dict] = []
    for r in rows:
        ciudad = r["ciudad"]
        keys = area_keys_for(ciudad)
        lat, lng = float(r["lat"]), float(r["lng"])
        name = search_name(r)
        tol = tolerance(r["tipo"])

        ov = overrides.get(f"{ciudad}::{geo.normalize(name)}")
        if ov:
            d = haversine_m(lat, lng, ov["lat"], ov["lng"])
            out.append(_row(r, name, ov["lat"], ov["lng"], d, tol, "override",
                            "high", ov["source"], "override"))
            continue

        if not keys:
            out.append(_row(r, name, None, None, None, tol, "", "", "", "sin_area"))
            continue

        res, win = geo.resolve_multi(
            name, keys, r["tipo"], cache=cache,
            region_hint=REGION_HINT.get(ciudad, ""),
        )
        if not res.ok:
            out.append(_row(r, name, None, None, None, tol, "", res.confidence,
                            res.reason, "unresolved"))
            continue

        d = haversine_m(lat, lng, res.lat, res.lng)
        if d <= tol:
            veredicto = "ok"
        elif d <= 3 * tol:
            veredicto = "warn"
        else:
            veredicto = "error"
        # una coordenada de <=3 decimales es de origen manual: se re-resuelve
        # aunque el veredicto sea ok
        if min(decimals(lat), decimals(lng)) <= 3 and veredicto == "ok":
            veredicto = "baja_precision"
        out.append(_row(r, name, res.lat, res.lng, d, tol, win, res.confidence,
                        f"{res.source}/{res.reason}", veredicto))
    return out


def _row(r, name, la, ln, d, tol, area, conf, src, veredicto) -> dict:
    return {
        "file": r["_file"], "line": r["_line"], "ciudad": r["ciudad"],
        "nombre": r["nombre"], "buscado": name, "tipo": r["tipo"],
        "lat_csv": r["lat"], "lng_csv": r["lng"],
        "lat_res": f"{la:.6f}" if la is not None else "",
        "lng_res": f"{ln:.6f}" if ln is not None else "",
        "dist_m": f"{d:.0f}" if d is not None else "",
        "tolerancia_m": f"{tol:.0f}", "area": area, "confianza": conf,
        "fuente": src, "veredicto": veredicto,
    }


def write_report(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        order = {"error": 0, "unresolved": 1, "baja_precision": 2, "warn": 3,
                 "sin_area": 4, "override": 5, "ok": 6}
        for r in sorted(rows, key=lambda x: (order.get(x["veredicto"], 9),
                                             -float(x["dist_m"] or 0))):
            w.writerow(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ciudad")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default="audit.csv")
    ap.add_argument("--overpass", action="store_true",
                    help="habilita el fallback de Overpass (lento: hasta 70 s por fila)")
    args = ap.parse_args()
    geo.SKIP_OVERPASS = not args.overpass

    rows = load_rows()
    if args.ciudad:
        rows = [r for r in rows if r["ciudad"] == args.ciudad]
    if args.limit:
        rows = rows[: args.limit]

    cache = geo.load_cache()
    overrides = geo.load_overrides()
    print(f"auditando {len(rows)} filas · {len(overrides)} overrides · caché {len(cache)}")

    result: list[dict] = []
    try:
        for i, r in enumerate(rows, 1):
            result += audit([r], cache, overrides)
            if i % 10 == 0:
                geo.save_cache(cache)
                print(f"  {i}/{len(rows)}", flush=True)
    finally:
        geo.save_cache(cache)
        if result:
            write_report(result, REPORTS / args.out)

    import collections
    c = collections.Counter(x["veredicto"] for x in result)
    print("\nveredictos:", dict(c))
    for x in result:
        if x["veredicto"] in ("error", "unresolved"):
            print(f"  [{x['veredicto']}] {x['ciudad']} / {x['nombre']} "
                  f"({x['buscado']}) dist={x['dist_m']}m tol={x['tolerancia_m']}m {x['fuente']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
