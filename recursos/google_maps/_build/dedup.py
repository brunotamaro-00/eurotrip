#!/usr/bin/env python3
"""
Dedup de los lugares nuevos (notas-katia) contra las 585 filas existentes.

Regla dura: NUNCA se deduplica entre `area_key` distintas. Es lo que evita
colapsar "Panteón" (Roma vs París), "Arco del Triunfo" (París vs Innsbruck),
"Mercado Central" (Florencia/Liubliana/Budapest), "Altstadt" (Lucerna, Friburgo,
Innsbruck, Berna) y "50 Kalò" (Roma vs Nápoles).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from geoutil import haversine_m, normalize, token_key, token_set_ratio

# Umbrales
RATIO_AUTO = 96.0      # >= : mismo lugar, drop automático
RATIO_REVIEW = 88.0    # >= : a revisión manual
PROX_URBANO_M = 150.0
PROX_NATURAL_M = 400.0

TIPOS_NATURALES = {
    "Paisaje", "Naturaleza", "Lago", "Valle", "Glen", "Trekking", "Cima",
    "Cascada", "Parque nacional", "Playa", "Ruta", "Cueva", "Excursión",
}


@dataclass
class Match:
    new_id: str
    new_nombre: str
    old_nombre: str
    area_key: str
    rule: str          # A | B | C | D | E
    score: float
    dist_m: float | None = None
    action: str = ""   # drop | review


@dataclass
class Existing:
    ciudad: str
    nombre: str
    lugar_busqueda: str
    lat: float
    lng: float
    tipo: str
    area_key: str = ""
    keys: frozenset[str] = field(default_factory=frozenset)


def load_existing(csv_paths: list[Path], label_to_area: dict[str, str]) -> list[Existing]:
    out: list[Existing] = []
    for p in csv_paths:
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                e = Existing(
                    ciudad=r["ciudad"],
                    nombre=r["nombre"],
                    lugar_busqueda=r["lugar_busqueda"],
                    lat=float(r["lat"]),
                    lng=float(r["lng"]),
                    tipo=r["tipo"],
                    area_key=label_to_area.get(r["ciudad"], ""),
                )
                e.keys = token_key(e.nombre)
                out.append(e)
    return out


def _candidate_names(place: dict) -> list[str]:
    names = [place.get("nombre", ""), place.get("nombre_local", "")]
    names += place.get("alias_es", []) or []
    return [n for n in names if n]


def _existing_names(e: Existing) -> list[str]:
    # el primer segmento de lugar_busqueda es el nombre real que se buscó
    head = e.lugar_busqueda.split(",")[0].strip()
    return [n for n in {e.nombre, head} if n]


def _prox_threshold(tipo: str) -> float:
    return PROX_NATURAL_M if tipo in TIPOS_NATURALES else PROX_URBANO_M


def find_duplicates(
    new_places: list[dict],
    existing: list[Existing],
    area_of: dict[str, str] | None = None,
) -> list[Match]:
    """Pasadas A-D (sin coordenadas). La pasada E corre aparte, post-geocoding."""
    by_area: dict[str, list[Existing]] = {}
    for e in existing:
        if e.area_key:
            by_area.setdefault(e.area_key, []).append(e)

    # Highlands: las sub-áreas comparten pool, porque el CSV existente no las distingue
    def pool(area_key: str) -> list[Existing]:
        from areas import AREAS, HIGHLANDS_KEYS

        if area_key in HIGHLANDS_KEYS:
            res: list[Existing] = []
            for k in HIGHLANDS_KEYS:
                res.extend(by_area.get(k, []))
            return res
        # sub-áreas de una misma base comparten label
        a = AREAS.get(area_key)
        if a is None:
            return by_area.get(area_key, [])
        res = []
        for k, v in by_area.items():
            if AREAS[k].label == a.label:
                res.extend(v)
        return res

    matches: list[Match] = []
    for p in new_places:
        ak = p["area_key"]
        cands = pool(ak)
        if not cands:
            continue
        new_names = _candidate_names(p)
        new_keys = token_key(p.get("nombre_local") or p["nombre"])
        best: Match | None = None

        for e in cands:
            old_names = _existing_names(e)

            # A — alias explícito / nombre normalizado idéntico
            if any(normalize(a) == normalize(b) for a in new_names for b in old_names):
                best = Match(p["id"], p["nombre"], e.nombre, ak, "A", 100.0, action="drop")
                break

            # B — token-set exacto
            if new_keys and any(new_keys == token_key(b) for b in old_names):
                best = Match(p["id"], p["nombre"], e.nombre, ak, "B", 100.0, action="drop")
                break

            # C / D — similitud alta o subconjunto
            ratio = max(token_set_ratio(a, b) for a in new_names for b in old_names)
            subset = any(
                new_keys and token_key(b) and (new_keys <= token_key(b) or token_key(b) <= new_keys)
                for b in old_names
            )
            if ratio >= RATIO_AUTO:
                cand = Match(p["id"], p["nombre"], e.nombre, ak, "C", ratio, action="drop")
            elif ratio >= RATIO_REVIEW:
                cand = Match(p["id"], p["nombre"], e.nombre, ak, "C", ratio, action="review")
            elif subset:
                cand = Match(p["id"], p["nombre"], e.nombre, ak, "D", ratio, action="review")
            else:
                continue
            if best is None or cand.score > best.score:
                best = cand

        if best is not None:
            matches.append(best)
    return matches


def find_proximity_dupes(
    new_geocoded: list[dict],
    existing: list[Existing],
) -> list[Match]:
    """Pasada E — post-geocoding. Es la única que caza los duplicados con nombres
    completamente distintos (Praga `Reloj Astronómico` ≡ `Torre del Ayuntamiento
    Viejo`, cuyo token_set_ratio es ~20)."""
    from areas import AREAS, HIGHLANDS_KEYS

    out: list[Match] = []
    for p in new_geocoded:
        if p.get("lat") is None:
            continue
        ak = p["area_key"]
        label = AREAS[ak].label if ak in AREAS else None
        thr = _prox_threshold(p.get("tipo", ""))
        for e in existing:
            same_area = (
                e.area_key == ak
                or (e.area_key in HIGHLANDS_KEYS and ak in HIGHLANDS_KEYS)
                or (label and e.ciudad == label)
            )
            if not same_area:
                continue
            d = haversine_m(p["lat"], p["lng"], e.lat, e.lng)
            if d <= thr:
                out.append(
                    Match(p["id"], p["nombre"], e.nombre, ak, "E", 0.0, round(d, 1), "review")
                )
                break
    return out


def dedup_internal(places: list[dict]) -> list[Match]:
    """Duplicados dentro del propio katia_places.json."""
    seen: dict[tuple[str, frozenset[str]], dict] = {}
    out: list[Match] = []
    for p in places:
        k = (p["area_key"], token_key(p.get("nombre_local") or p["nombre"]))
        if k in seen:
            out.append(
                Match(p["id"], p["nombre"], seen[k]["nombre"], p["area_key"], "B", 100.0, action="drop")
            )
        else:
            seen[k] = p
    return out


def write_report(matches: list[Match], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["new_id", "nombre_nuevo", "nombre_existente", "area_key", "regla", "score", "dist_m", "accion"])
        for m in sorted(matches, key=lambda x: (x.action, x.area_key, -x.score)):
            w.writerow([m.new_id, m.new_nombre, m.old_nombre, m.area_key, m.rule,
                        m.score, m.dist_m if m.dist_m is not None else "", m.action])
