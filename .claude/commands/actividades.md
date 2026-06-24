# Skill: Estandarizar actividades.md

Sos un experto en planificación de viajes. Tu tarea es llevar el o los archivos `actividades.md` indicados al estándar consolidado del repositorio, investigando con fuentes reales (Reddit, foros, sitios oficiales) y **preservando todo el contenido de valor existente**.

## Invocación

`/actividades <ciudad> [ciudad2 ciudad3 ...]`

Ejemplo: `/actividades París Lisboa Porto`

Se procesan las ciudades **en orden**, una por una, con check entre cada una.

---

## Paso 1 — Localizar el archivo

Para cada ciudad en `$ARGUMENTS`, encontrar el archivo con:

```bash
find /Users/brunotamaro/Desktop/Trip/Itinerary -name "actividades.md" -path "*$CIUDAD*"
```

Si hay ambigüedad (varios resultados), mostrarle las opciones al usuario y preguntar antes de continuar.

Si la ciudad no se encuentra (0 resultados), intentar variantes de nombre (tildes, mayúsculas, nombre parcial) antes de preguntar.

---

## Paso 2 — Leer el archivo existente

Leer el `actividades.md` actual en su totalidad. Hacer un inventario mental:
- ¿Qué contenido de valor tiene que hay que **conservar**?
- ¿Cuántos `Ver PRESUPUESTO.md` u otros placeholders hay que **reemplazar**?
- ¿Qué secciones obligatorias **faltan**?
- ¿Qué categorías o actividades están **ausentes** pero deberían estar?

**Regla de oro: nunca borrar información de valor. Reformatear, expandir, completar — nunca recortar.**

---

## Paso 3 — Investigación (hilo conductor: opiniones repetidas de viajeros y locales)

**El principio de autenticidad:** todo lo que entre al archivo debe poder respaldarse con algo que dijeron viajeros reales o locales, no con lo que dice la guía oficial. La pregunta que hay que hacerse siempre es: *¿esto lo dicen los viajeros, o lo dice la guía de turismo?* Si solo lo dice la guía, va al final. Si lo repiten en varios hilos de foros distintos, va arriba.

Un dato que aparece en un solo hilo es un dato. Un dato que aparece en **tres foros distintos** es consenso. El consenso es lo que estructura el archivo: qué va primero, qué lleva advertencia, qué merece un tip en negrita.

Los locales tienen peso especial: si un local dice "eso no lo hacemos nosotros" o "esto es trampa turística", se pone como nota visible. Si un local dice "aquí venimos nosotros a comer", se pone en gastronomía con esa distinción explícita.

**Regla de recencia:** priorizar hilos y fuentes de 2024-2026. Las ciudades cambian (precios, obras, cierres, sistemas de reserva). Si un dato clave solo aparece en hilos viejos, incluirlo pero marcarlo explícitamente: `(dato 2022 — verificar)`. Nunca presentar como vigente algo cuya única fuente tiene más de ~2 años.

### 3a. Reddit/foros (obligatorio)

Buscar en **dos capas**, y etiquetar cada hallazgo según su origen como `[local]` o `[viajero]`:

**Capa viajeros** — subreddits turísticos (`r/paris`, `r/LisbonPortugalTravel`, `r/porto`, `r/vienna`, `r/prague`, `r/krakow`, `r/budapest`, `r/travel`, `r/eurotrips`, etc.) y foros como TripAdvisor, Lonely Planet Thorn Tree, Nomadic Matt, minube, Foro Viajes (español).

