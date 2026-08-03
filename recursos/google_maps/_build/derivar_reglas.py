#!/usr/bin/env python3
"""
Deriva `precio` y `reserva` por reglas baratas, antes del pase web.

Cubre el grueso de plazas, calles, barrios, parques y museos estatales
británicos que el markdown no marcó explícitamente. No inventa montos: si el
tipo no es claramente gratis, deja el campo vacío para investigación web.

Uso:
    python3 derivar_reglas.py            # aplica y reescribe places.json
    python3 derivar_reglas.py --dry-run  # solo reporta
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Tipos al aire libre / urbanos sin taquilla. Una plaza o un puente no cobramos.
TIPOS_GRATIS: frozenset[str] = frozenset({
    "Plaza", "Calle", "Barrio", "Paseo", "Parque", "Jardín", "Mirador",
    "Naturaleza", "Paisaje", "Lago", "Valle", "Glen", "Cementerio",
    "Casco histórico", "Fuente", "Puente", "Escultura", "Monumento",
    "Mercado",  # entrar es gratis; lo que se paga es dentro
})

# Museos estatales británicos con entrada permanente gratis. La exposición
# temporal se anota en `descripcion`, no pisa el precio.
MUSEOS_UK_GRATIS: frozenset[str] = frozenset({
    "british museum", "national gallery", "national portrait gallery",
    "tate modern", "tate britain", "victoria and albert museum", "v&a",
    "natural history museum", "science museum", "imperial war museum",
    "museum of london", "wallace collection", "saatchi gallery",
    "serpentine gallery", "national museum of scotland",
    "scottish national gallery", "scottish national portrait gallery",
    "kelvingrove", "hunterian museum",
})

CIUDADES_UK = {"Londres", "York", "Edimburgo", "Highlands"}


def _norm(s: str) -> str:
    return " ".join((s or "").lower().replace("&", "and").split())


def es_museo_uk_gratis(p: dict) -> bool:
    if p.get("ciudad") not in CIUDADES_UK:
        return False
    if p.get("tipo") not in ("Museo", "Galería", "Institución"):
        return False
    n = _norm(p.get("nombre", ""))
    lb = _norm((p.get("lugar_busqueda") or "").split(",")[0])
    return any(m in n or m in lb for m in MUSEOS_UK_GRATIS)


def derivar(p: dict) -> list[str]:
    """Aplica reglas in-place. Devuelve la lista de campos tocados."""
    tocados: list[str] = []
    origen = p.setdefault("origen", {})

    gratis = p.get("tipo") in TIPOS_GRATIS or es_museo_uk_gratis(p)

    if not p.get("precio") and gratis:
        p["precio"] = "Gratis"
        origen["precio"] = "derivado"
        tocados.append("precio")

    if not p.get("reserva"):
        if p.get("precio") == "Gratis" or gratis:
            p["reserva"] = "No necesaria"
            origen["reserva"] = "derivado"
            tocados.append("reserva")
        elif p.get("url_ticketing"):
            # Hay link de compra pero el .md no dijo si es obligatoria.
            # Recomendada es el default conservador: no bloquea, sí avisa.
            p["reserva"] = "Recomendada"
            origen["reserva"] = "derivado"
            tocados.append("reserva")

    # URL informativa no va al CSV: se vacía el campo accionable pero se
    # conserva la marca para no volver a investigar.
    if p.get("url") and not p.get("url_ticketing"):
        if origen.get("url") != "md_informativa":
            origen["url"] = "md_informativa"
            tocados.append("url_informativa")
        # No borramos de places.json: emit_csvs filtra al escribir.

    return tocados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = HERE / "places.json"
    places = json.loads(path.read_text(encoding="utf-8"))

    cambios: collections.Counter = collections.Counter()
    ejemplos: list[str] = []
    for p in places:
        tocados = derivar(p)
        for t in tocados:
            cambios[t] += 1
        if tocados and len(ejemplos) < 12:
            ejemplos.append(f"  {p['ciudad']:14} {p['nombre'][:40]:42} {tocados}")

    print("derivaciones:")
    for k, v in cambios.most_common():
        print(f"  {k:20} {v}")
    print("ejemplos:")
    for e in ejemplos:
        print(e)

    n = len(places)
    print("\ncobertura tras derivar:")
    for c in ("precio", "descripcion", "url", "reserva", "mejor_momento"):
        k = sum(1 for p in places if p.get(c))
        print(f"  {c:15} {k:4}/{n}  ({100 * k // n}%)")

    if not args.dry_run:
        path.write_text(json.dumps(places, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nescrito {path}")
    else:
        print("\n(dry-run: no se escribió)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
