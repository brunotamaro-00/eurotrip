#!/usr/bin/env python3
"""
Genera recursos/google_maps/europa_katia.csv desde katia_places.json.

Pasos: geocodificar -> deduplicar contra las 585 filas existentes -> escribir.

`lugar_busqueda` sale SIEMPRE en idioma local ("Karlův most", no "Puente de
Carlos") porque es la columna con la que se importa en My Maps, y una búsqueda
por texto resuelve mucho mejor el topónimo local que su traducción.

Uso:
    python3 build_katia.py --geocode      # resuelve y guarda katia_geocoded.json
    python3 build_katia.py --write        # dedup + escribe el CSV
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import geo
from areas import AREAS, LABEL_TO_KEYS
from dedup import (Existing, dedup_internal, find_duplicates,
                   find_proximity_dupes, load_existing, write_report)
from validate_csvs import validate_lugar_busqueda

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPORTS = HERE / "reports"
PLACES = HERE / "katia_places.json"
GEOCODED = HERE / "katia_geocoded.json"
TARGET = OUT / "europa_katia.csv"
EXISTING_CSVS = ["europa_occidental.csv", "europa_central.csv", "europa_del_sur.csv"]

FIELDS = ["ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo", "precio", "notas"]
PRIORIDAD = "Solo mapeado"   # decisión del usuario: uniforme en todo el archivo

# Sufijo de país/región que ayuda a Nominatim en la pasada libre.
REGION_HINT = {
    "Highlands": "Scotland, UK",
    "Edimburgo": "Scotland, UK",
}


def load_places() -> list[dict]:
    return json.loads(PLACES.read_text(encoding="utf-8"))


def geocode(places: list[dict], skip_overpass: bool = True) -> list[dict]:
    geo.SKIP_OVERPASS = skip_overpass
    cache = geo.load_cache()
    overrides = geo.load_overrides()
    out: list[dict] = []
    try:
        for i, p in enumerate(places, 1):
            area = AREAS[p["area_key"]]
            key = f"{p['ciudad']}::{geo.normalize(p['nombre_local'])}"
            ov = overrides.get(key)
            if ov:
                p = {**p, "lat": ov["lat"], "lng": ov["lng"], "geo_source": "override",
                     "confianza": "high", "locality": area.locality, "geo_name": p["nombre_local"]}
            else:
                res = geo.resolve(
                    p["nombre_local"], area, p.get("tipo", ""), p.get("wikidata", ""),
                    query_extra=f"{area.locality}, {area.country_en}", cache=cache,
                )
                p = {**p,
                     "lat": res.lat, "lng": res.lng,
                     "geo_source": res.source or "", "confianza": res.confidence,
                     "geo_name": res.name or "", "locality": res.locality or area.locality,
                     "geo_reason": res.reason, "score": res.score}
            out.append(p)
            if i % 10 == 0:
                geo.save_cache(cache)
                print(f"  {i}/{len(places)}", flush=True)
    finally:
        geo.save_cache(cache)
    GEOCODED.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def lugar_busqueda(p: dict) -> str:
    """{nombre_local}, {localidad}, {país en inglés} — sin paréntesis ni & + /."""
    area = AREAS[p["area_key"]]
    def clean(s: str) -> str:
        for ch in "()[]":
            s = s.replace(ch, "")
        # las localidades bilingües de OSM vienen como "Piran / Pirano": la barra
        # rompe la búsqueda por texto, así que se queda el primer nombre
        s = s.split("/")[0]
        return s.replace(" & ", " ").replace(" + ", " ").strip(" ,")

    name = clean(p["nombre_local"])
    loc = clean(p.get("locality") or area.locality)
    parts = [name]
    if loc and geo.normalize(loc) != geo.normalize(name):
        parts.append(loc)
    parts.append(area.country_en)
    return ", ".join(parts)


def to_rows(places: list[dict]) -> list[dict]:
    rows = []
    for p in places:
        if p.get("lat") is None:
            continue
        notas = p.get("notas", "")
        if p.get("descartado"):
            notas = f"Katia: descartado. {notas}" if notas and not notas.startswith("Katia: descartado") else (notas or "Katia: descartado")
        rows.append({
            "ciudad": p["ciudad"],
            "nombre": p["nombre"],
            "prioridad": PRIORIDAD,
            "lat": f"{p['lat']:.6f}",
            "lng": f"{p['lng']:.6f}",
            "lugar_busqueda": lugar_busqueda(p),
            "tipo": p.get("tipo", "Sitio"),
            "precio": p.get("precio", ""),
            "notas": notas[:190],
        })
    return rows


def write_csv(rows: list[dict], path: Path) -> None:
    # newline="" + DictWriter => CRLF, que es el formato de los 3 CSV existentes
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geocode", action="store_true")
    ap.add_argument("--overpass-pass", action="store_true",
                    help="segunda pasada, solo sobre lo que quedó sin resolver, con Overpass")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    places = load_places()
    if args.limit:
        places = places[: args.limit]

    if args.overpass_pass:
        done = {p["id"]: p for p in json.loads(GEOCODED.read_text(encoding="utf-8"))}
        falta = [p for p in places if done.get(p["id"], {}).get("lat") is None]
        print(f"segunda pasada con Overpass sobre {len(falta)} sin resolver…")
        # se borra la entrada de caché para forzar la reconsulta
        cache = geo.load_cache()
        for p in falta:
            cache.pop(geo.cache_key(p["area_key"], p["nombre_local"]), None)
        geo.save_cache(cache)
        for p in geocode(falta, skip_overpass=False):
            done[p["id"]] = p
        places = [done[p["id"]] for p in places if p["id"] in done]
        GEOCODED.write_text(json.dumps(places, ensure_ascii=False, indent=1), encoding="utf-8")
    elif args.geocode or not GEOCODED.exists():
        print(f"geocodificando {len(places)} lugares…")
        places = geocode(places)
    else:
        places = json.loads(GEOCODED.read_text(encoding="utf-8"))

    ok = [p for p in places if p.get("lat") is not None]
    print(f"resueltos {len(ok)}/{len(places)}")
    import collections
    print("  confianza:", dict(collections.Counter(p.get("confianza") for p in places)))
    sin = [p for p in places if p.get("lat") is None]
    for p in sin:
        print(f"  [sin resolver] {p['ciudad']} / {p['nombre']} ({p['nombre_local']}) {p.get('geo_reason','')}")

    if not args.write:
        return 0

    # --- dedup ---
    label_to_area = {}
    for label, keys in LABEL_TO_KEYS.items():
        label_to_area[label] = keys[0]
    existing = load_existing([OUT / n for n in EXISTING_CSVS], label_to_area)
    # corrige area_key por ciudad real
    for e in existing:
        keys = LABEL_TO_KEYS.get(e.ciudad)
        e.area_key = keys[0] if keys else ""

    internos = dedup_internal(ok)
    ok = [p for p in ok if p["id"] not in {m.new_id for m in internos if m.action == "drop"}]

    matches = find_duplicates(ok, existing)
    prox = find_proximity_dupes(ok, existing)
    all_m = internos + matches + prox
    write_report(all_m, REPORTS / "dupes_review.csv")

    # La proximidad SOLA no alcanza para descartar: en un casco histórico denso,
    # `Oude Kerk` y `Red Light Secrets` están a 100 m y son lugares distintos, y
    # las tres fuentes renacentistas de Berna están a ~100 m entre sí. Solo se
    # descarta cuando además el nombre coincide; el resto va al reporte.
    from geoutil import name_sim as _nsim
    for m in prox:
        m.action = "drop" if (m.dist_m is not None and m.dist_m <= 30
                              and _nsim(m.new_nombre, m.old_nombre) >= 0.5) else "review"

    drop_ids = {m.new_id for m in all_m if m.action == "drop"}
    kept = [p for p in ok if p["id"] not in drop_ids]

    # proximidad DENTRO del archivo nuevo: dos lugares distintos pueden resolver
    # al mismo punto (Piran y Tartinijev trg, que es su plaza central)
    from geoutil import haversine_m
    from dedup import _prox_threshold
    vistos: list[dict] = []
    solapados: set[str] = set()
    for p in sorted(kept, key=lambda x: x["id"]):
        for q in vistos:
            if q["area_key"] != p["area_key"]:
                continue
            d = haversine_m(p["lat"], p["lng"], q["lat"], q["lng"])
            if d <= 30 and haversine_m(p["lat"], p["lng"], q["lat"], q["lng"]) >= 0:
                solapados.add(p["id"])
                all_m.append(type(prox[0])(p["id"], p["nombre"], q["nombre"], p["area_key"],
                                           "F", 0.0, None, "drop") if prox else None)
                break
        else:
            vistos.append(p)
    all_m = [m for m in all_m if m is not None]
    kept = [p for p in kept if p["id"] not in solapados]
    write_report(all_m, REPORTS / "dupes_review.csv")

    print(f"\ndedup: {len(internos)} internos · {len(matches)} contra CSV · "
          f"{len(prox)} por proximidad contra CSV · {len(solapados)} solapados entre sí")
    print(f"quedan {len(kept)} de {len(ok)}")

    rows = to_rows(kept)
    bad = [(r["nombre"], e) for r in rows for e in validate_lugar_busqueda(r["lugar_busqueda"], r["nombre"])]
    if bad:
        print(f"\n{len(bad)} problemas de lugar_busqueda:")
        for n, e in bad[:25]:
            print(f"  {n}: {e}")

    write_csv(rows, TARGET)
    print(f"\nescrito {TARGET} con {len(rows)} filas")
    print("por ciudad:", dict(collections.Counter(r["ciudad"] for r in rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
