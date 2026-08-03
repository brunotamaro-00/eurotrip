#!/usr/bin/env python3
"""
Extracción de los 5 campos enriquecidos desde una línea de `actividades.md`.

El formato de las líneas es regular:

    - [x] **Nombre** - Descripción; **£31 adulto** — **mejor martes** `https://...`

pero lo que viene después del nombre es prosa libre, así que cada campo se saca
con patrones que salieron de minar los 1518 ítems reales del repo, no de
imaginar formatos. Los conteos que justifican cada decisión están en los
docstrings de cada extractor.

Se separa de `parse_actividades.py` porque los mismos extractores se aplican
después a las filas de Katia, que vienen de otro parser.
"""
from __future__ import annotations

import re
import unicodedata

# --- Monedas -----------------------------------------------------------------
# El viaje cruza 6 monedas. Los .md ya escriben "700 CZK (~€28)" en muchos
# casos; donde no lo hacen, se completa con esta tabla.
#
# Cotizaciones aproximadas, tomadas como referencia de planificación (2026-08).
# NO son para calcular gastos reales: sirven para que un HUF 14.000 se pueda
# comparar de un vistazo contra un £31. El CSV siempre muestra primero el
# número que se paga en la ventanilla.
FX_A_EUR: dict[str, float] = {
    "EUR": 1.0,
    "GBP": 1.17,
    "CHF": 1.07,
    "CZK": 0.040,
    "PLN": 0.235,
    "HUF": 0.0025,
    "USD": 0.92,
}

# Cómo se escribe cada moneda en la salida: prefijo (£31) o sufijo (700 CZK).
PREFIJO = {"EUR": "€", "GBP": "£", "USD": "$", "CHF": "CHF "}
SUFIJO = {"CZK": " CZK", "PLN": " PLN", "HUF": " HUF"}

# Alias tal como aparecen en los .md -> código ISO
SIMBOLO_A_ISO = {
    "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP",
    "$": "USD", "usd": "USD",
    "chf": "CHF", "fr.": "CHF", "sfr": "CHF",
    "czk": "CZK", "kč": "CZK", "kc": "CZK",
    "pln": "PLN", "zł": "PLN", "zl": "PLN",
    "huf": "HUF", "ft": "HUF",
}

_NUM = r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?"
_RANGO = rf"{_NUM}(?:\s*(?:[-–—]|a|/)\s*{_NUM})?"
_PRE = r"€|£|\$|CHF|EUR|GBP|USD"
_SUF = r"CZK|Kč|Kc|PLN|zł|zl|HUF|Ft|€|EUR|£|GBP"

# "€26" · "CHF 115–140" · "£15-20" · "~€5"
PRECIO_PREFIJO_RE = re.compile(rf"(?<![\w])(?:~|≈|desde\s+|approx\.?\s*)?({_PRE})\s?({_RANGO})", re.I)
# "700 CZK" · "143 PLN" · "14,000 HUF" · "15 €" · "6,50 €" · "~35 €"
PRECIO_SUFIJO_RE = re.compile(rf"(?<![\w])(?:~|≈|desde\s+)?({_RANGO})\s?({_SUF})(?![\w])")
# equivalente en euros que el .md ya escribió al lado: "(~€28)"
EQUIV_EUR_RE = re.compile(rf"\(\s*[~≈]?\s*€\s?({_RANGO})\s*\)")

# "entrada libre" NO es gratis: en museos suele significar visita libre (vs guiada)
# por un precio ("Entrada libre ~15 €" = Palais Garnier).
GRATIS_RE = re.compile(r"(?i)\b(gratis|gratuit[ao]s?|free entry|free admission)\b")

URL_RE = re.compile(r"https?://[^\s`>)]+")
# Un link sirve para el CSV solo si permite sacar entrada o reservar. Los
# dominios informativos (wikipedia, la homepage de turismo de la ciudad) no
# entran: el campo `url` es accionable, no una bibliografía.
URL_TICKETING_RE = re.compile(
    r"(?i)(ticket|entrada|bigliett|bilet|reserv|book|buy|shop|visit|besuch|"
    r"prices|precio|prezzi|tarif|admission|eintritt|jegy|vstupenk|kupuj)"
)
URL_NO_TICKETING_RE = re.compile(r"(?i)(wikipedia\.|wikimedia\.|tripadvisor\.|reddit\.|youtube\.|maps\.google)")

