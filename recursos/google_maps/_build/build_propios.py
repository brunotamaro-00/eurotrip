#!/usr/bin/env python3
"""
Suma a los 3 CSV regionales los destinos que faltaban (Eslovenia, Italia, España),
a partir de los `actividades.md` propios.

Tres pasos:

1. **Cruce con notas-katia.** Muchos de estos lugares ya se resolvieron al armar
   `europa_katia.csv`. De ahí se toman el nombre en idioma local y la coordenada
   ya verificada —que es justo lo que pidió el usuario— y se ahorra la consulta.
   La descripción, el precio y la prioridad salen SIEMPRE de las notas propias.
2. **Geocodificar** solo lo que no cruzó.
3. **Deduplicar** contra las filas que ya están en el CSV de destino y anexar.

Uso:
    python3 build_propios.py --cruzar          # paso 1, sin red
    python3 build_propios.py --geocode         # paso 2
    python3 build_propios.py --write           # paso 3
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
from dataclasses import replace
from pathlib import Path

import geo
from areas import AREAS
from destinos import CSV_POR_REGION, DESTINOS
from dedup import Existing, find_duplicates, load_existing
from geoutil import haversine_m, name_sim, normalize, token_key
from validate_csvs import validate_lugar_busqueda

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPORTS = HERE / "reports"
PLACES = HERE / "propios_places.json"
CRUZADO = HERE / "propios_cruzado.json"
KATIA_GEO = HERE / "katia_geocoded.json"
KATIA_CSV = OUT / "europa_katia.csv"

FIELDS = ["ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo", "precio", "notas"]
UMBRAL_CRUCE = 0.86   # similitud de nombre para dar por cruzado


# ---------------------------------------------------------------------------
# 1 — cruce con lo ya resuelto en notas-katia
# ---------------------------------------------------------------------------
def cruzar() -> list[dict]:
    from fix_lugar_busqueda import strip_paren

    places = json.loads(PLACES.read_text(encoding="utf-8"))
    # Los nombres propios traen una glosa entre paréntesis
    # (`Prešernov trg (Plaza Prešeren)`). El marcador conserva el nombre
    # completo, pero la consulta tiene que ir sin el paréntesis: consultarlo
    # entero no devuelve nada.
    for p in places:
        p["nombre_local"] = strip_paren(p["nombre"]) or p["nombre"]
    katia = [k for k in json.loads(KATIA_GEO.read_text(encoding="utf-8"))
             if k.get("lat") is not None]
    por_area: dict[str, list[dict]] = {}
    for k in katia:
        por_area.setdefault(k["area_key"], []).append(k)

    hits = 0
    for p in places:
        cands = por_area.get(p["area_key"], [])
        mejor, mejor_s = None, 0.0
        for k in cands:
            nombres_k = [k["nombre"], k["nombre_local"]] + (k.get("alias_es") or [])
            s = max(name_sim(p["nombre"], n) for n in nombres_k if n)
            # el token-set exacto vale como cruce aunque el ratio baje
            if token_key(p["nombre"]) == token_key(k["nombre_local"]):
                s = max(s, 0.95)
            if s > mejor_s:
                mejor, mejor_s = k, s
        if mejor is not None and mejor_s >= UMBRAL_CRUCE:
            hits += 1
            p["nombre_local"] = mejor["nombre_local"]
            p["lat"], p["lng"] = mejor["lat"], mejor["lng"]
            p["locality"] = mejor.get("locality") or AREAS[p["area_key"]].locality
            p["origen_geo"] = "katia"
            p["katia_id"] = mejor["id"]
            p["cruce_score"] = round(mejor_s, 3)
        else:
            p["lat"] = p["lng"] = None
            p["origen_geo"] = ""
    CRUZADO.write_text(json.dumps(places, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"cruzados con notas-katia: {hits}/{len(places)}")
    print("  por ciudad:", dict(collections.Counter(
        p["ciudad"] for p in places if p["origen_geo"] == "katia")))
    return places


# ---------------------------------------------------------------------------
# 2 — geocodificar el resto
# ---------------------------------------------------------------------------
import re as _re

# Nombres que describen una actividad, un plato o una película, no un punto fijo.
NO_ES_LUGAR = _re.compile(
    r"(?i)^(caminar|callejear|callejeo|pasear|paseo por|recorrer|subir|bajar|"
    r"ba[ñn]o|atardecer|amanecer|vuelta al|tours? tem|tour de|combinados?$)|"
    r"(?i)(nocturno|sin rumbo|a pie|en bici|combo)$|"
    r"(?i)^(panzerotti|focaccia|orecchiette|arancini|granita|cannoli|"
    r"kremna rezina|gelato|pasticciotto|rustico|puccia|sfogliatella)\b|"
    r"(?i)^(la pasi[oó]n de cristo|no time to die|el evangelio seg[uú]n)"
)

# Separadores de nombre compuesto: `A + B`, `A / B`, `A y B`
_SEPARADORES = _re.compile(r"\s+\+\s+|\s+/\s+|\s+y\s+(?=[A-ZÁÉÍÓÚÑ])")


_PREFIJO_ES = _re.compile(
    r"(?i)^(barrio|jardines?|museo de|casa de|cripta de|iglesias? de|"
    r"catedral de|palacio de|plaza de|puerto de|parque de|mercado de|"
    r"teatro de|torre de|castillo de|puente de|calle de|zona de)\s+"
)


def sin_prefijo_es(nombre: str) -> str:
    """`Barrio Krakovo` -> `Krakovo`. Los prefijos genéricos en español no
    existen en OSM y hacen fallar la búsqueda."""
    return _PREFIJO_ES.sub("", nombre).strip()


def variantes_consulta(nombre: str) -> list[str]:
    """Nombre completo y, si es compuesto, cada componente por separado.

    Es el fallo más común de este lote: `Palazzo dei Normanni + Cappella
    Palatina` o `Chiesa di Santa Chiara / Santa Teresa` no resuelven enteros,
    pero su primer componente sí. El marcador conserva el nombre compuesto.
    """
    partes = [p.strip(" .,;") for p in _SEPARADORES.split(nombre) if p.strip(" .,;")]
    out = [nombre]
    for p in partes:
        if p != nombre and len(p) > 3 and p not in out:
            out.append(p)
    for v in list(out):
        sp = sin_prefijo_es(v)
        if sp and sp != v and sp not in out:
            out.append(sp)
    return out


def geocode(skip_overpass: bool = True, solo_cache: bool = False) -> list[dict]:
    """`solo_cache` resuelve sin tocar la red, usando lo que ya está cacheado.

    Sirve para recuperar el trabajo de una corrida interrumpida: el SIGTERM no
    ejecuta el `finally`, así que los resultados quedaban en la caché pero no en
    propios_cruzado.json.
    """
    geo.SKIP_OVERPASS = skip_overpass
    places = json.loads(CRUZADO.read_text(encoding="utf-8"))
    falta = [p for p in places if p.get("lat") is None]
    print(f"geocodificando {len(falta)} …{' (solo caché)' if solo_cache else ''}")
    cache = geo.load_cache()

    import signal

    interrumpido = {"v": False}

    def _parar(signum, frame):
        interrumpido["v"] = True
        print("  señal recibida: guardo y salgo", flush=True)

    signal.signal(signal.SIGTERM, _parar)
    signal.signal(signal.SIGINT, _parar)

    try:
        for i, p in enumerate(falta, 1):
            if interrumpido["v"]:
                break
            a = AREAS[p["area_key"]]
            if NO_ES_LUGAR.search(p["nombre_local"]):
                p["origen_geo"] = "descartado_no_es_lugar"
                continue
            if solo_cache and geo.cache_key(p["area_key"], p["nombre_local"]) not in cache:
                continue
            r = None
            for variante in variantes_consulta(p["nombre_local"]):
                if solo_cache and geo.cache_key(p["area_key"], variante) not in cache:
                    continue
                try:
                    r = geo.resolve(variante, a, p.get("tipo", ""),
                                    query_extra=f"{a.locality}, {a.country_en}", cache=cache)
                except geo.RateLimited as e:
                    print(f"  RATE LIMIT, corto acá: {e}", flush=True)
                    r = None
                    break
                if r.ok:
                    break
            # Último recurso: day trips reales (Alberobello está a 30 km de
            # Ostuni, Miramare a 21 de Piran). Ensanchar el radio es peligroso
            # —es el mismo error que tenía Highlands con max_km=220— así que se
            # exige coincidencia de nombre casi exacta y se rechazan alojamientos
            # y calles, que es lo que devolvía: `Muraglia` -> `La Muraglia B&B`,
            # `Cripta della Cattedrale` -> una gruta a 65 km.
            if (r is None or not r.ok) and not solo_cache:
                ancho = replace(a, key=f"{a.key}__daytrip", max_km=45.0)
                for variante in variantes_consulta(p["nombre_local"]):
                    try:
                        rr = geo.resolve(variante, ancho, p.get("tipo", ""),
                                         query_extra=a.country_en, cache=cache)
                    except geo.RateLimited:
                        break
                    clase = (rr.osm_class or "").split("=")[0]
                    if (rr.ok
                            and name_sim(variante, rr.name or "") >= 0.92
                            and clase not in {"highway", "tourism_hotel", "building"}
                            and (rr.osm_class or "") not in {
                                "tourism=hotel", "tourism=guest_house",
                                "tourism=apartment", "tourism=hostel"}):
                        r = rr
                        p["es_daytrip"] = True
                        break

            if r is not None and r.ok:
                p["lat"], p["lng"] = r.lat, r.lng
                p["locality"] = r.locality or a.locality
                p["origen_geo"] = r.source
                if r.name and name_sim(p["nombre_local"], r.name) >= 0.6:
                    p["nombre_local"] = r.name
            if i % 10 == 0:
                geo.save_cache(cache)
                print(f"  {i}/{len(falta)}", flush=True)
    finally:
        geo.save_cache(cache)
        CRUZADO.write_text(json.dumps(places, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(1 for p in places if p.get("lat") is not None)
    print(f"resueltos {ok}/{len(places)}")
    return places


# ---------------------------------------------------------------------------
# 3 — dedup y escritura
# ---------------------------------------------------------------------------
def lugar_busqueda(p: dict) -> str:
    a = AREAS[p["area_key"]]

    def limpiar(s: str) -> str:
        for ch in "()[]":
            s = s.replace(ch, "")
        s = s.split("/")[0]
        return s.replace(" & ", " ").replace(" + ", " ").strip(" ,")

    nombre = limpiar(p.get("nombre_local") or p["nombre"])
    loc = limpiar(p.get("locality") or a.locality)
    partes = [nombre]
    if loc and normalize(loc) != normalize(nombre):
        partes.append(loc)
    partes.append(a.country_en)
    return ", ".join(partes)


def a_fila(p: dict) -> dict:
    return {
        "ciudad": p["ciudad"],
        "nombre": p["nombre"],
        "prioridad": p["prioridad"],
        "lat": f"{p['lat']:.6f}",
        "lng": f"{p['lng']:.6f}",
        "lugar_busqueda": lugar_busqueda(p),
        "tipo": p.get("tipo", "Sitio"),
        "precio": p.get("precio", ""),
        "notas": p.get("notas", "")[:190],
    }


def write() -> int:
    places = [p for p in json.loads(CRUZADO.read_text(encoding="utf-8"))
              if p.get("lat") is not None]
    label_area = {d.label: d.area_key for d in DESTINOS}

    total_nuevas = 0
    for region, csv_name in CSV_POR_REGION.items():
        sel = [p for p in places if p["region"] == region]
        if not sel:
            continue
        path = OUT / csv_name
        with path.open(encoding="utf-8") as f:
            existentes = list(csv.DictReader(f))

        # dedup contra lo que ya está en ESE csv, por ciudad
        ex_por_ciudad: dict[str, list[dict]] = {}
        for r in existentes:
            ex_por_ciudad.setdefault(r["ciudad"], []).append(r)

        nuevas, dups = [], []
        for p in sel:
            fila = a_fila(p)
            colision = None
            for r in ex_por_ciudad.get(p["ciudad"], []):
                if normalize(r["nombre"]) == normalize(fila["nombre"]) or \
                        token_key(r["nombre"]) == token_key(fila["nombre"]):
                    colision = r
                    break
                d = haversine_m(float(r["lat"]), float(r["lng"]),
                                float(fila["lat"]), float(fila["lng"]))
                if d <= 30 and name_sim(r["nombre"], fila["nombre"]) >= 0.5:
                    colision = r
                    break
            if colision:
                dups.append((fila["nombre"], colision["nombre"]))
            else:
                nuevas.append(fila)
                ex_por_ciudad.setdefault(p["ciudad"], []).append(fila)

        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            w.writerows(existentes + nuevas)
        total_nuevas += len(nuevas)
        print(f"{csv_name}: +{len(nuevas)} filas ({len(existentes)} -> {len(existentes)+len(nuevas)}) "
              f"· {len(dups)} ya estaban")
        for a, b in dups[:8]:
            print(f"    dup: {a!r} ~= {b!r}")

    print(f"\nagregadas {total_nuevas} filas en total")
    return total_nuevas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cruzar", action="store_true")
    ap.add_argument("--geocode", action="store_true")
    ap.add_argument("--solo-cache", action="store_true",
                    help="resuelve solo con lo ya cacheado, sin tocar la red")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if args.cruzar:
        cruzar()
    if args.geocode or args.solo_cache:
        geocode(solo_cache=args.solo_cache)
    if args.write:
        write()
    if not any((args.cruzar, args.geocode, args.write)):
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