**Capa locales** (acá está el oro; no saltarla):
- Subreddits **de residentes**, no de turismo: `r/Amsterdam` (vs `r/Amsterdamtourism`), `r/AskFrance`, `r/AskUK`, `r/de`, `r/Austria`, `r/Polska`, `r/czech`, `r/hungary`, `r/Slovenia`, `r/italy`, `r/askspain`, etc.
- Hilos de gente que **vive ahí o se mudó**: buscar "moving to [ciudad]", "living in [ciudad]", "what do you wish tourists knew [ciudad]", "tourists always ask [ciudad]".
- **Búsquedas en el idioma local** — los foros en inglés ya están masticados; los locales no:
  - Alemán: "[ciudad] geheimtipps", "[ciudad] insider tipps"
  - Francés: "[ciudad] bonnes adresses", "[ciudad] bons plans"
  - Italiano: "[ciudad] posti poco conosciuti", "dove mangiano i [gentilicio]"
  - Portugués: "[ciudad] dicas de quem mora", "[ciudad] fora do roteiro"
  - Neerlandés: "[ciudad] verborgen plekjes"
  - Checo: "kam na výlet [ciudad]" / Polaco: "[ciudad] nieoczywiste miejsca" / Húngaro: "[ciudad] rejtett helyek" / Esloveno: "[ciudad] skriti kotički"
  - Español (España): "[ciudad] sitios poco turísticos", "donde comen los locales"

Preguntas clave a responder con fuentes reales:
- ¿Qué dice la gente que **no se puede saltar**? (¿cuántos hilos lo repiten?)
- ¿Cuál es el tip más repetido que **no está en las guías oficiales**?
- ¿Qué atracción es "sobrevalorada según los viajeros" (no según la guía)?
- ¿Qué atracción es una **sorpresa inesperada** que los viajeros descubren y recomiendan?
- ¿Qué dicen los **locales** que vale la pena y los turistas no ven?
- ¿Qué hay que reservar con X semanas de anticipación y por qué (experiencia de alguien que no lo hizo)?
- ¿Cuál es el barrio local favorito vs. el más turístico?

### 3b. Precios oficiales 2026
Para cada atracción de pago, verificar en el sitio oficial o plataformas de venta (GetYourGuide, Musement, Tiqets). **No inventar ni estimar precios.** Si no se encuentra precio verificado: omitir el precio o marcar `(verificar en [sitio])`.

Monedas por país:
- UK: GBP (£) — verificar tipo de cambio si conviene
- Países Bajos, Francia, Portugal, Alemania, Austria, Eslovenia, Italia, España: EUR (€)
- Suiza: CHF — siempre añadir conversión aproximada a € entre paréntesis (1 CHF ≈ €1.08 a junio 2026)
- Chequia: CZK — siempre añadir conversión € (verificar tipo al momento)
- Polonia: PLN — siempre añadir conversión €
- Hungría: HUF — siempre añadir conversión €

### 3c. Free Walking Tours
Investigar operadores concretos con punto de encuentro exacto:
- **SANDEMANs**: EN + ES (freelancers, propina). Verificar si opera en la ciudad.
- **Civitatis**: tours guiados pagados; opción ES más confiable; sin obligación de propina.
- **GuruWalk**: marketplace; EN y ES; verificar reviews del guía individual.
- **Operadores locales**: buscar "[ciudad] free walking tour reddit" para encontrar los que usan los locales.

Para cada operador confirmado incluir: punto de encuentro **exacto** (dirección, estatua, punto de referencia), horarios, idioma, y si hay propina o precio fijo.

### 3d. Investigación por fechas exactas de la estadía (obligatorio)

Las fechas de cada ciudad están en el header del archivo (o en `ITINERARIO_GENERAL.md`). Cruzar el calendario del viaje con el de la ciudad:

- **Eventos y festivales** que caen durante la estadía (música, gastronomía, ferias, eventos deportivos que llenan hoteles o cortan calles).
- **Feriados locales/nacionales** en esos días: qué cierra (museos, comercios), transporte reducido, qué se celebra.
- **Cierres por día de semana**: si la estadía es lun-mié y el museo clave cierra lunes, decirlo explícitamente.
- **Mercados y actividades que solo ocurren ciertos días** (mercados de sábado, vísperas, horarios de verano/invierno).
- **Renovaciones y cierres activos en 2026**: buscar "[atracción] closed renovation 2026" para las 3-5 atracciones principales.
- **Clima y luz del mes exacto**: temperaturas reales esperadas, lluvia, horas de luz (relevante en oct-nov).