# --- Reserva -----------------------------------------------------------------
# Solo ~60 de los 1518 ítems mencionan reserva explícitamente, así que este
# extractor cubre poco por diseño: el resto sale de reglas por tipo y del pase
# de investigación web.
#
# `\b` en "book" es imprescindible: sin eso matchean "edbookfest",
# "leakeysbookshop", "Book of Mormon" y "preservados".
RESERVA_OBLIGATORIA_RE = re.compile(
    r"(?i)(reserva\s+(?:online\s+)?obligatori|obligatorio\s+reservar|"
    r"reservar\s+(?:slot\s+)?online\s+obligatori|pre-?booking\s+obligatori|"
    r"reservar\s+obligatoriamente|imprescindible\s+reservar|"
    r"reserva\s+de\s+franja\s+horaria|tour\s+obligatorio|"
    r"reservar\s+slot\s+online|solo\s+con\s+reserva)"
)
RESERVA_RECOMENDADA_RE = re.compile(
    r"(?i)(reserva\s+recomendad|reservar\s+con\s+(?:mucha\s+|semanas\s+de\s+)?anticipaci|"
    r"reservar\s+online\s+con\s+anticipaci|conviene\s+(?:reservar|sacar)|"
    r"tickets?\s+se\s+liberan|tickets?\s+(?:vuelan|se\s+agotan)|se\s+agotan\s+con|"
    r"reservar\s+(?:online|en\s+agosto|ya|el\s+slot|para)|comprar\s+(?:la\s+)?entrada\s+online|"
    r"capacidad\s+m[aá]xima|entrada\s+anticipada|con\s+antelaci[oó]n)"
)
RESERVA_NO_RE = re.compile(r"(?i)(sin\s+reserva|no\s+(?:hace\s+falta|es\s+de\s+reserva\s+obligatoria|requiere\s+reserva)|walk-?in)")

# --- Mejor momento -----------------------------------------------------------
# El repo tiene una convención explícita: "**📅 Mejor sábado**". Es la señal
# más confiable y va primero. Después vienen las frases sueltas en prosa.
MOMENTO_EMOJI_RE = re.compile(r"📅\s*\**\s*([^*;.()—]{2,60})")

# Una hora concreta: "9am", "18h", "11:30h", "1pm". El `\d` inicial es
# imprescindible: sin él, "después de la anexión de 1871" matcheaba como si
# "anexión" fuera una hora, porque a/p/m/h son letras válidas del sufijo.
_HORA = r"\d{1,2}(?::\d{2})?\s*(?:h|hs|am|pm)?"

MOMENTO_FRASES = [
    re.compile(rf"(?i)\b(mejor\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)[^;.()—]{{0,40}})"),
    re.compile(rf"(?i)\b(mejor\s+(?:entre\s+semana|al\s+atardecer|al\s+amanecer|temprano|de\s+ma[ñn]ana|a\s+primera\s+hora)[^;.()—]{{0,30}})"),
    re.compile(rf"(?i)\b(llegar\s+(?:antes\s+de\s+las?\s+{_HORA}|a\s+las?\s+{_HORA}|temprano|a\s+primera\s+hora)[^;.()—]{{0,35}})"),
    re.compile(rf"(?i)\b((?:ir|visitar)\s+(?:antes\s+de\s+las?\s+{_HORA}|temprano|a\s+primera\s+hora|al\s+atardecer)[^;.()—]{{0,35}})"),
    re.compile(r"(?i)\b(madrugar[^;.()—]{0,45})"),
    re.compile(rf"(?i)\b((?:mucho\s+mejor\s+)?(?:antes|despu[eé]s)\s+de\s+las?\s+{_HORA}[^;.()—]{{0,30}})"),
    re.compile(r"(?i)\b((?:recomendado\s+)?ir\s+al\s+atardecer|al\s+atardecer|al\s+amanecer|golden\s+hour)"),
    re.compile(r"(?i)\b(evitar\s+(?:el\s+|los\s+|las\s+)?(?:fin\s+de\s+semana|s[aá]bados?|domingos?|medio\s?d[ií]a)[^;.()—]{0,30})"),
    re.compile(r"(?i)\b(cierra\s+(?:los\s+)?(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bados?|domingos?)[^;.()—]{0,25})"),
]

