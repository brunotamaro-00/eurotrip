#!/usr/bin/env python3
"""
Los 39 destinos que tienen filas en los 3 CSV regionales, con su
`actividades.md` de origen.

Antes esta lista tenía solo 19: los destinos que `build_propios.py` agregó en
un segundo pase. Las otras 585 filas venían de `build_maps.py`, que está
congelado y no dejó `src_file`/`src_line` en ninguna. Sin ese vínculo, el
precio, la URL y el "mejor momento" que ya estaban escritos en los .md no se
podían recuperar: por eso el CSV guardaba `notas = "Piedra Rosetta"` para el
British Museum. Completar la lista es lo que devuelve esa trazabilidad.

`label` tiene que coincidir EXACTO con la columna `ciudad` del CSV — es la
clave del join — y estar en `areas.LABEL_TO_KEYS` para que el resolver
geográfico sepa dónde buscar.

Quedan fuera a propósito los `actividades.md` de destinos que nunca entraron a
los CSV (Calabria, Costa Amalfitana): son opciones del sur de Italia que no se
eligieron, y sumarlas sería ampliar el mapa, no enriquecerlo.

Eslovenia va a `central` (viene después de Budapest en la ruta); Italia y España
van a `sur`, junto con Portugal.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Destino:
    area_key: str      # prefijo de los ids; para Highlands agrupa 19 sub-zonas
    label: str         # columna `ciudad` del CSV
    md: str            # ruta del actividades.md, relativa a la raíz del repo
    region: str        # occidental | central | sur


DESTINOS: list[Destino] = [
    # --- Reino Unido -> europa_occidental.csv ---
    Destino("londres", "Londres", "01_Reino_Unido/Londres/actividades.md", "occidental"),
    Destino("york", "York", "01_Reino_Unido/York/actividades.md", "occidental"),
    Destino("edimburgo", "Edimburgo", "01_Reino_Unido/Edimburgo/actividades.md", "occidental"),
    # Highlands no es una ciudad: son 19 sub-zonas en areas.HIGHLANDS_KEYS.
    Destino("highlands", "Highlands", "01_Reino_Unido/Highlands/actividades.md", "occidental"),

    # --- Países Bajos -> europa_occidental.csv ---
    Destino("amsterdam", "Ámsterdam", "02_Paises_Bajos/Amsterdam/actividades.md", "occidental"),

    # --- Francia -> europa_occidental.csv ---
    Destino("paris", "París", "03_Francia/Paris/actividades.md", "occidental"),
    Destino("colmar", "Colmar", "03_Francia/Colmar/actividades.md", "occidental"),
    Destino("estrasburgo", "Estrasburgo", "03_Francia/Estrasburgo/actividades.md", "occidental"),

    # --- Portugal -> europa_del_sur.csv ---
    Destino("lisboa", "Lisboa", "04_Portugal/Lisboa/actividades.md", "sur"),
    Destino("porto", "Porto", "04_Portugal/Porto/actividades.md", "sur"),

    # --- Alemania / Suiza / Austria -> europa_central.csv ---
    Destino("friburgo", "Friburgo", "05_Alemania/Friburgo/actividades.md", "central"),
    Destino("grindelwald", "Grindelwald", "06_Suiza/Grindelwald/actividades.md", "central"),
    Destino("interlaken", "Interlaken", "06_Suiza/Interlaken/actividades.md", "central"),
    Destino("lauterbrunnen", "Lauterbrunnen", "06_Suiza/Lauterbrunnen/actividades.md", "central"),
    Destino("lucerna", "Lucerna", "06_Suiza/Lucerna/actividades.md", "central"),
    Destino("innsbruck", "Innsbruck", "07_Austria/Innsbruck/actividades.md", "central"),
    Destino("viena", "Viena", "07_Austria/Viena/actividades.md", "central"),

    # --- Chequia / Polonia / Hungría -> europa_central.csv ---
    Destino("praga", "Praga", "08_Chequia/Praga/actividades.md", "central"),
    Destino("cracovia", "Cracovia", "09_Polonia/Cracovia/actividades.md", "central"),
    Destino("budapest", "Budapest", "10_Hungria/Budapest/actividades.md", "central"),

    # --- Eslovenia -> europa_central.csv ---
    Destino("liubliana", "Liubliana", "11_Eslovenia/Liubliana/actividades.md", "central"),
    Destino("bled", "Lagos Alpinos", "11_Eslovenia/Lagos Alpinos/actividades.md", "central"),
    Destino("karst", "Karst y Cuevas", "11_Eslovenia/Karst y Cuevas/actividades.md", "central"),
    Destino("soca", "Valle del Soča", "11_Eslovenia/Valle del Soča y Triglav/actividades.md", "central"),
    Destino("piran", "Costa Eslovena", "11_Eslovenia/Costa Eslovena y Trieste/actividades.md", "central"),

    # --- Italia -> europa_del_sur.csv ---
    Destino("florencia", "Florencia", "12_Italia/Florencia/actividades.md", "sur"),
    Destino("roma", "Roma", "12_Italia/Roma/actividades.md", "sur"),
    Destino("napoles", "Nápoles", "12_Italia/Napoles/actividades.md", "sur"),
    Destino("bari", "Bari", "12_Italia/Sur de Italia/Puglia/Bari/actividades.md", "sur"),
    Destino("lecce", "Lecce", "12_Italia/Sur de Italia/Puglia/Lecce/actividades.md", "sur"),
    Destino("matera", "Matera", "12_Italia/Sur de Italia/Puglia/Matera/actividades.md", "sur"),
    Destino("ostuni", "Ostuni", "12_Italia/Sur de Italia/Puglia/Ostuni/actividades.md", "sur"),
    Destino("palermo", "Palermo", "12_Italia/Sur de Italia/Sicilia/Palermo/actividades.md", "sur"),
    Destino("catania", "Catania", "12_Italia/Sur de Italia/Sicilia/Catania/actividades.md", "sur"),
    Destino("siracusa", "Siracusa", "12_Italia/Sur de Italia/Sicilia/Siracusa/actividades.md", "sur"),
    Destino("agrigento", "Agrigento", "12_Italia/Sur de Italia/Sicilia/Agrigento/actividades.md", "sur"),
    Destino("noto", "Noto", "12_Italia/Sur de Italia/Sicilia/Noto/actividades.md", "sur"),
    Destino("ragusa", "Ragusa", "12_Italia/Sur de Italia/Sicilia/Ragusa/actividades.md", "sur"),

    # --- España -> europa_del_sur.csv ---
    Destino("barcelona", "Barcelona", "13_España/Barcelona/actividades.md", "sur"),
    Destino("madrid", "Madrid", "13_España/Madrid/actividades.md", "sur"),
]

CSV_POR_REGION = {
    "occidental": "europa_occidental.csv",
    "central": "europa_central.csv",
    "sur": "europa_del_sur.csv",
}