Si las fechas son post-Portugal (tentativas), investigar igual para el rango tentativo y marcar la sección como tentativa.

---

## Paso 4 — Reescribir al estándar

### Formato de cada actividad

```
- [ ] **Nombre** [pass/card si aplica] - descripción concisa (precio en negrita) — tip clave o dato de Reddit `link-oficial`
```

- Un solo renglón por actividad.
- Precio siempre en `**negrita**`. Si es gratis: `GRATIS`. Si no se verificó: omitir o `(verificar en sitio.com)`.
- El link siempre en backticks `` `https://...` ``.
- Si tiene pase/card que cubre la entrada: agregar `[nombre-del-pase]` entre corchetes después del nombre.

### Categorías con emoji (usar las relevantes, en este orden aproximado)

```
## 🏛️ Museos y Atracciones Pagadas
## 🎭 Cultura y Espectáculos  
## 🌆 Miradores y Panorámicas
## 🚶 Barrios y Callejeo (gratis)
## 🌿 Parques y Naturaleza
## 🍽️ Gastronomía
## 🗺️ Day Trips / Desvíos Cercanos
## 💎 Off the Beaten Path
## 🎟️ Pases y Cards de Ciudad
```

Adaptar según la ciudad. No forzar categorías que no aplican.

### Criterio de cobertura — CRÍTICO

**Mapear el máximo posible, no curar.** El objetivo es ser exhaustivo: todo lo que un viajero podría querer hacer (atracciones mayores, museos, miradores, barrios, gastronomía, day trips, joyas locales). Ordenar implícitamente por importancia dentro de cada categoría (lo imprescindible arriba). El usuario decide después qué se queda y qué no. **No descartar ninguna actividad por "menor"** — si aparece en foros o tiene valor, va incluida.

### Secciones obligatorias (siempre al final del archivo, en este orden)

#### 1. `## 🚶 Free Walking Tour`

Una subsección por operador confirmado:

```markdown
### SANDEMANs (EN/ES)
- Tour diario a las **11:00h y 14:00h** (verificar temporada)
- Punto de encuentro: **[lugar exacto, dirección o referencia visual clara]**
- Freelancers; ingreso = propina (sugerido €5-10 pp)
`https://...`

### Civitatis (ES)
- Tours en español; guía contratado; precio fijo **€X**
`https://...`

### GuruWalk (EN/ES)
- Marketplace; verificar reviews del guía individual antes de reservar
- Punto de encuentro: **[lugar exacto]**
`https://...`
```

Si SANDEMANs o algún operador no opera en esa ciudad, decirlo explícitamente: `> SANDEMANs no opera en [ciudad].`

#### 2. `## 🧠 Consenso Reddit/Foros`

Mínimo 5-7 bullets. Cada bullet debe reflejar algo que se repite en **varios** hilos o que lo dice un local con peso específico. No incluir lo que solo aparece en un sitio.

**Cada bullet lleva al menos un link al hilo fuente en backticks** — sin link, el bullet no entra. Esto permite volver a la fuente para profundizar y es la garantía de que el consenso no está inventado. Marcar el origen con `[local]` o `[viajero]` cuando aporte. Formato:

```markdown
- **[tema/atracción]** — [paráfrasis del sentimiento repetido; ej: "aparece en al menos 4 hilos de r/paris como imprescindible"] `https://reddit.com/...`
- **Tip más repetido:** [tip concreto que aparece una y otra vez, no en la guía oficial] `https://...`
- **Lo que dicen los locales [local]:** [opinión de local, explicitada como tal] `https://...`
- **Joya inesperada:** [lugar o actividad que los viajeros descubren y recomiendan; no está en Lonely Planet] `https://...`
- **Sobrevalorado según viajeros:** [qué bajarle las expectativas o saltar directamente] `https://...`
- **Reservar con anticipación:** [qué y con cuánto tiempo; idealmente respaldado por alguien que llegó sin reserva] `https://...`
- **Trampa turística frecuente:** [si hay consenso de foro sobre algo que engaña o decepciona] `https://...`
```

Si no se encontró consenso real sobre alguno de estos puntos (no hay hilos sobre ese tema), omitir el bullet — mejor vacío que inventado.

#### 3. `## 📅 Durante tus fechas (2026)`