TAG_RE = re.compile(r"^\s*\[[^\]]{0,30}\]\s*")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _a_float(num: str) -> float:
    """'14,000' -> 14000.0 · '3.50' -> 3.5 · '1.700' -> 1700.0

    Los .md mezclan separadores: "14,000 HUF" usa coma de miles y "€3.50" usa
    punto decimal. La regla que los distingue: si el último grupo tiene 3
    dígitos es separador de miles, si tiene 1-2 es decimal.
    """
    n = num.strip().replace(" ", "")
    m = re.search(r"[.,](\d+)$", n)
    if m and len(m.group(1)) <= 2:
        return float(re.sub(r"[.,](?=\d{3}\b)", "", n[: m.start()]).replace(",", "") + "." + m.group(1))
    return float(re.sub(r"[.,]", "", n))


def _primer_numero(rango: str) -> float:
    m = re.match(rf"\s*({_NUM})", rango)
    return _a_float(m.group(1)) if m else 0.0


def _fmt_monto(rango: str, iso: str) -> str:
    """Escribe el monto en su moneda, respetando el rango si lo hay."""
    r = re.sub(r"\s*[-–—]\s*", "-", rango.strip())
    r = re.sub(r"\s*/\s*", "/", r)
    if iso in PREFIJO:
        return f"{PREFIJO[iso]}{r}"
    return f"{r}{SUFIJO.get(iso, ' ' + iso)}"


def _equiv_eur(rango: str, iso: str) -> str:
    """'≈€34' para monedas que no son el euro. Se omite si el monto es ínfimo."""
    if iso == "EUR":
        return ""
    v = _primer_numero(rango) * FX_A_EUR.get(iso, 0)
    if v <= 0:
        return ""
    return f"≈€{v:.0f}" if v >= 10 else f"≈€{v:.1f}".rstrip("0").rstrip(".")


def _tokens_precio(texto: str) -> list[dict]:
    """Todos los montos del texto, en orden de aparición, con si venían en negrita."""
    out: list[dict] = []
    for m in PRECIO_PREFIJO_RE.finditer(texto):
        iso = SIMBOLO_A_ISO.get(m.group(1).lower(), m.group(1).upper())
        out.append({"ini": m.start(), "fin": m.end(), "iso": iso, "rango": m.group(2)})
    for m in PRECIO_SUFIJO_RE.finditer(texto):
        iso = SIMBOLO_A_ISO.get(m.group(2).lower(), m.group(2).upper())
        out.append({"ini": m.start(), "fin": m.end(), "iso": iso, "rango": m.group(1)})
    out.sort(key=lambda x: x["ini"])

    # Un "700 CZK (~€28)" produce 2 tokens; el segundo es el equivalente que el
    # .md ya calculó, no un precio distinto. Se absorbe.
    limpio: list[dict] = []
    for t in out:
        if limpio and t["iso"] == "EUR" and t["ini"] - limpio[-1]["fin"] <= 4:
            ctx = texto[limpio[-1]["fin"]: t["fin"] + 1]
            if EQUIV_EUR_RE.search(ctx) or ctx.strip().startswith("("):
                rango_eq = re.sub(r"\s*[-–—]\s*", "-", t["rango"])
                limpio[-1]["equiv_md"] = "≈€" + rango_eq
                continue
        limpio.append(t)

    for t in limpio:
        t["negrita"] = _en_negrita(texto, t["ini"])
    return limpio


def _en_negrita(texto: str, pos: int) -> bool:
    """¿El monto en `pos` cae dentro de un `**...**`?

    La convención del repo es marcar el precio principal en negrita
    (`**£31 adulto**`), así que es el mejor desempate cuando hay varios montos.
    """
    return texto.count("**", 0, pos) % 2 == 1


