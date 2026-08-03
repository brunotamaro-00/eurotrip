#!/usr/bin/env python3
"""
Validación estructural de los CSV (sin red).

El chequeo que importa de verdad —que `lugar_busqueda` resuelva al lugar correcto
en una búsqueda por texto— vive en verify_search.py, que sí usa red.

Uso:
    python3 validate_csvs.py                # valida los 4 CSV
    python3 validate_csvs.py europa_katia.csv
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from areas import AREAS, COUNTRIES_EN, LABEL_TO_KEYS
from geoutil import decimals, haversine_km, normalize

OUT = Path(__file__).resolve().parent.parent
CSVS = ["europa_occidental.csv", "europa_central.csv", "europa_del_sur.csv", "europa_katia.csv"]

FIELDS = [
    "ciudad", "nombre", "prioridad", "lat", "lng", "lugar_busqueda", "tipo",
    "precio", "descripcion", "url", "reserva", "mejor_momento",
]
PRIORIDADES = {"Quiero ir", "Quizás", "Solo mapeado"}
RESERVAS = {"", "Obligatoria", "Recomendada", "No necesaria"}
# Precio: Gratis · £31 · £31 (≈€36) · CHF 32 (≈€34) · HUF 4900 (≈€12) · €18-25
PRECIO_OK_RE = re.compile(
    r"^(?:"
    r"Gratis(?:\s*\([^)]{1,40}\))?"
    r"|Incluida"
    r"|(?:desde\s+)?"
    r"(?:"
    r"£\d[\d.,/\-–]*"
    r"|€\d[\d.,/\-–]*"
    r"|\$\d[\d.,/\-–]*"
    r"|CHF\s?\d[\d.,/\-–]*"
    r"|\d[\d.,]*\s?(?:CZK|PLN|HUF|Ft|Kč)"
    r")"
    r"(?:\s*\(≈€[\d.,]+\))?"
    r"|verificar precio"
    r")$",
    re.I,
)
URL_OK_RE = re.compile(r"^https?://\S+$")

# Europa continental + islas británicas
BBOX = (35.0, -11.0, 60.0, 25.0)  # lat_min, lng_min, lat_max, lng_max

# 3 decimales ≈ 110 m: es la firma de una coordenada tipeada a mano (las 92
# `manual_fix`). 4 decimales ≈ 11 m ya sirve para un pin, así que solo avisa.
BAD_DECIMALS = 3
WARN_DECIMALS = 4

# Caracteres que rompen una búsqueda por texto en Google Maps.
FORBIDDEN_RE = re.compile(r"[&+/()\[\]]|~~")

# Nombres que existen en muchas ciudades: exigen localidad + país (2 comas).
GENERIC_NAMES = {
    "altstadt", "old town", "new town", "casco antiguo", "casco historico",
    "centro storico", "centro historico", "kunsthalle", "mercado central",
    "mercato centrale", "hauptbahnhof", "rathaus", "rathausplatz", "duomo",
    "marktplatz", "grand place", "stare miasto", "staro mesto",
}


class Issue:
    def __init__(self, path: str, row: int, campo: str, msg: str, sev: str = "error"):
        self.path, self.row, self.campo, self.msg, self.sev = path, row, campo, msg, sev

    def __str__(self) -> str:
        return f"[{self.sev}] {self.path}:{self.row} {self.campo}: {self.msg}"


def validate_lugar_busqueda(lb: str, nombre: str = "") -> list[str]:
    """Devuelve la lista de problemas. Vacía = válido."""
    errs: list[str] = []
    if not lb.strip():
        return ["vacío"]
    if FORBIDDEN_RE.search(lb):
        errs.append(f"caracteres prohibidos (& + / paréntesis corchetes ~~): {lb!r}")
    parts = [p.strip() for p in lb.split(",")]
    if len(parts) < 2:
        errs.append("falta localidad y país (sin coma)")
        return errs
    if parts[-1] not in COUNTRIES_EN:
        errs.append(f"el último segmento no es un país conocido: {parts[-1]!r}")
    head = normalize(parts[0])
    if head in GENERIC_NAMES and len(parts) < 3:
        errs.append(f"nombre genérico {parts[0]!r} necesita localidad Y país")
    if any(not p for p in parts):
        errs.append("segmento vacío")
    return errs


def validate(path: Path) -> list[Issue]:
    issues: list[Issue] = []
    rel = path.name
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        issues.append(Issue(rel, 0, "-", "el archivo tiene BOM"))
    # Los CSV existentes son CRLF (los escribió csv.DictWriter). Se preserva.
    if raw.count(b"\r\n") != raw.count(b"\n"):
        issues.append(Issue(rel, 0, "-", "line endings mezclados (se espera CRLF en todas)", "warn"))

    with path.open(encoding="utf-8") as f:
        rd = csv.DictReader(f)
        if rd.fieldnames != FIELDS:
            issues.append(Issue(rel, 1, "header", f"header inesperado: {rd.fieldnames}"))
            return issues
        rows = list(rd)

    seen_nombre: dict[tuple[str, str], int] = {}
    seen_coord: dict[tuple[str, float, float], int] = {}
    is_katia = rel == "europa_katia.csv"

    for i, r in enumerate(rows, start=2):
        ciudad = r["ciudad"]

        if r["prioridad"] not in PRIORIDADES:
            issues.append(Issue(rel, i, "prioridad", f"valor inválido {r['prioridad']!r}"))
        if is_katia and r["prioridad"] != "Solo mapeado":
            issues.append(Issue(rel, i, "prioridad", "en europa_katia.csv debe ser 'Solo mapeado'"))

        try:
            lat, lng = float(r["lat"]), float(r["lng"])
        except ValueError:
            issues.append(Issue(rel, i, "lat/lng", f"no numérico: {r['lat']!r},{r['lng']!r}"))
            continue

        if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lng <= BBOX[3]):
            issues.append(Issue(rel, i, "lat/lng", f"fuera del bbox europeo: {lat},{lng}"))
        dec = min(decimals(lat), decimals(lng))
        if dec <= BAD_DECIMALS:
            issues.append(Issue(rel, i, "lat/lng",
                                f"coordenada de baja precisión ({lat},{lng}): {dec} decimales, tipeada a mano"))
        elif dec == WARN_DECIMALS:
            issues.append(Issue(rel, i, "lat/lng", f"precisión justa ({lat},{lng})", "warn"))

        keys = LABEL_TO_KEYS.get(ciudad)
        if not keys:
            issues.append(Issue(rel, i, "ciudad", f"sin área definida en areas.py: {ciudad!r}"))
        else:
            d = min(haversine_km(lat, lng, AREAS[k].lat, AREAS[k].lng) for k in keys)
            lim = max(AREAS[k].max_km for k in keys)
            if d > lim:
                issues.append(Issue(rel, i, "lat/lng",
                                    f"a {d:.1f} km del ancla más cercana de {ciudad} (máx {lim:.0f} km)"))

        for e in validate_lugar_busqueda(r["lugar_busqueda"], r["nombre"]):
            issues.append(Issue(rel, i, "lugar_busqueda", e))

        if r.get("reserva", "") not in RESERVAS:
            issues.append(Issue(rel, i, "reserva", f"valor fuera del vocabulario: {r['reserva']!r}"))

        precio = (r.get("precio") or "").strip()
        if precio and not PRECIO_OK_RE.match(precio):
            issues.append(Issue(rel, i, "precio", f"formato no reconocido: {precio!r}", "warn"))

        url = (r.get("url") or "").strip()
        if url and not URL_OK_RE.match(url):
            issues.append(Issue(rel, i, "url", f"URL mal formada: {url!r}"))

        if not (r.get("descripcion") or "").strip():
            issues.append(Issue(rel, i, "descripcion", "vacía", "warn"))

        kn = (ciudad, normalize(r["nombre"]))
        if kn in seen_nombre:
            issues.append(Issue(rel, i, "nombre", f"duplicado de la fila {seen_nombre[kn]}: {r['nombre']!r}"))
        else:
            seen_nombre[kn] = i

        kc = (ciudad, round(lat, 4), round(lng, 4))
        if kc in seen_coord:
            issues.append(Issue(rel, i, "lat/lng",
                                f"misma coordenada que la fila {seen_coord[kc]} ({r['nombre']!r})"))
        else:
            seen_coord[kc] = i

    return issues


def cross_file_checks(paths: list[Path]) -> list[Issue]:
    """Un mismo lugar no puede estar en dos CSV para la misma ciudad."""
    seen: dict[tuple[str, str], str] = {}
    issues: list[Issue] = []
    for p in paths:
        with p.open(encoding="utf-8") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):
                k = (r["ciudad"], normalize(r["nombre"]))
                if k in seen:
                    issues.append(Issue(p.name, i, "nombre",
                                        f"ya existe en {seen[k]}: {r['ciudad']} / {r['nombre']!r}"))
                else:
                    seen[k] = p.name
    return issues


def main(argv: list[str]) -> int:
    names = argv[1:] or CSVS
    paths = [OUT / n for n in names if (OUT / n).exists()]
    if not paths:
        print("no hay CSV para validar", file=sys.stderr)
        return 2

    all_issues: list[Issue] = []
    for p in paths:
        iss = validate(p)
        all_issues += iss
        n = sum(1 for _ in p.open(encoding="utf-8")) - 1
        errs = sum(1 for x in iss if x.sev == "error")
        print(f"{p.name}: {n} filas · {errs} errores · {len(iss) - errs} warnings")
    all_issues += cross_file_checks(paths)

    by_campo = Counter(x.campo for x in all_issues if x.sev == "error")
    if by_campo:
        print("\nerrores por campo:", dict(by_campo))
    for x in all_issues[:80]:
        print(" ", x)
    if len(all_issues) > 80:
        print(f"  ... y {len(all_issues) - 80} más")

    return 1 if any(x.sev == "error" for x in all_issues) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
