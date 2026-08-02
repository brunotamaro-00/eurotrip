#!/usr/bin/env python3
"""
Áreas de geocodificación.

Reemplaza la lista CITIES de build_maps.py (congelado). Dos diferencias de fondo:

1. `max_km <= 25` y `view_deg <= 0.30` SIEMPRE. En build_maps.py Highlands tenía
   max_km=220 / view_deg=3.5, lo que dejaba pasar cualquier punto de Escocia y
   produjo el error de Loch Cluanie (~30 km).
2. Un área puede ser sub-área de otra (`parent`). El CSV usa `label` en la columna
   `ciudad`, así que las 10 sub-áreas de Highlands siguen escribiendo "Highlands".
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Area:
    key: str
    label: str        # columna `ciudad` del CSV
    lat: float        # ancla para validar distancia
    lng: float
    country: str      # ISO2 para Nominatim
    locality: str     # localidad para `lugar_busqueda`
    country_en: str   # país en inglés para `lugar_busqueda`
    region: str       # occidental | central | sur | katia
    max_km: float = 25.0
    view_deg: float = 0.30
    parent: str | None = None

    @property
    def viewbox(self) -> str:
        """left,top,right,bottom — el orden que espera Nominatim."""
        d = self.view_deg
        return f"{self.lng - d},{self.lat + d},{self.lng + d},{self.lat - d}"

    @property
    def bbox_overpass(self) -> str:
        """south,west,north,east — el orden que espera Overpass."""
        d = self.view_deg
        return f"{self.lat - d},{self.lng - d},{self.lat + d},{self.lng + d}"


def _a(*args, **kwargs) -> Area:
    a = Area(*args, **kwargs)
    assert a.max_km <= 25.0, f"{a.key}: max_km={a.max_km} > 25"
    assert a.view_deg <= 0.30, f"{a.key}: view_deg={a.view_deg} > 0.30"
    return a


# ---------------------------------------------------------------------------
# Bases existentes en los 3 CSV
# ---------------------------------------------------------------------------
_BASE: list[Area] = [
    _a("londres", "Londres", 51.5074, -0.1278, "gb", "London", "UK", "occidental", 22, 0.28),
    _a("york", "York", 53.9591, -1.0815, "gb", "York", "UK", "occidental", 12, 0.15),
    _a("edimburgo", "Edimburgo", 55.9533, -3.1883, "gb", "Edinburgh", "UK", "occidental", 15, 0.20),
    _a("amsterdam", "Ámsterdam", 52.3676, 4.9041, "nl", "Amsterdam", "Netherlands", "occidental", 18, 0.22),
    _a("paris", "París", 48.8566, 2.3522, "fr", "Paris", "France", "occidental", 20, 0.25),
    _a("colmar", "Colmar", 48.0794, 7.3586, "fr", "Colmar", "France", "occidental", 12, 0.15),
    _a("estrasburgo", "Estrasburgo", 48.5734, 7.7521, "fr", "Strasbourg", "France", "occidental", 15, 0.18),
    _a("lisboa", "Lisboa", 38.7223, -9.1393, "pt", "Lisboa", "Portugal", "sur", 20, 0.25),
    _a("porto", "Porto", 41.1579, -8.6291, "pt", "Porto", "Portugal", "sur", 15, 0.20),
    _a("friburgo", "Friburgo", 47.9990, 7.8421, "de", "Freiburg im Breisgau", "Germany", "central", 15, 0.18),
    _a("grindelwald", "Grindelwald", 46.6242, 8.0414, "ch", "Grindelwald", "Switzerland", "central", 15, 0.18),
    _a("interlaken", "Interlaken", 46.6863, 7.8632, "ch", "Interlaken", "Switzerland", "central", 20, 0.25),
    _a("lauterbrunnen", "Lauterbrunnen", 46.5937, 7.9091, "ch", "Lauterbrunnen", "Switzerland", "central", 15, 0.18),
    _a("lucerna", "Lucerna", 47.0502, 8.3093, "ch", "Luzern", "Switzerland", "central", 20, 0.25),
    _a("innsbruck", "Innsbruck", 47.2692, 11.4041, "at", "Innsbruck", "Austria", "central", 20, 0.25),
    _a("viena", "Viena", 48.2082, 16.3738, "at", "Wien", "Austria", "central", 18, 0.22),
    _a("praga", "Praga", 50.0755, 14.4378, "cz", "Praha", "Czechia", "central", 18, 0.22),
    _a("cracovia", "Cracovia", 50.0647, 19.9450, "pl", "Kraków", "Poland", "central", 15, 0.20),
    _a("budapest", "Budapest", 47.4979, 19.0402, "hu", "Budapest", "Hungary", "central", 18, 0.22),
]

# ---------------------------------------------------------------------------
# Highlands: 10 sub-áreas.
#
# En build_maps.py era UN área con max_km=220. Con ese radio la validación no
# validaba nada y el desempate "candidato más cercano al centroide (57.2,-4.5)"
# elegía activamente homónimos equivocados: `Loch Cluanie` matcheó un lochan de
# Whitebridge que estaba a 2 km del centroide, 30 km al este del real.
#
# Partido así, Loch Cluanie cae en `glen_shiel` (ancla 57.15,-5.30) y el falso
# de Whitebridge queda a ~47 km del ancla → rechazado automáticamente.
# ---------------------------------------------------------------------------
_HIGHLANDS: list[Area] = [
    _a("skye_norte", "Highlands", 57.4100, -6.1900, "gb", "Portree", "UK", "occidental", 25, 0.30, "highlands"),
    _a("skye_sur", "Highlands", 57.2900, -6.1700, "gb", "Sligachan", "UK", "occidental", 22, 0.28, "highlands"),
    _a("glencoe", "Highlands", 56.6800, -5.1000, "gb", "Glencoe", "UK", "occidental", 18, 0.22, "highlands"),
    _a("fort_william", "Highlands", 56.8200, -5.1100, "gb", "Fort William", "UK", "occidental", 20, 0.25, "highlands"),
    _a("road_to_isles", "Highlands", 57.0000, -5.8300, "gb", "Mallaig", "UK", "occidental", 25, 0.30, "highlands"),
    _a("glen_shiel", "Highlands", 57.1500, -5.3000, "gb", "Highland", "UK", "occidental", 22, 0.28, "highlands"),
    _a("loch_ness", "Highlands", 57.3300, -4.4800, "gb", "Drumnadrochit", "UK", "occidental", 25, 0.30, "highlands"),
    _a("inverness", "Highlands", 57.4800, -4.2200, "gb", "Inverness", "UK", "occidental", 20, 0.25, "highlands"),
    _a("cairngorms", "Highlands", 57.1900, -3.8300, "gb", "Aviemore", "UK", "occidental", 25, 0.30, "highlands"),
    _a("torridon_applecross", "Highlands", 57.5500, -5.6000, "gb", "Highland", "UK", "occidental", 25, 0.30, "highlands"),
]

# Highlands tiene además filas fuera de las Highlands propiamente dichas
# (Stirling, Falkirk, Pitlochry, Oban, Loch Lomond) que el CSV asignó a esa base.
_HIGHLANDS_EXTRA: list[Area] = [
    _a("perthshire", "Highlands", 56.7000, -3.7500, "gb", "Pitlochry", "UK", "occidental", 25, 0.30, "highlands"),
    _a("stirling_falkirk", "Highlands", 56.0600, -3.9400, "gb", "Stirling", "UK", "occidental", 25, 0.30, "highlands"),
    _a("oban_lomond", "Highlands", 56.3300, -5.2000, "gb", "Oban", "UK", "occidental", 25, 0.30, "highlands"),
]

# ---------------------------------------------------------------------------
# Bases nuevas que aportan los notas-katia.md (sin ninguna fila en los CSV)
# ---------------------------------------------------------------------------
_KATIA: list[Area] = [
    _a("roma", "Roma", 41.9028, 12.4964, "it", "Roma", "Italy", "katia", 20, 0.25),
    _a("napoles", "Nápoles", 40.8518, 14.2681, "it", "Napoli", "Italy", "katia", 15, 0.20),
    _a("florencia", "Florencia", 43.7696, 11.2558, "it", "Firenze", "Italy", "katia", 12, 0.15),
    _a("berna", "Berna", 46.9480, 7.4474, "ch", "Bern", "Switzerland", "katia", 12, 0.15),
    _a("kandersteg", "Kandersteg", 46.4950, 7.6750, "ch", "Kandersteg", "Switzerland", "katia", 15, 0.18),
    _a("liubliana", "Liubliana", 46.0569, 14.5058, "si", "Ljubljana", "Slovenia", "katia", 15, 0.18),
    _a("bled", "Lagos Alpinos", 46.3690, 14.1136, "si", "Bled", "Slovenia", "katia", 25, 0.30),
    _a("karst", "Karst y Cuevas", 45.7800, 14.2000, "si", "Postojna", "Slovenia", "katia", 25, 0.30),
    _a("soca", "Valle del Soča", 46.2500, 13.6000, "si", "Bovec", "Slovenia", "katia", 25, 0.30),
    _a("trieste", "Trieste", 45.6495, 13.7768, "it", "Trieste", "Italy", "katia", 15, 0.18),
    _a("piran", "Costa Eslovena", 45.5285, 13.5683, "si", "Piran", "Slovenia", "katia", 20, 0.25),
]

AREAS: dict[str, Area] = {
    a.key: a for a in _BASE + _HIGHLANDS + _HIGHLANDS_EXTRA + _KATIA
}

# Áreas que representan la base "Highlands" del CSV.
HIGHLANDS_KEYS: list[str] = [a.key for a in _HIGHLANDS + _HIGHLANDS_EXTRA]

# label -> keys candidatas (una base del CSV puede tener varias sub-áreas)
LABEL_TO_KEYS: dict[str, list[str]] = {}
for _area in AREAS.values():
    LABEL_TO_KEYS.setdefault(_area.label, []).append(_area.key)

COUNTRIES_EN: set[str] = {a.country_en for a in AREAS.values()}


def area_for_label(label: str) -> Area:
    """Área principal de una base del CSV. Para Highlands devuelve la primera
    sub-área; el asignador real vive en audit_existing.py."""
    keys = LABEL_TO_KEYS.get(label)
    if not keys:
        raise KeyError(f"label desconocido: {label!r}")
    return AREAS[keys[0]]


def nearest_area(lat: float, lng: float, candidates: list[str]) -> Area:
    """Sub-área cuyo ancla queda más cerca de un punto. Se usa para repartir las
    73 filas de Highlands entre sus sub-áreas antes de re-resolverlas."""
    from geoutil import haversine_km

    return min(
        (AREAS[k] for k in candidates),
        key=lambda a: haversine_km(lat, lng, a.lat, a.lng),
    )