def extraer_precio(resto: str) -> dict:
    """Precio normalizado a 'moneda local (≈€X)'.

    Devuelve `ambiguo=True` cuando la línea tiene varios montos distintos o
    mezcla gratis con un monto ("GRATIS exterior; £8 la torre"). Esos casos NO
    se adivinan: quedan marcados para el pase de investigación web, que es el
    que puede decidir cuál es el precio de entrada general.
    """
    texto = URL_RE.sub("", resto)
    tokens = _tokens_precio(texto)
    hay_gratis = bool(GRATIS_RE.search(texto))

    if not tokens:
        if hay_gratis:
            return {"precio": "Gratis", "origen": "md", "ambiguo": False, "raw": ""}
        return {"precio": "", "origen": "", "ambiguo": False, "raw": ""}

    negritas = [t for t in tokens if t["negrita"]]
    elegido = negritas[0] if negritas else tokens[0]

    monto = _fmt_monto(elegido["rango"], elegido["iso"])
    equiv = elegido.get("equiv_md") or _equiv_eur(elegido["rango"], elegido["iso"])
    precio = f"{monto} ({equiv})" if equiv else monto

    distintos = {(t["iso"], re.sub(r"\s", "", t["rango"])) for t in tokens}
    ambiguo = len(distintos) > 1 or hay_gratis
    if hay_gratis and GRATIS_RE.search(texto).start() < elegido["ini"]:
        # "GRATIS el exterior; **£8** la torre" -> el precio general es gratis
        precio = "Gratis"

    return {"precio": precio, "origen": "md", "ambiguo": ambiguo,
            "raw": texto[max(0, elegido["ini"] - 40): elegido["fin"] + 25].strip()}


def extraer_url(resto: str) -> dict:
    """URL solo si sirve para reservar o sacar entrada.

    26% de los ítems traen link. No todos son de ticketing: muchos son la
    homepage del museo. Se marca `ticketing` y el pase web decide si la deja o
    la reemplaza por la de compra real.
    """
    urls = [u.rstrip("`.,;)") for u in URL_RE.findall(resto)]
    urls = [u for u in urls if not URL_NO_TICKETING_RE.search(u)]
    if not urls:
        return {"url": "", "ticketing": False}
    for u in urls:
        if URL_TICKETING_RE.search(u):
            return {"url": u, "ticketing": True}
    return {"url": urls[0], "ticketing": False}


def extraer_reserva(resto: str) -> dict:
    texto = URL_RE.sub("", resto)
    if RESERVA_OBLIGATORIA_RE.search(texto):
        return {"reserva": "Obligatoria", "origen": "md"}
    if RESERVA_NO_RE.search(texto):
        return {"reserva": "No necesaria", "origen": "md"}
    if RESERVA_RECOMENDADA_RE.search(texto):
        return {"reserva": "Recomendada", "origen": "md"}
    return {"reserva": "", "origen": ""}


def _limpiar_momento(s: str, max_chars: int = 60) -> str:
    s = s.replace("**", "").strip(" ;,·-–—`")
    s = re.sub(r"\s{2,}", " ", s)
    if len(s) > max_chars:
        corte = s.rfind(" ", 0, max_chars)
        s = s[: corte if corte > max_chars * 0.5 else max_chars].rstrip(" ,;")
    return s[:1].upper() + s[1:] if s else s


def extraer_momento(resto: str) -> dict:
    """Mejor momento para ir. La marca `📅` del repo tiene prioridad."""
    texto = URL_RE.sub("", resto)
    m = MOMENTO_EMOJI_RE.search(texto)
    if m:
        return {"mejor_momento": _limpiar_momento(m.group(1)), "origen": "md"}

    # Los patrones se solapan a propósito (van de más específico a más
    # genérico): "madrugar antes de las 9:30am" dispara también el patrón
    # suelto "antes de las 9:30am". La deduplicación va sobre el texto CRUDO,
    # antes de recortar a 60 chars — si se hace después, dos recortes distintos
    # de la misma frase ya no se contienen y salen los dos.
    partes: list[str] = []
    vistos: list[str] = []
    for pat in MOMENTO_FRASES:
        mm = pat.search(texto)
        if not mm:
            continue
        c = strip_accents(mm.group(1).replace("**", "").strip()).lower()
        if any(c in q or q in c for q in vistos):
            continue
        vistos.append(c)
        partes.append(_limpiar_momento(mm.group(1)))
        if len(partes) == 2:
            break
    if not partes:
        return {"mejor_momento": "", "origen": ""}
    return {"mejor_momento": "; ".join(partes), "origen": "md"}


