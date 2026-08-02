#!/usr/bin/env python3
"""
DEPRECATED — no correr. Se conserva como registro de cómo se generaron los
primeros 585 lugares. Reemplazado por areas.py + geo.py + build_katia.py.

Extrae lugares de actividades.md (Londres→Budapest), geocodifica con
Nominatim (lat/lng verificadas contra bbox de ciudad) y genera CSVs
para Google My Maps.

Por qué se retiró — tres defectos que produjeron coordenadas mal ubicadas:

1. `CITIES` le da a Highlands `max_km=220` y `view_deg=3.5` (L48). Con ese radio
   la validación acepta cualquier punto de Escocia.
2. `nominatim_search()` elige el candidato MÁS CERCANO AL CENTROIDE de la ciudad
   (L597-616) e ignora la relevancia. Combinado con (1), eso hizo que
   `Loch Cluanie` matcheara un lochan homónimo cerca de Whitebridge —30 km al
   este del real— justamente porque quedaba a 2 km del centroide de Highlands.
   La regla de desempate seleccionaba el error.
3. `bounded="0"` (L581) deja el viewbox como simple hint, y el reintento sin
   `countrycodes` ni viewbox (L588-593) no filtra por distancia después.

Además, 25 lugares de Isle of Skye devolvieron `no_results` (el sufijo
", Isle of Skye, UK" rompe el match) y se rellenaron a mano en un segundo pase
que no dejó script: son las 92 filas con `geo_source: "manual_fix"` en
geocoded_ok.json, sin validar y con 2-4 decimales.

El reemplazo corrige los tres: max_km <= 25 con sub-áreas, scoring donde la
distancia pesa 0.15 en vez de ser el único criterio, y cascada
Wikidata -> Overpass -> Nominatim con bounded=1.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

ROOT = Path("/Users/brunotamaro/Desktop/Trip/Itinerary")
OUT = Path("/Users/brunotamaro/Desktop/Trip/Itinerary/recursos/google_maps")
CACHE = OUT / "_build" / "geocode_cache.json"
EXTRACTED = OUT / "_build" / "extracted.json"
FAILED = OUT / "_build" / "failed.json"
USER_AGENT = "TripItineraryMapper/1.0 (personal travel planning; contact: local)"

# ---------------------------------------------------------------------------
# City config: centroid + max radius (km) for validation + Nominatim country
# ---------------------------------------------------------------------------
@dataclass
class City:
    key: str
    label: str  # ciudad column
    md: str
    lat: float
    lng: float
    country: str  # ISO2 for Nominatim
    search_suffix: str
    region: str  # occidental | central | sur
    max_km: float = 25.0
    # optional wider viewbox degrees (half-side)
    view_deg: float = 0.35


CITIES: list[City] = [
    City("londres", "Londres", "01_Reino_Unido/Londres/actividades.md", 51.5074, -0.1278, "gb", "London, UK", "occidental", 35, 0.5),
    City("york", "York", "01_Reino_Unido/York/actividades.md", 53.9591, -1.0815, "gb", "York, UK", "occidental", 20, 0.25),
    City("edimburgo", "Edimburgo", "01_Reino_Unido/Edimburgo/actividades.md", 55.9533, -3.1883, "gb", "Edinburgh, UK", "occidental", 30, 0.4),
    City("highlands", "Highlands", "01_Reino_Unido/Highlands/actividades.md", 57.2, -4.5, "gb", "Scottish Highlands, UK", "occidental", 220, 3.5),
    City("amsterdam", "Ámsterdam", "02_Paises_Bajos/Amsterdam/actividades.md", 52.3676, 4.9041, "nl", "Amsterdam, Netherlands", "occidental", 30, 0.4),
    City("paris", "París", "03_Francia/Paris/actividades.md", 48.8566, 2.3522, "fr", "Paris, France", "occidental", 35, 0.45),
    City("colmar", "Colmar", "03_Francia/Colmar/actividades.md", 48.0794, 7.3586, "fr", "Colmar, France", "occidental", 55, 0.7),  # Route des Vins
    City("estrasburgo", "Estrasburgo", "03_Francia/Estrasburgo/actividades.md", 48.5734, 7.7521, "fr", "Strasbourg, France", "occidental", 25, 0.3),
    City("lisboa", "Lisboa", "04_Portugal/Lisboa/actividades.md", 38.7223, -9.1393, "pt", "Lisboa, Portugal", "sur", 40, 0.5),  # Sintra
    City("porto", "Porto", "04_Portugal/Porto/actividades.md", 41.1579, -8.6291, "pt", "Porto, Portugal", "sur", 30, 0.35),
    City("friburgo", "Friburgo", "05_Alemania/Friburgo/actividades.md", 47.9990, 7.8421, "de", "Freiburg im Breisgau, Germany", "central", 60, 0.8),  # Black Forest
    City("grindelwald", "Grindelwald", "06_Suiza/Grindelwald/actividades.md", 46.6242, 8.0414, "ch", "Grindelwald, Switzerland", "central", 25, 0.3),
    City("interlaken", "Interlaken", "06_Suiza/Interlaken/actividades.md", 46.6863, 7.8632, "ch", "Interlaken, Switzerland", "central", 35, 0.4),
    City("lauterbrunnen", "Lauterbrunnen", "06_Suiza/Lauterbrunnen/actividades.md", 46.5937, 7.9091, "ch", "Lauterbrunnen, Switzerland", "central", 25, 0.3),
    City("lucerna", "Lucerna", "06_Suiza/Lucerna/actividades.md", 47.0502, 8.3093, "ch", "Luzern, Switzerland", "central", 30, 0.35),
    City("innsbruck", "Innsbruck", "07_Austria/Innsbruck/actividades.md", 47.2692, 11.4041, "at", "Innsbruck, Austria", "central", 40, 0.5),
    City("viena", "Viena", "07_Austria/Viena/actividades.md", 48.2082, 16.3738, "at", "Vienna, Austria", "central", 30, 0.4),
    City("praga", "Praga", "08_Chequia/Praga/actividades.md", 50.0755, 14.4378, "cz", "Prague, Czechia", "central", 30, 0.4),
    City("cracovia", "Cracovia", "09_Polonia/Cracovia/actividades.md", 50.0647, 19.9450, "pl", "Kraków, Poland", "central", 70, 0.9),  # Auschwitz
    City("budapest", "Budapest", "10_Hungria/Budapest/actividades.md", 47.4979, 19.0402, "hu", "Budapest, Hungary", "central", 25, 0.35),
]

# Sections to skip entirely (case-insensitive substring on ## heading)
SKIP_SECTION_SUBSTR = [
    "nightlife",
    "gastronom",
    "anti-scam",
    "consenso",
    "links útiles",
    "links utiles",
    "precios oficiales",
    "city cards",
    "días de la semana",
    "dias de la semana",
    "tips",
    "entendiendo",
    "durante tus fechas",
    "vocabulario",
    "cómo pedir",
    "como pedir",
    "packing",
    "presupuesto",
    "eventos especiales",
    "festival",
    "hacks",
    "trampas",
    "ópera standing",  # standing room tips
    "standing room",
    "fauna",
    "wildlife",
    "vida silvestre",
    "cómo funciona",
    "comparativa",
]

# Name patterns that are not a fixed map point
SKIP_NAME_RE = re.compile(
    r"(?i)("
    r"free\s*tour|sandemans|civitatis|strawberry\s*tours|guruwalk|"
    r"ghost\s*tour|river\s*cruise|uber\s*boat|thames\s*clipper|"
    r"afternoon\s*tea|west\s*end\s*show|pub\s*tradicional|"
    r"cambio de guardia|"
    r"city\s*card|museum\s*pass|travel\s*card|ov-?chipkaart|"
    r"tranv[ií]as?\s+\d|tram\s+\d|metro\s|bus\s+\d|"
    r"alquiler de bici|bike\s*rental|rent\s*a\s*bike|alquilar bici|"
    r"carril bici|canales en bici|"
    r"parapente|bungee|canyoning|rafting|"
    r"the shambles en york|"
    r"scotland place$|"
    r"^standing room|"
    r"^iglesias$|"
    r"crucero|bateaux mouches|canal cruise|"
    r"highland games|highland gathering|"
    r"ciervos rojos|delfines|águilas|nutrias|focas|"
    r"white-tailed|otters|"
    r"festival|uitmarkt|woofeland|zeezout|silhouette|jazz à la|"
    r"pluk de nacht|pure markt|ij-hallen|"
    r"palcsinta|creper|"
    r"tren jacobite|"  # mobile experience
    r"scotch whisky experience \(edimburgo\)"  # wrong city when in Highlands file
    r")"
)

# Extra exact-name skips (normalized lower)
SKIP_NAMES_EXACT = {
    "iglesias",
    "wien modern",
    "ferry a noord (ndsm)",
    "ferry al noord",
    "canales en bici",
    "tiendas de queso jordaan",
    "ruta singel → herengracht → jordaan",
    "ruta keizersgracht → magere brug (puente delgado)",
    "innsbruck de noche desde el bergisel",
    "nordkette — seegrube hike",  # trail not a single POI; keep Top of Innsbruck
}

# Prefer keeping if name clearly is a place even in a skippy section
KEEP_DESPITE = re.compile(r"(?i).+")  # unused; nightlife already skipped by section

TYPE_FROM_SECTION = [
    (r"(?i)museo|museum|galer", "Museo"),
    (r"(?i)iglesia|catedral|abad|templo|sinagog|bas[ií]lica|mezquita|iglesias", "Iglesia"),
    (r"(?i)mirador|viewpoint|panoram", "Mirador"),
    (r"(?i)parque|jard[ií]n|park|verde|heath", "Parque"),
    (r"(?i)mercado|market|naschmarkt|feira", "Mercado"),
    (r"(?i)barrio|neighbour|neighborhood|quartier|wijk|district", "Barrio"),
    (r"(?i)puente|bridge|h[ií]d", "Puente"),
    (r"(?i)terma|bath|balneario|f[uü]rd[oő]|spa", "Termas"),
    (r"(?i)ruin\s*bar|romkocsma", "Ruin bar"),
    (r"(?i)caf[eé]|heuriger|pasteler", "Café"),
    (r"(?i)teatro|theatre|show|m[uú]sica|concert|opera|ópera", "Teatro"),
    (r"(?i)trek|sender|hike|caminata|ruta|trail", "Trekking"),
    (r"(?i)harry\s*potter|filming", "Harry Potter"),
    (r"(?i)cementeri|graveyard|cemetery", "Cementerio"),
    (r"(?i)plaza|square|platz|tér|rynek", "Plaza"),
    (r"(?i)castillo|palace|palacio|castle|fortaleza|château|schloss", "Monumento"),
    (r"(?i)day\s*trip|excursi|desv[ií]o|cerca|pueblo|isla|island", "Excursión"),
    (r"(?i)imprescindible|sitio|hist[oó]ric|monument|atracci", "Sitio histórico"),
]

# Manual query overrides (nombre exacto del MD → query Nominatim)
QUERY_OVERRIDES: dict[str, str] = {
    "Big Ben y Palacio de Westminster": "Big Ben, London, UK",
    "Tower of London": "Tower of London, London, UK",
    "Sky Garden": "Sky Garden, 20 Fenchurch Street, London",
    "Horizon 22 (22 Bishopsgate)": "Horizon 22, 22 Bishopsgate, London",
    "Book Market (South Bank)": "Southbank Book Market, London",
    "Harry Potter Studio Tour (Leavesden)": "Warner Bros Studio Tour London, Leavesden",
    "Shakespeare's Globe": "Shakespeare's Globe, London",
    "BBC Proms en Royal Albert Hall": "Royal Albert Hall, London",
    "Cutty Sark (Greenwich)": "Cutty Sark, Greenwich, London",
    "Greenwich Observatory y Meridiano 0": "Royal Observatory Greenwich, London",
    "Monument to the Great Fire": "The Monument, London Bridge, London",
    "Victoria & Albert Museum": "Victoria and Albert Museum, London",
    "Sir John Soane's Museum": "Sir John Soane's Museum, London",
    "Museum of London Docklands": "Museum of London Docklands, London",
    "The Courtauld Gallery": "The Courtauld Gallery, Somerset House, London",
    "Churchill War Rooms": "Churchill War Rooms, London",
    "Parlamento (Országház)": "Hungarian Parliament Building, Budapest",
    "Basílica de San Esteban (Szent István-bazilika)": "St. Stephen's Basilica, Budapest",
    "Gran Sinagoga (Dohány utcai zsinagóga)": "Dohány Street Synagogue, Budapest",
    "Mercado Central (Nagy Vásárcsarnok)": "Central Market Hall, Budapest",
    "Andrássy Út": "Andrássy Avenue, Budapest",
    "Plaza de los Héroes (Hősök tere)": "Heroes' Square, Budapest",
    "Zapatos en el Danubio (Cipők a Duna-parton)": "Shoes on the Danube Bank, Budapest",
    "Casa del Terror (Terror Háza)": "House of Terror, Budapest",
    "Bastión de los Pescadores (Halászbástya)": "Fisherman's Bastion, Budapest",
    "Iglesia de Matías (Mátyás-templom)": "Matthias Church, Budapest",
    "Castillo de Buda (Budavári Palota)": "Buda Castle, Budapest",
    "Colina Gellért (Gellért-hegy)": "Gellért Hill, Budapest",
    "Puente de las Cadenas (Széchenyi Lánchíd)": "Széchenyi Chain Bridge, Budapest",
    "Puente de la Libertad (Szabadság híd)": "Liberty Bridge, Budapest",
    "Margit-sziget (Isla Margarita)": "Margaret Island, Budapest",
    "Szimpla Kert": "Szimpla Kert, Budapest",
    "Instant-Fogas": "Instant-Fogas, Budapest",
    "Palacio Schönbrunn": "Schönbrunn Palace, Vienna",
    "Palacio Belvedere (Upper Belvedere)": "Upper Belvedere, Vienna",
    "Hofburg": "Hofburg Palace, Vienna",
    "Schönbrunn — jardines y Gloriette": "Gloriette, Schönbrunn, Vienna",
    "Catedral San Esteban (Stephansdom)": "St. Stephen's Cathedral, Vienna",
    "Graben & Kohlmarkt": "Graben, Vienna",
    "Hofburg exterior + Heldenplatz": "Heldenplatz, Vienna",
    "Café Central": "Café Central, Vienna",
    "Café Sperl": "Café Sperl, Vienna",
    "Café Hawelka": "Café Hawelka, Vienna",
    "Café Sacher": "Café Sacher, Vienna",
    "Demel": "Demel, Vienna",
    "Freiburger Münster": "Freiburger Münster, Freiburg im Breisgau",
    "Altstadt + Bächle": "Freiburg im Breisgau Altstadt",
    "Catedral Notre-Dame": "Cathédrale Notre-Dame de Strasbourg",
    "Mosteiro dos Jerónimos": "Mosteiro dos Jerónimos, Lisboa",
    "Torre de Belém": "Torre de Belém, Lisboa",
    "Castelo de São Jorge": "Castelo de São Jorge, Lisboa",
    # Paris
    "Torre Eiffel": "Tour Eiffel, Paris",
    "Arco del Triunfo": "Arc de Triomphe, Paris",
    "Sacré-Cœur": "Basilique du Sacré-Cœur, Paris",
    "Catacumbas de París": "Catacombes de Paris",
    "Palais Royal (jardines)": "Jardin du Palais Royal, Paris",
    "Musée de Cluny (Musée national du Moyen Âge)": "Musée de Cluny, Paris",
    "Jardines de Luxemburgo": "Jardin du Luxembourg, Paris",
    "Père Lachaise": "Cimetière du Père-Lachaise, Paris",
    "Le Marais (3ème/4ème)": "Le Marais, Paris",
    "Montmartre (18ème sur)": "Montmartre, Paris",
    "Latin Quarter / Saint-Germain (5ème/6ème)": "Quartier Latin, Paris",
    "Canal Saint-Martin (10ème)": "Canal Saint-Martin, Paris",
    "Oberkampf / Ménilmontant (11ème/20ème)": "Oberkampf, Paris",
    "Belleville (19ème/20ème)": "Belleville, Paris",
    "Île de la Cité + Île Saint-Louis": "Île Saint-Louis, Paris",
    "Pigalle / SoPi (South Pigalle, 9ème)": "South Pigalle, Paris",
    "Marché Bastille": "Marché Bastille, Paris",
    # Vienna
    "Riesenrad (noria gigante)": "Wiener Riesenrad, Vienna",
    "Wurstelprater": "Wurstelprater, Vienna",
    "Prater verde (Hauptallee)": "Hauptallee, Prater, Vienna",
    "Kunsthistorisches Museum (KHM)": "Kunsthistorisches Museum, Vienna",
    "Leopold Museum (MuseumsQuartier)": "Leopold Museum, Vienna",
    "MUMOK (MuseumsQuartier)": "MUMOK, Vienna",
    "Naturhistorisches Museum": "Naturhistorisches Museum, Vienna",
    "Josefstadt (8º)": "Josefstadt, Vienna",
    "Ottakring (16º)": "Ottakring, Vienna",
    "Augarten (2º)": "Augarten, Vienna",
    # Prague
    "Barrio Judío (Josefov)": "Josefov, Prague",
    "Malá Strana (Ciudad Pequeña)": "Malá Strana, Prague",
    "Letná (Letenské sady)": "Letenské sady, Prague",
    "Prague Beer Museum": "Prague Beer Museum, Prague",
    # Krakow
    "Barrio Judío (Kazimierz)": "Kazimierz, Kraków",
    "Sinagoga Vieja (Stara Synagoga)": "Old Synagogue, Kraków",
    "Sinagoga Remuh y Cementerio Remuh": "Remuh Synagogue, Kraków",
    "Plaza de los Héroes del Gueto (Plac Bohaterów Getta)": "Plac Bohaterów Getta, Kraków",
    "Barrio Universitario (Collegium Maius)": "Collegium Maius, Kraków",
    "Galería de Arte Polaco del s. XIX (Sukiennice, planta alta)": "Sukiennice, Kraków",
    "Bar Mleczny Centralny": "Bar Mleczny Centralny, Kraków",
    # Innsbruck
    "Altstadt (callejeo)": "Altstadt, Innsbruck",
    "Catedral de Santiago (Dom zu St. Jakob)": "Dom zu St. Jakob, Innsbruck",
    "Arco del Triunfo (Triumphpforte)": "Triumphpforte, Innsbruck",
    "Castillo Ambras (Schloss Ambras)": "Schloss Ambras, Innsbruck",
    "Tirol Panorama + Kaiserjäger Museum": "Tirol Panorama, Innsbruck",
    "Tiroler Volkskunstmuseum": "Tiroler Volkskunstmuseum, Innsbruck",
    # Budapest extras
    "Ruinas del Anfiteatro Romano (Aquincum)": "Aquincum, Budapest",
    "Óbuda": "Óbuda, Budapest",
}

# Hard-coded verified coordinates when Nominatim is unreliable
# (lat, lng, display_name used for notes)
COORD_OVERRIDES: dict[str, tuple[float, float, str]] = {
    # London
    "Big Ben y Palacio de Westminster": (51.5007, -0.1246, "Big Ben / Palace of Westminster"),
    "Piccadilly Circus": (51.5101, -0.1342, "Piccadilly Circus"),
    "Sky Garden": (51.5115, -0.0835, "Sky Garden, 20 Fenchurch St"),
    "Horizon 22 (22 Bishopsgate)": (51.5145, -0.0825, "Horizon 22"),
    "Book Market (South Bank)": (51.5070, -0.1150, "Southbank Book Market"),
    "Leadenhall Market": (51.5128, -0.0836, "Leadenhall Market"),
    "Maltby Street Market": (51.4975, -0.0755, "Maltby Street Market"),
    "Columbia Road Flower Market": (51.5295, -0.0695, "Columbia Road Flower Market"),
    "Broadway Market": (51.5370, -0.0615, "Broadway Market"),
    "Harry Potter Studio Tour (Leavesden)": (51.6905, -0.4178, "Warner Bros Studio Tour London"),
    "Platform 9¾ (King's Cross)": (51.5322, -0.1240, "Platform 9¾ King's Cross"),
    # Budapest
    "Zapatos en el Danubio (Cipők a Duna-parton)": (47.5033, 19.0448, "Shoes on the Danube Bank"),
    "Parlamento (Országház)": (47.5071, 19.0457, "Hungarian Parliament"),
    "Bastión de los Pescadores (Halászbástya)": (47.5021, 19.0348, "Fisherman's Bastion"),
    "Szimpla Kert": (47.4970, 19.0633, "Szimpla Kert"),
    "Instant-Fogas": (47.4975, 19.0645, "Instant-Fogas"),
    "Mazel Tov": (47.4985, 19.0638, "Mazel Tov Budapest"),
    "Ellátó Kert": (47.4988, 19.0620, "Ellátó Kert"),
    "Anker't": (47.4995, 19.0585, "Anker't"),
    "Gólya (Corvin köz)": (47.4865, 19.0720, "Gólya"),
    "Auróra": (47.4925, 19.0705, "Auróra Budapest"),
    "Széchenyi": (47.5181, 19.0825, "Széchenyi Thermal Bath"),
    "Rudas": (47.4890, 19.0475, "Rudas Baths"),
    "Lukács": (47.5180, 19.0370, "Lukács Baths"),
    "Dandár": (47.4795, 19.0685, "Dandár Baths"),
    "Király": (47.5070, 19.0385, "Király Baths"),
    "Memento Park (Szoborpark)": (47.4264, 18.9997, "Memento Park"),
    "Kertész utca y Dob utca": (47.4990, 19.0635, "Kertész utca / Dob utca"),
    "Kazinczy utca (no confundir con Kazimierz)": (47.4975, 19.0625, "Kazinczy utca"),
    "Corvin Mozi (Cine Corvin)": (47.4855, 19.0695, "Corvin Mozi"),
    # Vienna
    "Graben & Kohlmarkt": (48.2085, 16.3695, "Graben"),
    "Naschmarkt": (48.1985, 16.3630, "Naschmarkt"),
    "Ringstrasse": (48.2026, 16.3695, "Opernring / Ringstraße"),
    "Hofburg exterior + Heldenplatz": (48.2060, 16.3635, "Heldenplatz"),
    "Schönbrunn — jardines y Gloriette": (48.1770, 16.3075, "Gloriette Schönbrunn"),
    "MQ Libelle (MuseumsQuartier)": (48.2035, 16.3590, "MQ Libelle"),
    # Paris
    "Sainte-Chapelle": (48.8554, 2.3450, "Sainte-Chapelle"),
    "Catacumbas de París": (48.8338, 2.3324, "Catacombes de Paris"),
    "Torre Eiffel": (48.8584, 2.2945, "Tour Eiffel"),
    "Notre-Dame": (48.8530, 2.3499, "Cathédrale Notre-Dame de Paris"),
    "Arco del Triunfo": (48.8738, 2.2950, "Arc de Triomphe"),
    "Sacré-Cœur": (48.8867, 2.3431, "Basilique du Sacré-Cœur"),
    "Louvre": (48.8606, 2.3376, "Musée du Louvre"),
    "Musée d'Orsay": (48.8600, 2.3266, "Musée d'Orsay"),
    "Île aux Cygnes": (48.8500, 2.2800, "Île aux Cygnes"),
    "Promenade Plantée": (48.8465, 2.3750, "Coulée verte René-Dumont"),
    "Marchés aux Puces de Saint-Ouen": (48.9045, 2.3400, "Marché aux Puces de Saint-Ouen"),
    # Prague
    "Puente de Carlos (Karlův most)": (50.0865, 14.4114, "Karlův most"),
    "Castillo de Praga (Hradčany)": (50.0911, 14.4016, "Pražský hrad"),
    "Reloj Astronómico (Orloj)": (50.0870, 14.4208, "Pražský orloj"),
    "Plaza de la Ciudad Vieja (Staroměstské náměstí)": (50.0875, 14.4211, "Staroměstské náměstí"),
    "Muro de John Lennon": (50.0860, 14.4045, "John Lennon Wall"),
    "Colina Petřín": (50.0836, 14.3950, "Petřín"),
    "Riegrovy Sady beer garden (Vinohrady)": (50.0805, 14.4410, "Riegrovy sady"),
    "Letenský zámeček": (50.0965, 14.4205, "Letenský zámeček"),
    "U Fleků": (50.0785, 14.4180, "U Fleků"),
    "Lokál": (50.0905, 14.4250, "Lokál Dlouhááá"),
    "Zly Casy": (50.0705, 14.4400, "Zlý časy"),
    # Krakow
    "Plaza del Mercado (Rynek Główny)": (50.0617, 19.9373, "Rynek Główny"),
    "Castillo Wawel": (50.0540, 19.9355, "Wawel Castle"),
    "Auschwitz-Birkenau": (50.0276, 19.2038, "Auschwitz-Birkenau"),
    "Mina de Sal de Wieliczka": (49.9833, 20.0606, "Wieliczka Salt Mine"),
    "Fábrica de Schindler (Muzeum Krakowa)": (50.0474, 19.9617, "Oskar Schindler's Enamel Factory"),
    "Fábrica de Schindler": (50.0474, 19.9617, "Oskar Schindler's Enamel Factory"),
    "Kościół Mariacki (Basílica de Santa María)": (50.0616, 19.9393, "St. Mary's Basilica Kraków"),
    "Floriańska Gate y Barbican": (50.0655, 19.9415, "Barbakan Kraków"),
    "Apoteka Pod Orlem (Farmacia del Águila)": (50.0455, 19.9545, "Apteka pod Orłem"),
    "Arka Pana (Iglesia del Arca)": (50.0175, 20.0155, "Arka Pana Nowa Huta"),
    "Zakrzówek": (50.0395, 19.9155, "Zakrzówek"),
    # Innsbruck
    "Goldenes Dachl (Tejadillo de Oro)": (47.2686, 11.3933, "Goldenes Dachl"),
    "Nordkette — Top of Innsbruck": (47.3120, 11.3800, "Hafelekar / Nordkette"),
    "Bergisel Ski Jump": (47.2489, 11.3994, "Bergisel"),
    "Swarovski Kristallwelten (Wattens)": (47.2930, 11.5900, "Swarovski Kristallwelten"),
    "Patscherkofel + Zirbenweg": (47.2090, 11.4600, "Patscherkofel"),
    "Río Inn + Paseo Innkai": (47.2685, 11.3900, "Innkai Innsbruck"),
    # Amsterdam
    "Magere Brug": (52.3637, 4.9024, "Magere Brug"),
    "Ruta Keizersgracht → Magere Brug (Puente Delgado)": (52.3637, 4.9024, "Magere Brug"),
    "A'DAM Lookout": (52.3997, 4.8950, "A'DAM Lookout"),
    "Molino De Gooyer + Brouwerij 't IJ": (52.3666, 4.9264, "De Gooyer / Brouwerij 't IJ"),
    "Café 't Smalle": (52.3775, 4.8855, "Café 't Smalle"),
    "Proeflokaal Wynand Fockink": (52.3725, 4.8955, "Wynand Fockink"),
    "Grey Area": (52.3755, 4.8895, "Grey Area Coffeeshop"),
    "Dampkring (Handboogstraat)": (52.3685, 4.8915, "Dampkring"),
    # Highlands / Skye
    "Quiraing": (57.6436, -6.2705, "Quiraing, Isle of Skye"),
    "Old Man of Storr": (57.5072, -6.1742, "Old Man of Storr"),
    "Fairy Pools (Glen Brittle)": (57.2495, -6.2570, "Fairy Pools, Skye"),
    "Fairy Pools": (57.2495, -6.2570, "Fairy Pools, Skye"),
    "Neist Point Lighthouse": (57.4135, -6.7880, "Neist Point Lighthouse"),
    "Neist Point": (57.4135, -6.7880, "Neist Point Lighthouse"),
    "Fairy Glen (near Uig)": (57.5610, -6.3110, "Fairy Glen, Uig"),
    "Fairy Glen": (57.5610, -6.3110, "Fairy Glen, Uig"),
    "Glenfinnan Viaduct": (56.8763, -5.4320, "Glenfinnan Viaduct"),
    "Eilean Donan Castle (Dornie)": (57.2740, -5.5156, "Eilean Donan Castle"),
    "Buachaille Etive Mòr": (56.6500, -4.9000, "Buachaille Etive Mòr"),
    "Lost Valley (Coire Gabhail)": (56.6620, -4.9870, "Coire Gabhail"),
    "Brothers' Point (Rubha nam Brathairean)": (57.5500, -6.1500, "Brothers Point Skye"),
    "The Kelpies, Falkirk": (56.0190, -3.7550, "The Kelpies"),
    "Falkirk Wheel": (56.0005, -3.8415, "Falkirk Wheel"),
    "Bealach na Bà / Applecross": (57.4160, -5.7000, "Bealach na Bà"),
    "Devil's Staircase": (56.6780, -4.9050, "Devil's Staircase Glencoe"),
    "Signal Rock": (56.6700, -5.1000, "Signal Rock Glencoe"),
    "Clava Cairns (~8km este, camino a Culloden)": (57.4735, -4.0740, "Clava Cairns"),
    "Chanonry Point, Black Isle (~30km norte)": (57.5740, -4.0920, "Chanonry Point"),
    "Chanonry Point (delfines)": (57.5740, -4.0920, "Chanonry Point"),
}


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    from math import radians, sin, cos, asin, sqrt
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def priority_from_mark(mark: str) -> str:
    if mark == "x":
        return "Quiero ir"
    if mark == "?":
        return "Quizás"
    return "Solo mapeado"


def infer_tipo(section: str, nombre: str) -> str:
    blob = f"{section} {nombre}"
    for pat, tipo in TYPE_FROM_SECTION:
        if re.search(pat, blob):
            return tipo
    return "Sitio"


def extract_precio(rest: str) -> str:
    # Common price snippets
    pats = [
        r"\*\*£[\d.,]+[^*]{0,40}\*\*",
        r"\*\*€[\d.,]+[^*]{0,40}\*\*",
        r"\*\*CHF\s*[\d.,]+[^*]{0,40}\*\*",
        r"\*\*~?[\d.,]+\s*HUF[^*]{0,30}\*\*",
        r"\*\*GRATIS[^*]{0,20}\*\*",
        r"\(GRATIS[^)]*\)",
        r"\(gratis[^)]*\)",
        r"£[\d.,]+(?:\s*adulto)?",
        r"€[\d.,]+(?:\s*adulto)?",
        r"CHF\s*[\d.,]+",
        r"~?[\d.,]+\s*HUF",
        r"Gratis",
        r"GRATIS",
    ]
    for p in pats:
        m = re.search(p, rest)
        if m:
            return re.sub(r"[*_]", "", m.group(0)).strip(" ()")[:60]
    return ""


def extract_notas(rest: str) -> str:
    # First clause before URL / em-dash cleanup
    text = re.sub(r"`https?://[^`]+`", "", rest)
    text = re.sub(r"https?://\S+", "", text)
    text = text.strip(" -—:\n")
    # Take up to first long break
    parts = re.split(r"\s+[—–]\s+", text, maxsplit=1)
    core = parts[0] if parts else text
    # Remove leading price-ish paren blocks at end later
    core = re.sub(r"\s+", " ", core).strip()
    if len(core) > 140:
        core = core[:137] + "..."
    return core


def should_skip_section(heading: str) -> bool:
    h = heading.lower()
    return any(s in h for s in SKIP_SECTION_SUBSTR)


def clean_nombre(raw: str) -> str:
    n = raw.strip()
    n = re.sub(r"\s*⭐\s*", " ", n).strip()
    return n


def parse_city(city: City) -> list[dict]:
    path = ROOT / city.md
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"\n(?=## )", text)
    places = []
    seen = set()

    for sec in sections:
        lines = sec.split("\n")
        heading = lines[0].strip()
        if should_skip_section(heading):
            continue
        body = "\n".join(lines[1:])
        for m in re.finditer(r"^- \[([ x?])\] \*\*(.+?)\*\*\s*(.*)$", body, re.M):
            mark, nombre, rest = m.group(1), clean_nombre(m.group(2)), m.group(3)
            if SKIP_NAME_RE.search(nombre):
                continue
            if nombre.lower().strip() in SKIP_NAMES_EXACT:
                continue
            # Skip pure food dishes / vague experiences without place
            if re.search(r"(?i)^(probar|comer|beber|degustar|plato|menú)\b", nombre):
                continue
            # Skip "event on date" style names with month day patterns as primary
            if re.search(r"(?i)\b(ago|sept|oct|nov|dic|ene|feb|mar|abr|may|jun|jul)\b.*\d{4}", nombre):
                continue
            if re.search(r"(?i)^\d{1,2}\s+(agosto|septiembre|octubre)", nombre):
                continue
            key = nombre.lower()
            if key in seen:
                continue
            seen.add(key)

            query = QUERY_OVERRIDES.get(nombre, f"{nombre}, {city.search_suffix}")
            # Strip parenthetical Spanish aliases for cleaner search when no override
            if nombre not in QUERY_OVERRIDES:
                # Prefer official name in parentheses if looks foreign
                paren = re.search(r"\(([^)]+)\)\s*$", nombre)
                if paren and re.search(r"[áéíóúäöüőűčřžšąćęłńśźż]", paren.group(1), re.I):
                    # keep as-is; override list handles key ones
                    pass

            places.append(
                {
                    "ciudad": city.label,
                    "ciudad_key": city.key,
                    "nombre": nombre,
                    "prioridad": priority_from_mark(mark),
                    "lugar_busqueda": query,
                    "tipo": infer_tipo(heading, nombre),
                    "precio": extract_precio(rest),
                    "notas": extract_notas(rest),
                    "section": heading[:80],
                    "region": city.region,
                }
            )

        # Also catch non-checkbox bold places in certain curated sections
        # (e.g. Heuriger zones, named baths in tables) — skip for now to avoid noise

    # Budapest termas from table names with checkboxes elsewhere — add common baths if mentioned with coords intent
    if city.key == "budapest":
        baths = [
            ("Széchenyi", "Quiero ir", "Széchenyi Thermal Bath, Budapest", "Termas", "~13,200 HUF", "Neo-barroco; piscinas exteriores icónicas"),
            ("Rudas", "Quiero ir", "Rudas Baths, Budapest", "Termas", "~11,000 HUF", "Otomano s.XVI; rooftop al Danubio"),
            ("Lukács", "Quizás", "Lukács Baths, Budapest", "Termas", "~7,000 HUF", "Más local, menos turístico"),
            ("Dandár", "Solo mapeado", "Dandár Baths, Budapest", "Termas", "~5-7,000 HUF", "Pequeño y local"),
            ("Király", "Solo mapeado", "Király Baths, Budapest", "Termas", "~8,000 HUF", "Otomano pequeño"),
        ]
        for nombre, pri, q, tipo, precio, notas in baths:
            if nombre.lower() not in seen:
                seen.add(nombre.lower())
                places.append(
                    {
                        "ciudad": city.label,
                        "ciudad_key": city.key,
                        "nombre": nombre,
                        "prioridad": pri,
                        "lugar_busqueda": q,
                        "tipo": tipo,
                        "precio": precio,
                        "notas": notas,
                        "section": "## Termas",
                        "region": city.region,
                    }
                )

    return places


def load_cache() -> dict:
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {}


def save_cache(cache: dict) -> None:
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1))


def nominatim_search(query: str, city: City) -> Optional[dict]:
    params = {
        "q": query,
        "format": "json",
        "limit": "5",
        "addressdetails": "1",
        "countrycodes": city.country,
    }
    # viewbox: left,top,right,bottom
    half = city.view_deg
    left = city.lng - half
    right = city.lng + half
    top = city.lat + half
    bottom = city.lat - half
    params["viewbox"] = f"{left},{top},{right},{bottom}"
    params["bounded"] = "0"  # prefer but don't force — day trips need slack

    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    if not data:
        # retry without countrycodes / viewbox for remote POIs
        params2 = {"q": query, "format": "json", "limit": "5", "addressdetails": "1"}
        url2 = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params2)
        req2 = urllib.request.Request(url2, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req2, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    if not data:
        return None

    # Pick best within max_km; else closest
    scored = []
    for item in data:
        lat, lng = float(item["lat"]), float(item["lon"])
        dist = haversine_km(city.lat, city.lng, lat, lng)
        scored.append((dist, item))
    scored.sort(key=lambda x: x[0])
    best_dist, best = scored[0]
    if best_dist > city.max_km:
        # try any candidate within max_km
        within = [s for s in scored if s[0] <= city.max_km]
        if within:
            best_dist, best = within[0]
        else:
            return {
                "_reject": True,
                "reason": f"too_far_{best_dist:.1f}km",
                "candidate": best,
                "dist_km": best_dist,
            }
    return {
        "lat": float(best["lat"]),
        "lng": float(best["lon"]),
        "display_name": best.get("display_name", ""),
        "osm_type": best.get("type", ""),
        "osm_class": best.get("class", ""),
        "dist_km": best_dist,
        "importance": float(best.get("importance") or 0),
    }


def geocode_place(place: dict, city: City, cache: dict) -> dict:
    nombre = place["nombre"]
    cache_key = f"{city.key}::{nombre}"

    if nombre in COORD_OVERRIDES:
        lat, lng, label = COORD_OVERRIDES[nombre]
        result = {
            "lat": lat,
            "lng": lng,
            "display_name": label,
            "source": "manual_override",
            "dist_km": haversine_km(city.lat, city.lng, lat, lng),
            "ok": True,
        }
        cache[cache_key] = result
        return result

    if cache_key in cache and cache[cache_key].get("ok"):
        return cache[cache_key]

    query = place["lugar_busqueda"]
    time.sleep(1.05)  # Nominatim rate limit
    try:
        hit = nominatim_search(query, city)
    except Exception as e:
        result = {"ok": False, "error": str(e), "query": query}
        cache[cache_key] = result
        return result

    if hit is None:
        result = {"ok": False, "error": "no_results", "query": query}
        cache[cache_key] = result
        return result

    if hit.get("_reject"):
        result = {
            "ok": False,
            "error": hit["reason"],
            "query": query,
            "candidate_display": hit["candidate"].get("display_name"),
            "candidate_lat": float(hit["candidate"]["lat"]),
            "candidate_lng": float(hit["candidate"]["lon"]),
            "dist_km": hit["dist_km"],
        }
        cache[cache_key] = result
        return result

    result = {**hit, "ok": True, "source": "nominatim", "query": query}
    cache[cache_key] = result
    return result


def name_plausible(nombre: str, display_name: str) -> bool:
    """Soft check: at least one significant token of the place appears in display_name."""
    # Extract tokens from nombre (latin letters)
    base = re.sub(r"\([^)]*\)", " ", nombre)
    tokens = [t.lower() for t in re.findall(r"[A-Za-zÀ-ÿŐőŰűČčŘřŽžŠšĄąĆćĘęŁłŃńŚśŹźŻż]{4,}", base)]
    # Drop generic words
    stop = {
        "palace", "palacio", "museum", "museo", "church", "iglesia", "cathedral",
        "catedral", "bridge", "puente", "park", "parque", "market", "mercado",
        "street", "plaza", "square", "castle", "castillo", "tower", "torre",
        "garden", "jardines", "hill", "colina", "island", "isla", "temple",
        "gallery", "galeria", "galería", "abbey", "abadia", "abadía", "bath",
        "termas", "road", "avenue", "calle", "free", "tour", "studio", "harry",
        "potter", "filming", "locations", "upper", "lower", "exterior", "jardines",
    }
    tokens = [t for t in tokens if t not in stop]
    if not tokens:
        return True  # nothing to check
    disp = display_name.lower()
    return any(t in disp for t in tokens[:4])


def write_csvs(rows: list[dict]) -> dict:
    regions = {
        "occidental": OUT / "europa_occidental.csv",
        "central": OUT / "europa_central.csv",
        "sur": OUT / "europa_del_sur.csv",
    }
    fields = ["ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo", "precio", "notas"]
    counts = {}
    for region, path in regions.items():
        subset = [r for r in rows if r["region"] == region]
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, quoting=csv.QUOTE_MINIMAL)
            w.writeheader()
            for r in subset:
                w.writerow({k: r[k] for k in fields})
        counts[region] = len(subset)
    return counts


LABEL_TO_CITY = {c.label: c for c in CITIES}
# Aliases for CSV ciudad values
LABEL_TO_CITY["Amsterdam"] = LABEL_TO_CITY["Ámsterdam"]

# Cities we re-extract from markdown (not in previous CSVs / need refresh)
NEW_CITY_KEYS = {"paris", "innsbruck", "viena", "praga", "cracovia", "budapest"}

# Previous CSV files (curated place lists) — prefer backups so remaps don't eat themselves
PREV_CSVS = [
    (OUT / "_build" / "prev_europa_occidental.csv", "occidental"),
    (OUT / "_build" / "prev_europa_central.csv", "central"),
    (OUT / "_build" / "prev_europa_del_sur.csv", "sur"),
]


def load_previous_csv_places() -> list[dict]:
    """Reuse curated rows from existing CSVs for cities already mapped."""
    places = []
    seen = set()
    for path, region_fallback in PREV_CSVS:
        if not path.exists():
            continue
        # Read without lat/lng if old format
        with path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                label = row["ciudad"]
                city = LABEL_TO_CITY.get(label)
                if not city:
                    print(f"WARN unknown city in CSV: {label}")
                    continue
                if city.key in NEW_CITY_KEYS:
                    continue  # will come from fresh extract
                key = (city.key, row["nombre"].lower())
                if key in seen:
                    continue
                seen.add(key)
                places.append(
                    {
                        "ciudad": city.label,
                        "ciudad_key": city.key,
                        "nombre": row["nombre"],
                        "prioridad": row.get("prioridad", "Solo mapeado"),
                        "lugar_busqueda": row.get("lugar_busqueda") or f"{row['nombre']}, {city.search_suffix}",
                        "tipo": row.get("tipo", "Sitio"),
                        "precio": row.get("precio", ""),
                        "notas": row.get("notas", ""),
                        "section": "",
                        "region": city.region,
                    }
                )
    return places


def collect_places(only_city: str = "") -> list[dict]:
    city_map = {c.key: c for c in CITIES}
    all_places: list[dict] = []

    if only_city:
        c = city_map[only_city]
        places = parse_city(c)
        print(f"extract {c.label}: {len(places)}")
        return places

    # 1) curated previous CSVs
    prev = load_previous_csv_places()
    print(f"from previous CSVs: {len(prev)}")
    all_places.extend(prev)

    # 2) fresh extract for new cities
    for c in CITIES:
        if c.key not in NEW_CITY_KEYS:
            continue
        places = parse_city(c)
        print(f"extract {c.label}: {len(places)}")
        all_places.extend(places)

    return all_places


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--geocode", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--city", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--from-md-all", action="store_true", help="Ignore previous CSV; parse all MD")
    args = parser.parse_args()

    city_map = {c.key: c for c in CITIES}

    if args.from_md_all:
        all_places = []
        cities = CITIES if not args.city else [city_map[args.city]]
        for c in cities:
            places = parse_city(c)
            print(f"extract {c.label}: {len(places)}")
            all_places.extend(places)
    else:
        all_places = collect_places(args.city)

    EXTRACTED.write_text(json.dumps(all_places, ensure_ascii=False, indent=1))
    print(f"total extracted: {len(all_places)} → {EXTRACTED}")

    if args.extract_only:
        return

    if not args.geocode and not args.write:
        args.geocode = True
        args.write = True

    cache = load_cache()
    failed = []
    suspicious = []
    ok_rows = []

    to_process = all_places
    if args.limit:
        to_process = all_places[: args.limit]

    for i, place in enumerate(to_process, 1):
        city = city_map[place["ciudad_key"]]
        print(f"[{i}/{len(to_process)}] {place['ciudad']}: {place['nombre'][:60]}...", flush=True)
        geo = geocode_place(place, city, cache)
        if i % 5 == 0:
            save_cache(cache)

        if not geo.get("ok"):
            failed.append({**place, "geo": geo})
            print(f"  FAIL: {geo.get('error')} dist={geo.get('dist_km')}")
            continue

        if geo.get("source") != "manual_override" and not name_plausible(
            place["nombre"], geo.get("display_name", "")
        ):
            suspicious.append({**place, "geo": geo, "flag": "name_mismatch"})
            print(f"  SUSPICIOUS name vs {geo.get('display_name', '')[:80]}")
            # Do NOT include suspicious matches — force manual review
            failed.append({**place, "geo": geo, "error": "name_mismatch"})
            continue

        ok_rows.append(
            {
                **place,
                "lat": round(geo["lat"], 6),
                "lng": round(geo["lng"], 6),
                "geo_display": geo.get("display_name", ""),
                "geo_source": geo.get("source"),
                "dist_km": round(geo.get("dist_km") or 0, 2),
            }
        )

    save_cache(cache)
    FAILED.write_text(
        json.dumps({"failed": failed, "suspicious": suspicious}, ensure_ascii=False, indent=1)
    )
    print(f"OK={len(ok_rows)} FAIL={len(failed)} SUSPICIOUS={len(suspicious)}")

    if args.write:
        counts = write_csvs(ok_rows)
        print("wrote CSVs:", counts)
        # Also dump full geocoded JSON for QA
        (OUT / "_build" / "geocoded_ok.json").write_text(
            json.dumps(ok_rows, ensure_ascii=False, indent=1)
        )


if __name__ == "__main__":
    main()