Resultado del paso 3d, aplicado a las fechas concretas de la estadía:

```markdown
## 📅 Durante tus fechas (2026)

**Estadía:** [fechas y días de semana, ej: mar 25 – sáb 29 ago]

- **Eventos:** [festival/evento que cae en esos días, con link] — o "sin eventos mayores detectados"
- **Feriados:** [feriado local en esas fechas y qué cierra] — o "sin feriados"
- **Cierres por día de semana:** [ej: "Museo X cierra lunes → visitar mar-vie"]
- **Solo esos días:** [mercado de sábado, evento semanal que coincide]
- **Renovaciones/cierres 2026:** [atracción cerrada o parcialmente cerrada, con fuente]
- **Clima y luz:** [temp. esperada, lluvia, amanecer/anochecer del mes exacto]
```

Si las fechas son tentativas (post-Portugal), encabezar con `> Fechas tentativas — re-verificar al confirmar`.

#### 4. `## 💡 Tips`

Subsecciones prácticas: Logística, Transporte, Clima, Costumbres sociales, Dinero, Mejor época, etc. según corresponda.

#### 5. `## ⚠️ Precios Oficiales de Referencia (2026)` ← siempre al final

Tabla markdown con todas las atracciones de pago del archivo:

```markdown
| Atracción | Precio adulto | Reducido | Nota |
|-----------|--------------|----------|------|
| Museo X   | **€15**       | €10 (-26) | cerrado lunes; sitio.com |
```

Incluir: nombre, precio adulto en negrita, precio reducido si aplica, notas clave (día de cierre, reserva obligatoria, gratuidad específica, fuente).

Al pie de la tabla, listar las fuentes: `**Fuentes:** museoX.com · sitioY.com`

---

## Paso 5 — Guardar y verificar

Guardar el archivo con Write/Edit. **No hacer commit.** Dejar en working tree para revisión manual.

Verificación rápida antes de dar por terminada la ciudad:
- [ ] Formato una-línea con `##`+emoji en todas las categorías
- [ ] Cero `Ver PRESUPUESTO.md` u otros placeholders
- [ ] Las 5 secciones obligatorias presentes (FWT, Consenso Reddit, Durante tus fechas, Tips, Precios Oficiales)
- [ ] Cada bullet del Consenso tiene al menos un link a su hilo fuente
- [ ] Datos cuya única fuente tiene >2 años marcados con `(dato AAAA — verificar)`
- [ ] Todos los precios en `**negrita**`; ninguno inventado
- [ ] Todo el contenido de valor del archivo original preservado
- [ ] Links en backticks

---

## Paso 6 — Confirmar y continuar

Después de cada ciudad, informar en 2-3 líneas qué se hizo (actividades añadidas, precios reemplazados, secciones nuevas). Si hay más ciudades en `$ARGUMENTS`, procesar la siguiente sin preguntar.

Al terminar todas las ciudades: `git status` para confirmar que solo se modificaron los `actividades.md` esperados.

---

## Archivos de referencia (releer si hay duda sobre el formato)

Los archivos más completos y recientes del repositorio, en orden de prioridad:
1. `02_Paises_Bajos/Amsterdam/actividades.md` — modelo principal
2. `01_Reino_Unido/York/actividades.md` — modelo para ciudad chica/media
3. `01_Reino_Unido/Londres/actividades.md` — modelo para ciudad grande

---

## Contexto del viaje

- **Viajeros:** 2 personas (P1 + P2), excepto Portugal 4-12 sept = solo P2
- **Fechas:** 5 agosto – 21 noviembre 2026
- **Presupuesto:** estimado en `PRESUPUESTO.md`
- **Post-Portugal:** fechas tentativas; no presentar como definitivas
- **Idioma de respuesta:** siempre español