def _quitar_redundancia(t: str, precio: str, momento: str) -> str:
    """Saca de la prosa lo que ya tiene columna propia.

    El .md escribe todo junto —"...bien logrado (£34 adulto) — mejor entre
    semana"— y sin esto la ficha del pin muestra el precio y el horario dos
    veces, una en su columna y otra dentro de la descripción.

    Solo se borra lo que se extrajo con éxito: si `precio` quedó vacío, el
    monto se queda en la prosa en vez de perderse.
    """
    if precio and precio != "Gratis":
        # el paréntesis o guion final que contiene el monto: "(£34 adulto)",
        # "(GRATIS; reserva recomendada)", "— **€26** adulto"
        t = re.sub(rf"\s*\((?:[^()]*?)(?:{_PRE}|{_SUF})\s?\d[^()]*?\)", "", t, flags=re.I)
        t = re.sub(rf"\s*\([^()]*?\d\s?(?:{_SUF})[^()]*?\)", "", t, flags=re.I)
    if precio == "Gratis":
        t = re.sub(r"\s*\(\s*(?i:gratis|gratuito|free)[^()]{0,40}\)", "", t)

    if momento:
        for frag in momento.split("; "):
            if len(frag) < 6:
                continue
            esc = re.escape(frag)
            # Si la frase vive dentro de un paréntesis, se va el paréntesis
            # entero. Borrar solo la frase dejaba restos como
            # "...en Notting Hill (de mañana)".
            t = re.sub(rf"\s*\([^()]*{esc}[^()]*\)", "", t, flags=re.I)
            t = re.sub(rf"\s*[—–-]?\s*📅?\s*{esc}[^;.]{{0,20}}", "", t, flags=re.I)

    return _tidy(t)


def _tidy(t: str) -> str:
    """Repara la puntuación que queda colgando al remover un fragmento."""
    t = re.sub(r"\(\s*📅?\s*\)", "", t)
    t = re.sub(r"\s*;\s*(?=[;,.])", "", t)          # ";;" y ";,"
    t = re.sub(r":\s*;", ";", t)                     # "plan B de foros:;"
    t = re.sub(r"\s*([;,])\s*", r"\1 ", t)
    t = re.sub(r"\s*[—–-]\s*(?=[;,.]|$)", "", t)     # guion suelto al final
    t = re.sub(r"[;,:]\s*$", "", t)                  # clausula vacía al final
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip(" ;·-–—,:")


def extraer_descripcion(resto: str, max_chars: int = 400,
                        precio: str = "", momento: str = "") -> str:
    """Descripción limpia, cortada en límite de oración y no a mitad de palabra.

    El parser viejo hacía `[:190]` a secas y dejaba cosas como
    "...en otoño la plaza está llen".

    `precio` y `momento` son los valores ya extraídos: se pasan para poder
    sacarlos de la prosa y no repetirlos en la ficha del pin.
    """
    t = TAG_RE.sub("", resto)
    t = URL_RE.sub("", t)
    t = MD_LINK_RE.sub(r"\1", t)
    t = t.replace("**", "").replace("`", "")
    t = re.sub(r"^[\s\-–—]*[⭐★☆]+[\s\-–—]*", "", t)
    t = re.sub(r"^\s*[-–—]\s*", "", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" ;·-–—,")
    t = _quitar_redundancia(t, precio, momento)

    if len(t) <= max_chars:
        return t
    # cortar en el último separador de oración antes del límite
    corte = max(t.rfind("; ", 0, max_chars), t.rfind(". ", 0, max_chars))
    if corte < max_chars * 0.6:
        corte = t.rfind(" ", 0, max_chars)
    return t[:corte].rstrip(" ;,.·-–—") + "…"
