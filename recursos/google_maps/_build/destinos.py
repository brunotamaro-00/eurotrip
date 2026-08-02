#!/usr/bin/env python3
"""
Destinos que faltaban en los 3 CSV regionales y que sí están en las notas
propias (`actividades.md`), no en las de Katia.

Eslovenia va a `central` (viene después de Budapest en la ruta); Italia y España
van a `sur`, junto con Portugal.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Destino:
    area_key: str      # tiene que existir en areas.AREAS
    label: str         # columna `ciudad` del CSV
    md: str            # ruta del actividades.md, relativa a la raíz del repo
    region: str        # occidental | central | sur


DESTINOS: list[Destino] = [
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
