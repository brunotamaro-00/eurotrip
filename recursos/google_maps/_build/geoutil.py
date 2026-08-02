#!/usr/bin/env python3
"""Utilidades compartidas: distancia, normalización de nombres y similitud.

`token_set_ratio` está implementado a mano sobre difflib para no depender de
rapidfuzz (no está instalado y esto corre con el Python del sistema).
"""
from __future__ import annotations

import difflib
import math
import re
import unicodedata

EARTH_R_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_KM * math.asin(math.sqrt(a))


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    return haversine_km(lat1, lng1, lat2, lng2) * 1000.0


# ---------------------------------------------------------------------------
# Normalización de nombres
# ---------------------------------------------------------------------------

# Stopwords bilingües: artículos, preposiciones y sustantivos de categoría que
# aparecen en un idioma y no en el otro ("Puente de Carlos" vs "Karlův most").
# Sacarlos deja solo el núcleo distintivo, que es lo que compara el dedup.
STOPWORDS: frozenset[str] = frozenset("""
de del la el los las un una the of and y e a al o or
di da il lo gli le dei della delle du des le la les au aux
van der den het een zu zur zum am im in on
na pod nad przy sv st sta ste sto santa santo san saint sankt
museo museum musee musée muzeum muzej museu
iglesia church kirche chiesa chram kostel kostol cerkev igreja eglise église
catedral cathedral dom duomo katedra stolnica se
basilica basilique bazilika
plaza piazza platz square place namesti namestie trg ter plein praca praça
puente bridge brucke brücke most ponte pont brug
castillo castle schloss chateau château castel zamek grad hrad kasteel
torre tower turm veza vez
palacio palace palazzo palac palais paleis palast
parque park parc giardino jardin jardim vrt
mercado market markt marche marché mercato mercat trznica
calle street strasse straße rue via gasse utca ulica ulice straat
monte mount mont monti berg hora gora
lago lake lac see jezero jezioro meer
rio river fluss fiume riviere rivière reka rzeka
casa house haus maison huis
"""
.split())

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def normalize(name: str) -> str:
    """minúsculas, sin acentos, sin puntuación, sin apóstrofes (los pega:
    `dell'Ovo` -> `dellovo`)."""
    s = strip_accents(name).lower()
    s = s.replace("'", "").replace("’", "").replace("´", "")
    s = _PUNCT_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


def tokens(name: str) -> list[str]:
    return [t for t in normalize(name).split() if t]


def token_key(name: str) -> frozenset[str]:
    """Núcleo distintivo del nombre: tokens sin stopwords ni numerales sueltos.
    Si al sacar stopwords no queda nada (ej. "Duomo"), se devuelven los tokens
    originales para no colapsar todos esos nombres en el conjunto vacío."""
    ts = [t for t in tokens(name) if t not in STOPWORDS and len(t) > 1]
    return frozenset(ts) if ts else frozenset(tokens(name))


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def token_set_ratio(a: str, b: str) -> float:
    """Equivalente a rapidfuzz.fuzz.token_set_ratio, en 0..100.

    Compara la intersección de tokens contra cada resto, que es lo que hace que
    "Castillo de Praga" y "Castillo de Praga (Hradčany)" den ~100 aunque uno
    tenga tokens de más.
    """
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    s_inter = " ".join(sorted(inter))
    s_a = (s_inter + " " + " ".join(sorted(ta - inter))).strip()
    s_b = (s_inter + " " + " ".join(sorted(tb - inter))).strip()
    best = max(
        _ratio(s_inter, s_a) if s_inter else 0.0,
        _ratio(s_inter, s_b) if s_inter else 0.0,
        _ratio(s_a, s_b),
    )
    return round(best * 100, 2)


def name_sim(a: str, b: str) -> float:
    """0..1. Toma el mejor entre el ratio directo y el token_set_ratio, para no
    penalizar el orden de las palabras."""
    if not a or not b:
        return 0.0
    na, nb = normalize(a), normalize(b)
    if na == nb:
        return 1.0
    return max(_ratio(na, nb), token_set_ratio(a, b) / 100.0)


def decimals(x: float) -> int:
    s = repr(float(x))
    return len(s.split(".")[1]) if "." in s else 0
