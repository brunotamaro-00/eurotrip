#!/usr/bin/env python3
"""
Aplica precios investigados en web a places.json.

Fuente: sitios oficiales / municipalidades, verificados 2026-08.
Solo rellena campos vacíos (no pisa un precio que ya vino del .md).

Uso:
    python3 apply_web_precios.py
    python3 apply_web_precios.py --dry-run
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# (ciudad, nombre) -> {precio, reserva?, url?, url_ticketing?, mejor_momento?, note}
# Precio en el mismo formato que campos.py. verificado_el queda en origen.
WEB: dict[tuple[str, str], dict] = {
    # --- París ---
    ("París", "Grande Galerie de l'Évolution"): {
        "precio": "€13", "reserva": "Recomendada",
        "url": "https://www.mnhn.fr/fr/visite/grande-galerie-de-l-evolution",
        "url_ticketing": True,
        "note": "mnhn.fr tarif plein permanente 2026",
    },
    ("París", "Musée des Arts et Métiers"): {
        "precio": "€12", "reserva": "No necesaria",
        "url": "https://www.arts-et-metiers.net/musee/tarifs-et-horaires",
        "url_ticketing": True,
        "note": "arts-et-metiers.net tarif plein",
    },
    ("París", "Musée Rodin"): {
        "precio": "€14", "reserva": "Recomendada",
        "url": "https://www.musee-rodin.fr/preparer-sa-visite/informations-pratiques",
        "url_ticketing": True,
        "note": "musee-rodin.fr tarif plein 2026 (jardín incluido)",
    },
    ("París", "Palacio de Versalles"): {
        "precio": "€35", "reserva": "Obligatoria",
        "url": "https://en.chateauversailles.fr/plan-your-visit/tickets-and-prices",
        "url_ticketing": True,
        "mejor_momento": "Primera hora; Passport jardines+palacio",
        "note": "Passport ~€35 (katia_md ya tenía ~35; se confirma oficial)",
    },
    ("París", "Grand Palais"): {
        "precio": "Según exposición", "reserva": "Recomendada",
        "note": "espacio de muestras; el precio cambia por evento",
    },
    ("París", "Galerie Vivienne"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "pasaje cubierto, acceso libre",
    },
    ("París", "Moulin Rouge"): {
        "precio": "Desde €125", "reserva": "Obligatoria",
        "url": "https://www.moulinrouge.fr/en/booking/",
        "url_ticketing": True,
        "note": "espectáculo; pasar por fuera es gratis",
    },
    ("París", "Shakespeare and Company"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "librería; entrar a mirar es libre",
    },

    # --- Ámsterdam ---
    ("Ámsterdam", "Oude Kerk"): {
        "precio": "€14,50", "reserva": "Recomendada",
        "url": "https://www.oudekerk.nl/en/opening-hours-admission-prices/40784",
        "url_ticketing": True,
        "note": "oudekerk.nl adult 2026",
    },
    ("Ámsterdam", "Nieuwe Kerk"): {
        "precio": "Según exposición", "reserva": "Recomendada",
        "url": "https://www.nieuwekerk.nl/en/visit/",
        "url_ticketing": True,
        "note": "solo abre con exposiciones temporales",
    },
    ("Ámsterdam", "Palacio Real de Ámsterdam"): {
        "precio": "€13,50", "reserva": "Recomendada",
        "url": "https://www.paleisamsterdam.nl/en/visit/",
        "url_ticketing": True,
        "note": "paleisamsterdam.nl adult 2026, audioguía incluida",
    },

    # --- Roma ---
    ("Roma", "Museo Palatino"): {
        "precio": "Incluida", "reserva": "Obligatoria",
        "url": "https://ticketing.colosseo.it/",
        "url_ticketing": True,
        "note": "incluido en el ticket Coliseo/Foro/Palatino",
    },
    ("Roma", "Basílica de Majencio"): {
        "precio": "Incluida", "reserva": "Obligatoria",
        "note": "dentro del Foro Romano; mismo ticket",
    },
    ("Roma", "Santa Maria Maggiore"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "nave gratis; museos/terrazas aparte",
    },
    ("Roma", "Santa Maria della Vittoria"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "iglesia activa, donación voluntaria",
    },
    ("Roma", "Biblioteca Angelica"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "sala de lectura pública; consultar horarios",
    },
    ("Roma", "Auditorium Parco della Musica"): {
        "precio": "Según evento", "reserva": "Recomendada",
        "note": "pasear el exterior es gratis",
    },
    ("Roma", "Manufactus"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "tienda; entrar a mirar es libre",
    },

    # --- Nápoles ---
    ("Nápoles", "Catedral de Nápoles"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "nave gratis; baptisterio/cripta pueden cobrar",
    },
    ("Nápoles", "Santa Chiara"): {
        "precio": "€7", "reserva": "No necesaria",
        "note": "claustro de mayólicas €7; iglesia gratis (monasterodisantachiara.it)",
    },
    ("Nápoles", "Gesù Nuovo"): {
        "precio": "Gratis", "reserva": "No necesaria",
    },
    ("Nápoles", "San Lorenzo Maggiore"): {
        "precio": "€9", "reserva": "Recomendada",
        "note": "complejo + scavi ≈€9; iglesia suele ser gratis",
    },
    ("Nápoles", "Castel Nuovo"): {
        "precio": "€10", "reserva": "No necesaria",
        "note": "tarifa turista 2026 (Comune di Napoli); residentes €6",
    },
    ("Nápoles", "Teatro di San Carlo"): {
        "precio": "Según función", "reserva": "Obligatoria",
        "url": "https://www.teatrosancarlo.it/",
        "url_ticketing": True,
        "note": "visitas al edificio aparte según programación",
    },

    # --- Trieste ---
    ("Trieste", "Castillo de Miramare"): {
        "precio": "€17", "reserva": "Recomendada",
        "url": "https://www.coopculture.it/en/products/ticket-museo-storico-e-parco-del-castello-di-miramare/",
        "url_ticketing": True,
        "note": "coopculture 2026 museo+muestra; parque gratis",
    },
    ("Trieste", "Caffè degli Specchi"): {
        "precio": "Consumo", "reserva": "No necesaria",
        "note": "café histórico; se paga lo que se consume",
    },
    ("Trieste", "Antico Caffè San Marco"): {
        "precio": "Consumo", "reserva": "No necesaria",
    },

    # --- Liubliana ---
    ("Liubliana", "Museo Etnográfico Esloveno"): {
        "precio": "€6", "reserva": "No necesaria",
        "note": "etno-muzej.si adult aprox.",
    },
    ("Liubliana", "Catedral de San Nicolás"): {
        "precio": "Gratis", "reserva": "No necesaria",
    },
    ("Liubliana", "Iglesia Franciscana de la Anunciación"): {
        "precio": "Gratis", "reserva": "No necesaria",
    },
    ("Liubliana", "Biblioteca Nacional (NUK)"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "exterior/Plečnik gratis; sala de lectura con registro",
    },

    # --- Berna ---
    ("Berna", "Einsteinhaus"): {
        "precio": "CHF 7 (≈€7.5)", "reserva": "No necesaria",
        "url": "https://einstein-bern.ch/en/booking",
        "url_ticketing": True,
        "note": "einstein-bern.ch adult",
    },
    ("Berna", "Museo de Historia de Berna / Museo Einstein"): {
        "precio": "CHF 18 (≈€19)", "reserva": "Recomendada",
        "note": "Einstein Plus (histórico + Einstein Museum)",
    },
    ("Berna", "Zytglogge"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "mejor_momento": "Cada hora en punto, llegar unos minutos antes",
        "note": "el espectáculo mecánico se ve desde la calle; tour interior aparte",
    },

    # --- Viena ---
    ("Viena", "Cripta Imperial"): {
        "precio": "€15", "reserva": "No necesaria",
        "url": "https://www.kaisergruft.at/site/en/visit/prices",
        "url_ticketing": True,
        "note": "kaisergruft.at adult 2026",
    },
    ("Viena", "Biblioteca Nacional Austriaca (Prunksaal)"): {
        "precio": "€12", "reserva": "Recomendada",
        "url": "https://www.onb.ac.at/en/opening-hours/admission-fees",
        "url_ticketing": True,
        "note": "onb.ac.at State Hall adult",
    },
    ("Viena", "Wiener Konzerthaus"): {
        "precio": "Según concierto", "reserva": "Obligatoria",
        "note": "standing/entrada según programa",
    },

    # --- Budapest ---
    ("Budapest", "Castillo Vajdahunyad"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "exteriores/parque libres; museo agrícola aparte",
    },
    ("Budapest", "Ópera Estatal Húngara"): {
        "precio": "12760 HUF (≈€32)", "reserva": "Obligatoria",
        "url": "https://www.opera.hu/",
        "url_ticketing": True,
        "note": "visita guiada OperaTour desde ~12760 HUF",
    },
    ("Budapest", "Holocaust Memorial Center"): {
        "precio": "3600 HUF (≈€9)", "reserva": "No necesaria",
        "url": "https://hdke.hu/en/about-us/visitors/tickets/",
        "url_ticketing": True,
        "note": "hdke.hu adult permanente",
    },
    ("Budapest", "Museo Nacional de Hungría"): {
        "precio": "3500 HUF (≈€8.8)", "reserva": "No necesaria",
        "url": "https://mnm.hu/en/tickets",
        "url_ticketing": True,
        "note": "mnm.hu full price",
    },
    ("Budapest", "Funicular del Castillo"): {
        "precio": "4500 HUF (≈€11)", "reserva": "No necesaria",
        "url": "https://siklojegy.hu/en/tickets",
        "url_ticketing": True,
        "note": "BKV sikló ida 4500 / ida+vuelta 5500 HUF (feb 2026)",
    },

    # --- Edimburgo ---
    ("Edimburgo", "Royal Yacht Britannia"): {
        "precio": "£23 (≈€27)", "reserva": "Recomendada",
        "url": "https://www.royalyachtbritannia.co.uk/visit/tickets-and-tours/",
        "url_ticketing": True,
        "note": "online Apr-Oct 2026; puerta £25",
    },
    ("Edimburgo", "Oink"): {
        "precio": "Consumo", "reserva": "No necesaria",
        "note": "sándwiches; no hay entrada",
    },

    # --- Suiza / Alpes ---
    ("Lauterbrunnen", "Grütschalp"): {
        "precio": "Según tramo SBB", "reserva": "No necesaria",
        "note": "incluido en Swiss Travel / Jungfrau / Berner Oberland Pass",
    },
    ("Lauterbrunnen", "Obersteinberg"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "trekking; sin teleférico obligatorio",
    },
    ("Grindelwald", "Alpiglen"): {
        "precio": "Según tren WAB", "reserva": "No necesaria",
        "note": "estación WAB; se vuelve en tren",
    },
    ("Grindelwald", "Wilderswil"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "pueblo; el cremallera a Schynige Platte se paga aparte",
    },
    ("Kandersteg", "Kandersteg"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "pueblo",
    },
    ("Friburgo", "Schlossbergbahn"): {
        "precio": "€3,50", "reserva": "No necesaria",
        "note": "visit.freiburg.de ida €3,50 / ida+vuelta €6",
    },
    ("Lagos Alpinos", "Teleférico de Vogel"): {
        "precio": "€33", "reserva": "Recomendada",
        "note": "ida+vuelta 2026; cerrado 21-sep a 30-nov 2026 (mantenimiento)",
        "mejor_momento": "Antes de las 9am; verificar si está abierto",
    },
    ("Valle del Soča", "Paso de Vršič"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "carretera alpina; peaje no aplica a turismo estándar",
    },

    # --- Otros ---
    ("Praga", "Basílica de San Jorge"): {
        "precio": "Incluida", "reserva": "Recomendada",
        "note": "incluida en el circuito del Castillo de Praga",
    },
    ("Cracovia", "Iglesia de San José"): {
        "precio": "Gratis", "reserva": "No necesaria",
    },
    ("Colmar", "Église des Dominicains"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "nave; Madonna de Schongauer puede tener tarifa de coro",
    },
    ("Colmar", "Église Saint-Matthieu"): {
        "precio": "Gratis", "reserva": "No necesaria",
    },
    ("Estrasburgo", "Biblioteca Nacional y Universitaria"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "fachada Neustadt; consultar si hay visita interior",
    },
    ("Estrasburgo", "Église Saint-Paul"): {
        "precio": "Gratis", "reserva": "No necesaria",
    },
    ("Innsbruck", "Altes Landhaus"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "fachada / exterior",
    },
    ("Innsbruck", "Spitalskirche"): {
        "precio": "Gratis", "reserva": "No necesaria",
    },
    ("Innsbruck", "Hall in Tirol"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "pueblo",
    },
    ("Highlands", "St Andrews"): {
        "precio": "Gratis", "reserva": "No necesaria",
        "note": "pueblo; atracciones puntuales se pagan aparte",
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = HERE / "places.json"
    places = json.loads(path.read_text(encoding="utf-8"))
    hoy = "2026-08-03"
    aplicados = 0
    for p in places:
        key = (p["ciudad"], p["nombre"])
        w = WEB.get(key)
        if not w:
            continue
        origen = p.setdefault("origen", {})
        tocados = []
        if not p.get("precio") and w.get("precio"):
            p["precio"] = w["precio"]
            origen["precio"] = "web"
            p["verificado_el"] = hoy
            tocados.append("precio")
        if not p.get("reserva") and w.get("reserva"):
            p["reserva"] = w["reserva"]
            origen["reserva"] = "web"
            tocados.append("reserva")
        if not p.get("url") and w.get("url"):
            p["url"] = w["url"]
            p["url_ticketing"] = bool(w.get("url_ticketing"))
            origen["url"] = "web"
            tocados.append("url")
        if not p.get("mejor_momento") and w.get("mejor_momento"):
            p["mejor_momento"] = w["mejor_momento"]
            origen["mejor_momento"] = "web"
            tocados.append("mejor_momento")
        if tocados:
            aplicados += 1
            print(f"  {p['ciudad']:14} {p['nombre'][:40]:42} {p['precio']}")

    katia = [x for x in places if x["csv"] == "europa_katia.csv"]
    print(f"\naplicados: {aplicados}")
    print(f"katia precio: {sum(1 for x in katia if x.get('precio'))}/{len(katia)}")
    sin = [x for x in katia if not x.get("precio")]
    print(f"katia sin precio: {len(sin)}")
    for x in sin:
        print(f"  FALTA {x['ciudad']} / {x['nombre']}")

    if not args.dry_run:
        path.write_text(json.dumps(places, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"escrito {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
