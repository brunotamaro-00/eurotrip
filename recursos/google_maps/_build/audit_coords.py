#!/usr/bin/env python3
"""
Auditoría de las coordenadas de los 1243 lugares, con 4 señales independientes.

Por qué 4 y no 1
----------------
`audit_existing.py` usaba una sola: re-resolver el nombre y medir la distancia
contra la coordenada guardada. Eso deja pasar dos clases de error:

  * el pin que cayó en el edificio de al lado — si la tolerancia del tipo es
    150 m, entra y se da por bueno;
  * el lugar que está en otra ciudad — `Mina de Sal de Wieliczka` figura bajo
    Cracovia y el reverse lo ubica en Wieliczka, a 13 km.

Las señales:

  S1 resolver   re-resuelve el nombre (Wikidata → Overpass → Nominatim → Photon)
                y compara distancias contra la tolerancia por tipo.
  S2 reverse    le pregunta al mapa qué hay EN la coordenada guardada.
                OJO: el reverse suele devolver la calle o plaza adyacente
                ("Piazza del Colosseo" para el Coliseo, "Avenue Gustave Eiffel"
                para la Torre Eiffel), así que la ausencia del nombre NO es
                prueba de error. Se usa como confirmador positivo, y solo la
                localidad distinta cuenta como señal negativa.
  S3 decimales  ≤3 decimales delata una coordenada tipeada a mano: 92 filas del
                pase anterior tienen `geo_source: manual_fix` sin procedencia.
  S4 encuadre   ¿cae dentro del área de su ciudad? Es el chequeo que hubiera
                atrapado el `Loch Cluanie` a 34 km del lago real.

Veredictos: `verificado` · `revisar` · `no_verificable`.
Nada se corrige acá; las correcciones van a `overrides.json`, que exige
`source`, `url` y `checked_at`.

Uso:
    python3 audit_coords.py --limit 20            # prueba
    python3 audit_coords.py --ciudad Londres
    python3 audit_coords.py                       # los 1243 (horas)
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import signal
import time
from pathlib import Path

import geo
from areas import AREAS, HIGHLANDS_KEYS, LABEL_TO_KEYS
from geoutil import decimals, haversine_m, normalize

HERE = Path(__file__).resolve().parent
REPORTS = HERE / "reports"

# Cuánto puede desviarse la coordenada guardada de la re-resuelta, por tipo.
# Un barrio o un valle admiten mucho más error que un museo. Calles y paseos
# son features LINEALES: Prinsengracht mide 3 km, Via Appia Antica 16.
TOLERANCIA_M: dict[str, float] = {
    "Museo": 150, "Iglesia": 150, "Catedral": 150, "Mirador": 150, "Teatro": 150,
    "Termas": 150, "Puente": 150, "Café": 120, "Bar": 120, "Tienda": 120,
    "Coffee shop": 120, "Smart shop": 120, "Ruin bar": 120, "Pub": 120,
    "Sitio histórico": 200, "Monumento": 200, "Escultura": 150, "Institución": 200,
    "Plaza": 250, "Fuente": 150, "Palacio": 200,
    "Mercado": 300, "Calle": 2000, "Paseo": 2000, "Parque": 600, "Jardín": 400,
    "Cementerio": 400, "Barrio": 1500, "Casco histórico": 1500, "Ciudad": 7000,
    "Pueblo": 6000, "Pueblo Route des Vins": 6000,
    "Faro": 200, "Castillo": 250, "Fuerte": 250, "Cascada": 300, "Cueva": 300,
    "Teleférico": 300, "Destilería": 250, "Cima": 400, "Playa": 500,
    "Naturaleza": 2000, "Paisaje": 2500, "Lago": 3000, "Valle": 3000,
    "Glen": 3000, "Parque nacional": 5000, "Trekking": 3000, "Ruta": 5000,
    "Excursión": 3000, "Day trip": 3000,
}
TOLERANCIA_DEFECTO = 300.0

REGION_HINT = {"Highlands": "Scotland, UK", "Edimburgo": "Scotland, UK"}

CAMPOS = ["csv", "csv_line", "ciudad", "nombre", "buscado", "tipo",
          "lat_csv", "lng_csv", "lat_res", "lng_res", "dist_m", "tolerancia_m",
          "s1_resolver", "s2_reverse", "s3_decimales", "s4_encuadre",
          "puntaje", "reverse_localidad", "reverse_que_hay", "fuente", "veredicto"]


def tolerancia(tipo: str) -> float:
    return TOLERANCIA_M.get(tipo, TOLERANCIA_DEFECTO)


def claves_de_area(ciudad: str) -> list[str]:
    if ciudad == "Highlands":
        return HIGHLANDS_KEYS
    return LABEL_TO_KEYS.get(ciudad, [])


def nombre_a_buscar(p: dict) -> str:
    """El primer segmento de `lugar_busqueda` está en idioma local.

    Comparar contra `nombre` (que está en español: "Puente de Carlos" en vez de
    "Karlův most") era lo que producía los 41 falsos `name_mismatch` del pase
    de build_maps.py.
    """
    cabeza = (p.get("lugar_busqueda") or "").split(",")[0].strip()
    return cabeza or p["nombre"]


def ciudad_esperada(p: dict) -> str:
    """Topónimo local de la ciudad, no el label en español.

    Nominatim habla en idioma local (`Greater London`, `Wien`, `Roma`). Comparar
    contra `p["ciudad"]` (`Londres`, `Viena`) produce falsos `s2=-1` en masa.
    El penúltimo segmento de `lugar_busqueda` ya está en el idioma correcto.
    """
    parts = [x.strip() for x in (p.get("lugar_busqueda") or "").split(",") if x.strip()]
    if len(parts) >= 2:
        return normalize(parts[-2])
    return normalize(p["ciudad"])


def s2_reverse(p: dict, nombre: str) -> tuple[int, dict]:
    """+1 si el mapa confirma el nombre en el punto; -1 si está en otra localidad."""
    rev = geo.reverse(p["lat"], p["lng"])
    if not rev:
        return 0, {}

    objetivo = normalize(nombre)
    display = normalize(rev.get("display", ""))
    name = normalize(rev.get("name", ""))
    # El reverse a zoom 18 suele devolver la calle/plaza adyacente
    # ("Piazza del Colosseo", "Avenue Gustave Eiffel"): basta con que el
    # nombre buscado aparezca en el display, no hace falta igualdad exacta.
    if objetivo and len(objetivo) >= 4 and (objetivo in display or objetivo in name):
        return 1, rev

    loc = normalize(rev.get("locality", ""))
    esperado = ciudad_esperada(p)
    if esperado and (esperado in loc or esperado in display or (loc and loc in esperado)):
        return 0, rev
    if loc and esperado and esperado not in loc and esperado not in display:
        return -1, rev
    return 0, rev


def auditar_uno(p: dict, cache: dict, overrides: dict) -> dict:
    ciudad = p["ciudad"]
    lat, lng = p["lat"], p["lng"]
    nombre = nombre_a_buscar(p)
    tol = tolerancia(p["tipo"])
    fila = {c: "" for c in CAMPOS}
    fila.update({"csv": p["csv"], "csv_line": p["csv_line"], "ciudad": ciudad,
                 "nombre": p["nombre"], "buscado": nombre, "tipo": p["tipo"],
                 "lat_csv": f"{lat:.6f}", "lng_csv": f"{lng:.6f}",
                 "tolerancia_m": f"{tol:.0f}"})

    ov = (overrides.get(f"{ciudad}::{geo.normalize(nombre)}")
          or overrides.get(f"{ciudad}::{geo.normalize(p['nombre'])}"))
    if ov:
        d = haversine_m(lat, lng, ov["lat"], ov["lng"])
        fila.update({"lat_res": f"{ov['lat']:.6f}", "lng_res": f"{ov['lng']:.6f}",
                     "dist_m": f"{d:.0f}", "fuente": ov["source"],
                     "veredicto": "verificado" if d < 50 else "revisar",
                     "s1_resolver": "override", "puntaje": "3"})
        return fila

    # --- S1: re-resolución multi-fuente ---
    claves = claves_de_area(ciudad)
    s1 = None
    if claves:
        res, area_ganadora = geo.resolve_multi(
            nombre, claves, p["tipo"], cache=cache,
            region_hint=REGION_HINT.get(ciudad, ""))
        if res.ok:
            d = haversine_m(lat, lng, res.lat, res.lng)
            s1 = 1 if d <= tol else (0 if d <= 3 * tol else -1)
            fila.update({"lat_res": f"{res.lat:.6f}", "lng_res": f"{res.lng:.6f}",
                         "dist_m": f"{d:.0f}", "fuente": f"{res.source}/{res.reason}"})
        else:
            fila["fuente"] = f"sin resolver: {res.reason}"
    else:
        fila["fuente"] = "sin area definida"
    fila["s1_resolver"] = "" if s1 is None else str(s1)

    # --- S2: reverse geocode ---
    s2, rev = s2_reverse(p, nombre)
    fila["s2_reverse"] = str(s2)
    fila["reverse_localidad"] = rev.get("locality", "")
    fila["reverse_que_hay"] = (rev.get("display", "") or "")[:90]

    # --- S3: precisión decimal ---
    s3 = 1 if min(decimals(lat), decimals(lng)) >= 4 else -1
    fila["s3_decimales"] = str(s3)

    # --- S4: encuadre en el área de la ciudad ---
    s4 = 0
    for k in claves:
        a = AREAS[k]
        if haversine_m(lat, lng, a.lat, a.lng) <= a.max_km * 1000:
            s4 = 1
            break
    else:
        if claves:
            s4 = -1
    fila["s4_encuadre"] = str(s4)

    puntaje = sum(x for x in (s1, s2, s3, s4) if x is not None)
    fila["puntaje"] = str(puntaje)

    # Day trips y pueblos caen fuera del ancla a propósito.
    daytrip = p["tipo"] in ("Day trip", "Pueblo", "Pueblo Route des Vins", "Ciudad")

    if s1 is None and s2 == 0:
        veredicto = "no_verificable"
    elif s1 == 1 and s2 != -1 and (s4 != -1 or daytrip):
        # Coordenada re-resuelta dentro de tolerancia: los pocos decimales
        # (s3=-1) son un warning de procedencia, no prueba de ubicación errónea.
        veredicto = "verificado"
    elif s1 == 0 and s2 != -1 and s4 == 1:
        veredicto = "verificado"
    elif s4 == -1 and s2 == 1 and (s1 is None or s1 >= 0) and daytrip:
        veredicto = "verificado"
    elif puntaje >= 2 and s1 != -1 and s4 != -1 and s2 != -1:
        veredicto = "verificado"
    else:
        veredicto = "revisar"
    fila["veredicto"] = veredicto
    return fila


def escribir(filas: list[dict], path: Path) -> None:
    if not filas:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    orden = {"revisar": 0, "no_verificable": 1, "verificado": 2}
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for r in sorted(filas, key=lambda x: (orden.get(x["veredicto"], 9),
                                              -float(x["dist_m"] or 0))):
            w.writerow(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ciudad")
    ap.add_argument("--csv", help="filtra por archivo de origen")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default="auditoria.csv")
    ap.add_argument("--overpass", action="store_true",
                    help="habilita Overpass (lento: hasta 70 s por fila)")
    args = ap.parse_args()
    geo.SKIP_OVERPASS = not args.overpass

    places = json.loads((HERE / "places.json").read_text(encoding="utf-8"))
    if args.ciudad:
        places = [p for p in places if p["ciudad"] == args.ciudad]
    if args.csv:
        places = [p for p in places if p["csv"] == args.csv]
    if args.limit:
        places = places[: args.limit]

    cache = geo.load_cache()
    overrides = geo.load_overrides()
    print(f"auditando {len(places)} lugares · {len(overrides)} overrides · caché {len(cache)}",
          flush=True)

    # Sin esto un SIGTERM mata el proceso antes del `finally` y se pierde todo
    # lo auditado hasta ese momento — que a 1 req/s son horas.
    parar = {"v": False}

    def _parar(signum, frame):
        parar["v"] = True
        print("  señal recibida: guardo el reporte parcial y salgo", flush=True)

    signal.signal(signal.SIGTERM, _parar)
    signal.signal(signal.SIGINT, _parar)

    filas: list[dict] = []
    t0 = time.time()
    try:
        for i, p in enumerate(places, 1):
            if parar["v"]:
                break
            filas.append(auditar_uno(p, cache, overrides))
            if i % 10 == 0:
                geo.save_cache(cache)
                escribir(filas, REPORTS / args.out)
                seg = (time.time() - t0) / i
                print(f"  {i}/{len(places)} · {seg:.1f}s/fila · faltan ~{seg * (len(places) - i) / 60:.0f} min",
                      flush=True)
    finally:
        geo.save_cache(cache)
        escribir(filas, REPORTS / args.out)

    c = collections.Counter(f["veredicto"] for f in filas)
    total = len(filas) or 1
    print(f"\nveredictos sobre {len(filas)}:")
    for k in ("verificado", "revisar", "no_verificable"):
        print(f"  {k:16} {c[k]:5}  ({100 * c[k] // total}%)")
    for f in filas:
        if f["veredicto"] == "revisar":
            print(f"  [revisar] {f['ciudad']} / {f['nombre']} · dist={f['dist_m']}m "
                  f"tol={f['tolerancia_m']}m · s1={f['s1_resolver']} s2={f['s2_reverse']} "
                  f"s3={f['s3_decimales']} s4={f['s4_encuadre']} · {f['reverse_localidad']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
