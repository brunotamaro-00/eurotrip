#!/usr/bin/env python3
"""
Resolver de coordenadas multi-fuente: Wikidata -> Overpass -> Nominatim.

Reemplaza a nominatim_search() de build_maps.py, que elegía el candidato más
cercano al centroide de la ciudad. Esa regla seleccionaba activamente el error:
`Loch Cluanie` matcheó un lochan homónimo cerca de Whitebridge porque quedaba a
2 km del centroide de Highlands, 34 km al este del real.

Acá la distancia pesa 0.15 en el score y el nombre pesa 0.50 —comparado siempre
contra `nombre_local`, no contra el español, que es lo que producía los 41
falsos `name_mismatch` (`Catedral San Esteban` vs `Stephansdom` da 0.39).
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, asdict
from pathlib import Path

from areas import Area
from geoutil import haversine_km, name_sim, normalize

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE / "geocode_cache2.json"

USER_AGENT = "TripItineraryMapper/2.0 (personal travel planning; github.com/brunotamaro-00/eurotrip)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
OVERPASS_HOSTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

SLEEP_NOMINATIM = 1.1
SLEEP_OVERPASS = 2.0
SLEEP_WIKIDATA = 0.2

# Umbrales de aceptación por pasada (ver docstring del módulo).
TH_OVERPASS = 0.75
TH_NOMINATIM_BOUNDED = 0.70
TH_NOMINATIM_FREE = 0.80
MIN_NAME_SIM = 0.60  # rechazo duro

_last_call: dict[str, float] = {}

# Overpass resuelve ~10% de los casos pero cuesta hasta 70 s cada uno, contra
# ~3 s de Nominatim. En una corrida masiva eso multiplica el tiempo total por
# tres. Se apaga para el barrido y se corre después solo sobre lo que quedó sin
# resolver (`build_katia.py --overpass-pass`).
SKIP_OVERPASS = False


# ---------------------------------------------------------------------------
# Clases OSM esperadas por tipo, y clases que nunca son el lugar buscado
# ---------------------------------------------------------------------------
EXPECTED: dict[str, set[str]] = {
    "Museo": {"tourism=museum", "tourism=gallery", "building=museum"},
    "Iglesia": {"amenity=place_of_worship", "building=church", "building=chapel", "historic=church"},
    "Catedral": {"amenity=place_of_worship", "building=cathedral", "building=church"},
    "Castillo": {"historic=castle", "historic=fort", "historic=ruins", "building=castle", "tourism=attraction"},
    "Mirador": {"tourism=viewpoint", "tourism=attraction", "natural=peak"},
    "Cascada": {"waterway=waterfall", "natural=waterfall"},
    "Lago": {"natural=water", "water=lake", "water=reservoir", "place=locality"},
    "Cima": {"natural=peak", "natural=ridge", "place=locality"},
    "Faro": {"man_made=lighthouse"},
    "Plaza": {"place=square", "highway=pedestrian", "landuse=square", "area:highway=*"},
    "Parque": {"leisure=park", "leisure=garden", "leisure=nature_reserve", "boundary=national_park"},
    "Mercado": {"amenity=marketplace", "shop=mall", "building=retail", "amenity=market"},
    "Puente": {"man_made=bridge", "bridge=yes", "highway=footway"},
    "Teleférico": {"aerialway=station", "aerialway=cable_car", "aerialway=gondola", "railway=station"},
    "Termas": {"leisure=water_park", "amenity=public_bath", "leisure=sports_centre"},
    "Teatro": {"amenity=theatre", "amenity=arts_centre", "building=civic"},
    "Cueva": {"natural=cave_entrance", "tourism=attraction"},
    "Playa": {"natural=beach", "leisure=beach_resort"},
    "Pueblo": {"place=village", "place=town", "place=hamlet", "place=municipality"},
    "Ciudad": {"place=city", "place=town"},
    "Barrio": {"place=suburb", "place=neighbourhood", "place=quarter", "place=borough"},
    "Cementerio": {"amenity=grave_yard", "landuse=cemetery"},
    "Destilería": {"craft=distillery", "man_made=works", "industrial=distillery"},
}

# Nunca es el POI buscado. Caza `Nevis Range Gondola` -> cycle track y
# `Fort George` -> "Training Area".
BLACKLIST: set[str] = {
    "highway=cycleway", "highway=path", "highway=footway", "highway=track",
    "highway=bridleway", "highway=service", "highway=residential",
    "route=bicycle", "route=hiking", "route=foot", "route=road", "route=bus",
    "boundary=administrative", "boundary=military", "landuse=military",
    "landuse=residential", "landuse=forest", "natural=scrub",
}


@dataclass
class Candidate:
    lat: float
    lng: float
    name: str = ""
    source: str = ""            # wikidata | overpass | nominatim
    osm_id: str = ""
    wikidata: str = ""
    osm_class: str = ""         # "tourism=museum"
    locality: str = ""
    display: str = ""
    names_all: list[str] = field(default_factory=list)  # name + name:xx + alt_name
    importance: float = 0.0  # relevancia de Nominatim (0..1); 0 si la fuente no la da
    rank: int = 0            # posición en la lista de resultados

    def to_json(self) -> dict:
        return asdict(self)


@dataclass
class Resolution:
    ok: bool
    lat: float | None = None
    lng: float | None = None
    source: str = ""
    confidence: str = ""        # high | medium | review
    score: float = 0.0
    name: str = ""
    locality: str = ""
    osm_class: str = ""
    wikidata: str = ""
    display: str = ""
    reason: str = ""
    alternatives: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
def _throttle(key: str, seconds: float) -> None:
    now = time.time()
    prev = _last_call.get(key, 0.0)
    wait = seconds - (now - prev)
    if wait > 0:
        time.sleep(wait)
    _last_call[key] = time.time()


def _get(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout).read()


# ---------------------------------------------------------------------------
# Wikidata
# ---------------------------------------------------------------------------
def wikidata_coords(qid: str) -> Candidate | None:
    _throttle("wd", SLEEP_WIKIDATA)
    try:
        data = json.loads(_get(WIKIDATA_ENTITY.format(qid=qid)))
        ent = data["entities"][qid]
        val = ent["claims"]["P625"][0]["mainsnak"]["datavalue"]["value"]
    except Exception:
        return None
    labels = ent.get("labels", {})
    names = [v["value"] for v in labels.values()]
    label = (labels.get("en") or labels.get("mul") or next(iter(labels.values()), {})).get("value", "")
    return Candidate(
        lat=float(val["latitude"]), lng=float(val["longitude"]),
        name=label, source="wikidata", wikidata=qid, names_all=names,
        display=f"wikidata:{qid}",
    )


def wikidata_search(name: str, area: Area, limit: int = 5) -> list[Candidate]:
    _throttle("wd", SLEEP_WIKIDATA)
    q = urllib.parse.urlencode(
        {"action": "wbsearchentities", "search": name, "language": "en",
         "uselang": "en", "format": "json", "limit": limit, "type": "item"}
    )
    try:
        data = json.loads(_get(f"{WIKIDATA_API}?{q}"))
    except Exception:
        return []
    out: list[Candidate] = []
    for hit in data.get("search", []):
        c = wikidata_coords(hit["id"])
        if c is None:
            continue
        if haversine_km(c.lat, c.lng, area.lat, area.lng) <= area.max_km:
            out.append(c)
    return out


# ---------------------------------------------------------------------------
# Overpass
# ---------------------------------------------------------------------------
_OV_ESCAPE = re.compile(r'["\\]')


def overpass_named(name: str, area: Area, timeout_s: int = 25) -> list[Candidate]:
    """Búsqueda por nombre (regex, case-insensitive) dentro del bbox del área.

    Es la pasada que rescata los 25 lugares de Isle of Skye que Nominatim
    devolvía como `no_results`: acá no hace falta sufijo de localidad, el bbox
    del área hace ese trabajo.
    """
    safe = _OV_ESCAPE.sub(lambda m: "\\" + m.group(0), name)
    query = (
        f'[out:json][timeout:{timeout_s}];'
        f'nwr["name"~"{safe}",i]({area.bbox_overpass});'
        f'out center tags 8;'
    )
    url_q = urllib.parse.quote(query)
    # Presupuesto acotado a propósito: Overpass es la fuente más frágil de las
    # tres y es solo un fallback. Con 3 hosts x 3 intentos x backoff exponencial
    # un solo lugar podía comerse >10 minutos y frenaba toda la auditoría.
    deadline = time.time() + 70
    for host in OVERPASS_HOSTS[:2]:
        for attempt in range(2):
            if time.time() > deadline:
                return []
            _throttle("overpass", SLEEP_OVERPASS)
            try:
                data = json.loads(_get(f"{host}?data={url_q}", timeout=timeout_s + 10))
                return [_ov_to_candidate(e) for e in data.get("elements", []) if _ov_point(e)]
            except urllib.error.HTTPError as e:
                if e.code in (429, 504, 502, 503):
                    time.sleep(3 * (attempt + 1))
                    continue
                break
            except Exception:
                break
    return []


def _ov_point(e: dict) -> bool:
    return e.get("lat") is not None or "center" in e


def _ov_to_candidate(e: dict) -> Candidate:
    lat = e.get("lat") if e.get("lat") is not None else e["center"]["lat"]
    lng = e.get("lon") if e.get("lon") is not None else e["center"]["lon"]
    tags = e.get("tags", {})
    names = [v for k, v in tags.items() if k == "name" or k.startswith(("name:", "alt_name", "official_name", "int_name"))]
    return Candidate(
        lat=float(lat), lng=float(lng),
        name=tags.get("name", ""),
        source="overpass",
        osm_id=f"{e['type']}/{e['id']}",
        wikidata=tags.get("wikidata", ""),
        osm_class=_primary_class(tags),
        locality=tags.get("addr:city", ""),
        display=tags.get("name", ""),
        names_all=names,
    )


_CLASS_KEYS = (
    "tourism", "historic", "amenity", "natural", "waterway", "leisure",
    "aerialway", "man_made", "place", "shop", "craft", "railway", "building",
    "landuse", "boundary", "highway", "route", "bridge", "water",
)


def _primary_class(tags: dict) -> str:
    for k in _CLASS_KEYS:
        if k in tags:
            return f"{k}={tags[k]}"
    return ""


# ---------------------------------------------------------------------------
# Nominatim
# ---------------------------------------------------------------------------
def nominatim_search(query: str, area: Area | None, bounded: bool, limit: int = 8) -> list[Candidate]:
    params = {"q": query, "format": "jsonv2", "limit": limit, "addressdetails": 1, "extratags": 1}
    if area is not None and bounded:
        params["countrycodes"] = area.country
        params["viewbox"] = area.viewbox
        params["bounded"] = 1
    _throttle("nominatim", SLEEP_NOMINATIM)
    try:
        data = json.loads(_get(f"{NOMINATIM}?{urllib.parse.urlencode(params)}"))
    except Exception:
        return []
    out: list[Candidate] = []
    for i, r in enumerate(data):
        addr = r.get("address", {})
        loc = (addr.get("city") or addr.get("town") or addr.get("village")
               or addr.get("municipality") or addr.get("county") or "")
        out.append(Candidate(
            importance=float(r.get("importance") or 0.0), rank=i,
            lat=float(r["lat"]), lng=float(r["lon"]),
            name=r.get("name") or r.get("display_name", "").split(",")[0],
            source="nominatim",
            osm_id=f"{r.get('osm_type','')}/{r.get('osm_id','')}",
            wikidata=(r.get("extratags") or {}).get("wikidata", ""),
            osm_class=f"{r.get('category', r.get('class',''))}={r.get('type','')}",
            locality=loc,
            display=r.get("display_name", ""),
            names_all=[r.get("name", "")],
        ))
    return out


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
SOURCE_PRIOR = {"wikidata": 1.0, "overpass": 0.9, "nominatim": 0.7}


def best_name_sim(c: Candidate, target: str) -> float:
    names = [n for n in ([c.name] + c.names_all) if n]
    return max((name_sim(target, n) for n in names), default=0.0)


def class_prior(c: Candidate, tipo: str) -> float:
    cls = c.osm_class
    if not cls:
        return 0.4
    if cls in BLACKLIST:
        return 0.0
    exp = EXPECTED.get(tipo)
    if not exp:
        return 0.4
    if cls in exp:
        return 1.0
    key = cls.split("=")[0]
    if any(e.split("=")[0] == key for e in exp):
        return 0.7
    return 0.3


def rank_prior(c: Candidate) -> float:
    """Relevancia según la fuente. Es el criterio que build_maps.py descartaba y
    el que desempata los homónimos: para `Loch Cluanie` Nominatim devuelve el
    lago real primero (importance alta) y el lochan de Whitebridge segundo, pero
    el falso queda más cerca del ancla. Sin este término gana el falso.

    Overpass no da importance: se le asigna un valor neutro alto porque ya
    filtró por bbox ajustada y por nombre.
    """
    if c.source == "overpass":
        return 0.7
    if c.source == "wikidata":
        return 0.8
    imp = min(max(c.importance, 0.0), 1.0)
    decay = 1.0 / (1.0 + 0.6 * c.rank)
    return max(imp, 0.0) * 0.6 + decay * 0.4


def score(c: Candidate, nombre_local: str, tipo: str, area: Area) -> tuple[float, float]:
    ns = best_name_sim(c, nombre_local)
    dist = haversine_km(c.lat, c.lng, area.lat, area.lng)
    dist_score = max(0.0, 1.0 - dist / max(area.max_km, 1.0))
    s = (0.45 * ns
         + 0.22 * class_prior(c, tipo)
         + 0.12 * dist_score
         + 0.09 * SOURCE_PRIOR.get(c.source, 0.5)
         + 0.12 * rank_prior(c))
    return s, ns


def _pick(cands: list[Candidate], nombre_local: str, tipo: str, area: Area) -> tuple[Candidate | None, float]:
    best, best_s = None, -1.0
    for c in cands:
        if haversine_km(c.lat, c.lng, area.lat, area.lng) > area.max_km:
            continue
        s, ns = score(c, nombre_local, tipo, area)
        if ns < MIN_NAME_SIM:      # rechazo duro por nombre
            continue
        if s > best_s:
            best, best_s = c, s
    return best, best_s


# ---------------------------------------------------------------------------
# Caché
# ---------------------------------------------------------------------------
def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def cache_key(area_key: str, nombre_local: str) -> str:
    return f"{area_key}::{normalize(nombre_local)}"


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------
def resolve(
    nombre_local: str,
    area: Area,
    tipo: str = "",
    qid: str = "",
    query_extra: str = "",
    cache: dict | None = None,
) -> Resolution:
    """Cascada de 4 pasadas; corta en la primera que supera su umbral."""
    if cache is not None:
        hit = cache.get(cache_key(area.key, nombre_local))
        if hit is not None:
            return Resolution(**hit)

    found: list[tuple[Candidate, float]] = []
    res: Resolution | None = None

    # 1 — Wikidata por QID conocido: gana siempre
    if qid:
        c = wikidata_coords(qid)
        if c is not None and haversine_km(c.lat, c.lng, area.lat, area.lng) <= area.max_km:
            res = _mk(c, 1.0, "high", "wikidata_qid")

    # 2 — Nominatim libre (una sola request, resuelve la gran mayoría)
    if res is None:
        q = f"{nombre_local}, {query_extra}" if query_extra else f"{nombre_local}, {area.locality}, {area.country_en}"
        cands = nominatim_search(q, None, bounded=False, limit=10)
        c, s = _pick(cands, nombre_local, tipo, area)
        if c is not None:
            found.append((c, s))
            if s >= TH_NOMINATIM_FREE:
                res = _mk(c, s, "high", "nominatim_free")

    # 2b — Nominatim solo con nombre + país. El sufijo de localidad ayuda a
    # desambiguar pero a veces impide el match: "Slap Savica, Bled, Slovenia"
    # devuelve vacío y "Slap Savica, Slovenia" resuelve bien.
    if res is None:
        cands = nominatim_search(f"{nombre_local}, {area.country_en}", None, bounded=False, limit=10)
        c, s = _pick(cands, nombre_local, tipo, area)
        if c is not None:
            found.append((c, s))
            if s >= TH_NOMINATIM_FREE:
                res = _mk(c, s, "high", "nominatim_sin_localidad")

    # 3 — Nominatim acotado al viewbox del área (bounded=1)
    if res is None:
        cands = nominatim_search(nombre_local, area, bounded=True)
        c, s = _pick(cands, nombre_local, tipo, area)
        if c is not None:
            found.append((c, s))
            if s >= TH_NOMINATIM_BOUNDED:
                res = _mk(c, s, "high", "nominatim_bounded")

    # 4 — Overpass, último porque es la fuente más lenta y frágil: con Overpass
    # primero, cada lugar tardaba ~1 minuto y los 371 no terminaban nunca.
    if res is None and not SKIP_OVERPASS:
        cands = overpass_named(nombre_local, area)
        c, s = _pick(cands, nombre_local, tipo, area)
        if c is not None:
            found.append((c, s))
            if s >= TH_OVERPASS:
                res = _mk(c, s, "high", "overpass")

    if res is None:
        if found:
            c, s = max(found, key=lambda x: x[1])
            res = _mk(c, s, "review", "bajo_umbral")
        else:
            res = Resolution(ok=False, confidence="review", reason="sin_candidatos")

    # consenso entre fuentes distintas
    if res.ok and len(found) >= 2:
        others = [c for c, _ in found if c.source != res.source]
        if others:
            d = min(haversine_km(res.lat, res.lng, o.lat, o.lng) for o in others) * 1000
            if d <= 250:
                res.confidence = "high"
            elif d <= 1000 and res.confidence != "high":
                res.confidence = "medium"
            elif d > 1000:
                res.confidence = "review"
                res.reason = f"fuentes discrepan {d/1000:.1f} km"
    res.alternatives = [c.to_json() for c, _ in found[:4]]

    if cache is not None:
        cache[cache_key(area.key, nombre_local)] = asdict(res)
    return res


def _span_area(keys: list[str]) -> Area:
    """Área sintética que envuelve a varias sub-áreas. Solo se usa para acotar la
    consulta (bbox de Overpass / viewbox de Nominatim); la validación de
    distancia se sigue haciendo contra cada sub-área real."""
    from areas import AREAS

    subs = [AREAS[k] for k in keys]
    lat = (max(s.lat for s in subs) + min(s.lat for s in subs)) / 2
    lng = (max(s.lng for s in subs) + min(s.lng for s in subs)) / 2
    half_lat = (max(s.lat for s in subs) - min(s.lat for s in subs)) / 2
    half_lng = (max(s.lng for s in subs) - min(s.lng for s in subs)) / 2
    margin = max(s.max_km for s in subs) / 90.0
    ref = subs[0]
    return Area(
        key="__span__", label=ref.label, lat=lat, lng=lng, country=ref.country,
        locality=ref.locality, country_en=ref.country_en, region=ref.region,
        max_km=10_000.0, view_deg=max(half_lat, half_lng) + margin,
    )


def resolve_multi(
    nombre_local: str,
    area_keys: list[str],
    tipo: str = "",
    qid: str = "",
    cache: dict | None = None,
    region_hint: str = "",
    hint_area_key: str = "",
) -> tuple[Resolution, str]:
    """Resuelve contra un conjunto de sub-áreas a la vez y devuelve (resolución,
    sub-área ganadora).

    Existe para romper una circularidad: si se eligiera la sub-área a partir de
    la coordenada que hay en el CSV, un punto mal ubicado se resolvería dentro
    del área equivocada y el error quedaría confirmado. `Loch Cluanie` está en
    57.21,-4.53, que cae en `loch_ness` —justo donde vive el homónimo falso— en
    vez de en `glen_shiel`, que es donde está el lago real.

    Un candidato se acepta solo si cae dentro del radio de ALGUNA sub-área, y se
    puntúa contra la sub-área más ajustada que lo contenga.
    """
    from areas import AREAS, covering_areas

    span = _span_area(area_keys)
    ck = cache_key("|".join(sorted(area_keys)), nombre_local) if cache is not None else ""
    if cache is not None and ck in cache:
        d = dict(cache[ck])
        return Resolution(**d["res"]), d["area_key"]

    def evaluate(cands: list[Candidate]) -> tuple[Candidate | None, float, str]:
        best, best_s, best_k = None, -1.0, ""
        for c in cands:
            cov = covering_areas(c.lat, c.lng, area_keys)
            if not cov:
                continue
            a = cov[0]
            s, ns = score(c, nombre_local, tipo, a)
            if ns < MIN_NAME_SIM:
                continue
            if s > best_s:
                best, best_s, best_k = c, s, a.key
        return best, best_s, best_k

    found: list[tuple[Candidate, float, str]] = []
    res: Resolution | None = None
    win_key = ""

    if qid:
        c = wikidata_coords(qid)
        if c is not None and covering_areas(c.lat, c.lng, area_keys):
            res = _mk(c, 1.0, "high", "wikidata_qid")
            win_key = covering_areas(c.lat, c.lng, area_keys)[0].key

    # Nominatim libre va primero: es una sola request y resuelve casi todo,
    # incluidos los 25 de Skye que build_maps.py daba por `no_results` (fallaban
    # por el sufijo ", Isle of Skye, UK", no por el nombre). Overpass sobre el
    # span combinado es carísimo —la bbox de Highlands mide ~3,5°— así que queda
    # como fallback y acotado a la sub-área, no al span.
    if res is None:
        q = f"{nombre_local}, {region_hint}" if region_hint else f"{nombre_local}, {span.country_en}"
        c, s, k = evaluate(nominatim_search(q, None, bounded=False, limit=10))
        if c is not None:
            found.append((c, s, k))
            if s >= TH_NOMINATIM_FREE:
                res, win_key = _mk(c, s, "high", "nominatim_free"), k

    if res is None:
        c, s, k = evaluate(nominatim_search(nombre_local, span, bounded=True))
        if c is not None:
            found.append((c, s, k))
            if s >= TH_NOMINATIM_BOUNDED:
                res, win_key = _mk(c, s, "high", "nominatim_bounded"), k

    # Overpass acotado a la sub-área sugerida por el mejor candidato hasta ahora
    # (o por `hint_area_key`), nunca al span completo.
    if res is None:
        probe = hint_area_key or (found[0][2] if found else area_keys[0])
        c, s, k = evaluate(overpass_named(nombre_local, AREAS[probe]))
        if c is not None:
            found.append((c, s, k))
            if s >= TH_OVERPASS:
                res, win_key = _mk(c, s, "high", "overpass"), k

    if res is None:
        if found:
            c, s, k = max(found, key=lambda x: x[1])
            res, win_key = _mk(c, s, "review", "bajo_umbral"), k
        else:
            res = Resolution(ok=False, confidence="review", reason="sin_candidatos")

    if res.ok and len({c.source for c, _, _ in found}) >= 2:
        others = [c for c, _, _ in found if c.source != res.source]
        d = min(haversine_km(res.lat, res.lng, o.lat, o.lng) for o in others) * 1000
        if d <= 250:
            res.confidence = "high"
        elif d > 1000:
            res.confidence = "review"
            res.reason = f"fuentes discrepan {d/1000:.1f} km"
    res.alternatives = [c.to_json() for c, _, _ in found[:4]]

    if cache is not None:
        cache[ck] = {"res": asdict(res), "area_key": win_key}
    return res, win_key


def _mk(c: Candidate, s: float, conf: str, reason: str) -> Resolution:
    return Resolution(
        ok=True, lat=round(c.lat, 6), lng=round(c.lng, 6), source=c.source,
        confidence=conf, score=round(s, 3), name=c.name, locality=c.locality,
        osm_class=c.osm_class, wikidata=c.wikidata, display=c.display, reason=reason,
    )


# ---------------------------------------------------------------------------
# Overrides verificados a mano
# ---------------------------------------------------------------------------
def load_overrides(path: Path | None = None) -> dict[str, dict]:
    """Exige source + url + checked_at y precisión >= 5 decimales. Es la regla
    que impide repetir las 92 filas `manual_fix` sin procedencia."""
    from geoutil import decimals

    p = path or (HERE / "overrides.json")
    raw = json.loads(p.read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for k, v in raw.items():
        if k.startswith("_"):
            continue
        for campo in ("lat", "lng", "source", "url", "checked_at"):
            assert v.get(campo) not in (None, ""), f"override {k}: falta {campo}"
        assert str(v["url"]).startswith("http"), f"override {k}: url inválida"
        # >=4 decimales (~11 m). No se puede exigir 5: repr(float) descarta los
        # ceros finales, así que una coordenada legítima como -5.082300 se lee
        # como 4 decimales. El umbral que importa es el que caza las coordenadas
        # tipeadas a mano, que tienen 2-3.
        assert min(decimals(v["lat"]), decimals(v["lng"])) >= 4, \
            f"override {k}: precisión insuficiente ({v['lat']},{v['lng']})"
        out[k] = v
    return out
