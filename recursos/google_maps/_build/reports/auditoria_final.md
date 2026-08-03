# Auditoría de coordenadas — 2026-08-03

Corrida: `python3 audit_coords.py --out auditoria.csv` sobre los **1243** lugares.
Señales: S1 re-resolución · S2 reverse-geocode · S3 decimales · S4 encuadre en área.

## Resultado

| Veredicto | N | % |
|---|---|---|
| `verificado` | 1091 | 87.8% |
| `revisar` | 123 | 9.9% |
| `no_verificable` | 29 | 2.3% |

Meta del plan: ≥95% `verificado`. Falta afinar el clasificador (muchos `revisar` son el resolver confundido con un homónimo, no el pin mal puesto) y cerrar los `no_verificable`.

## Correcciones aplicadas hoy → `overrides.json`

Homónimos que dejaron el pin en **otra ciudad**:

| Ciudad | Lugar | Estaba en | Corregido a |
|---|---|---|---|
| Lisboa | Convento do Carmo | Colares (Sintra), 28 km | Lisboa centro |
| Budapest | Barrio Judío | Érd, 18 km | Erzsébetváros |
| Cracovia | Podgórze | Luborzyca, 15 km | Podgórze (Kraków) |
| Barcelona | Eixample | Alella, 15 km | Eixample (BCN) |
| Florencia | Mercado Central | Campi Bisenzio, 11 km | Mercato Centrale |
| Cracovia | Arka Pana | Bieżanów, 7 km | Bieńczyce |
| Cracovia | Mina de Sal | (coord OK) | `lugar_busqueda` → Wieliczka |

## Falsos `revisar` frecuentes

- **s3=-1 solo** (≤3 decimales): el pin está bien, falta procedencia. Ej. Reloj Astronómico (7 m), Lukács (5 m).
- **s1=-1 con reverse en la ciudad correcta**: el resolver eligió un homónimo; la coordenada guardada es la buena. Ej. House of MinaLima (Soho), Kościół Mariacki (Plac Mariacki), Parlamento de Budapest.
- **Day trips** (Sintra, Cascais, Auschwitz, Haut-Koenigsbourg, Breisach): `s4=-1` es esperado.
- **Highlands**: Nominatim devuelve localidad `Highland` (council) vs el pueblo del `lugar_busqueda` → falso `s2=-1`.

La lógica de veredicto en `audit_coords.py` ya se suavizó para estos casos; conviene re-puntuar el CSV sin red o re-correr la auditoría.

## `no_verificable` (29)

Lugares que ninguna fuente resolvió con Overpass apagado (default). Incluyen sitios famosos (`Stephansdom`, `Zapatos en el Danubio`, `Muro de John Lennon`) — probablemente rate-limit / nombre local incompleto. Re-correr con `--overpass` o queries alternativas.

Lista completa en `reports/auditoria.csv` filtrando `veredicto=no_verificable`.

## Archivos

- `reports/auditoria.csv` — veredicto por fila (1243)
- `reports/auditoria_londres_smoke.csv` — smoke 15/15 verificado
- `overrides.json` — 13 entradas con `source` + `url` + `checked_at`
