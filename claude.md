# Contexto del Repositorio: Viaje a Europa 2026

Este archivo sirve como contexto macro del proyecto para que cualquier nuevo agente entienda rápidamente de qué se trata, cómo está estructurado el repositorio y cuáles son las convenciones.

## 1. Visión General del Proyecto
Este repositorio contiene toda la planificación, itinerario y recursos para un viaje a Europa de 109 días (108 noches).

- **Fechas:** 5 de agosto al 21 de noviembre de 2026.
- **Viajeros:** 2 personas (excepto en Portugal del 4 al 12 de septiembre, que es para 1 persona).
- **Alcance:** 13 países y 23 paradas/bases principales, más un margen de días flexibles.
- **Presupuesto Estimado:** $9,000 - $13,000 por persona.

## 2. Estructura del Repositorio

### ¡Importante!
**Ignorar la carpeta `operativo-app/`**. No forma parte del planeamiento del viaje documentado en Markdown.

### Archivos Raíz (Maestros)
Contienen la información consolidada y de alto nivel de todo el viaje:
- `README.md`: Resumen general, ruta completa y estado del proyecto.
- `CHECKLIST.md`: Panel de control de tareas pendientes, reservas críticas (vuelos, alojamiento, atracciones muy solicitadas).
- `ITINERARIO_GENERAL.md`: Cronograma exacto con fechas y ciudades.
- `PRESUPUESTO.md`: Estimaciones de gasto por país.
- `TRANSPORTE_ENTRE_CIUDADES.md`: Logística entre puntos (Eurail, vuelos internos, trenes nocturnos, alquiler de autos).
- `TIPS_VIAJE.md`: Compilación de consejos clave de Reddit y foros sobre supervivencia (ej. evitar estafas, reglas gastronómicas, cómo evitar el "burnout" del viajero).

### Carpetas por Destino
Están numeradas secuencialmente y agrupadas por país y ciudad. Ejemplo: `01_Reino_Unido/Londres/`.
Dentro de la carpeta de **cada ciudad/base**, se sigue siempre la misma estructura de archivos:
- `actividades.md`: Qué hacer, tiempos estimados y organización.
- `alojamiento.md`: Opciones de estadía investigadas y mejores zonas recomendadas.
- `transporte.md`: Cómo llegar a la ciudad y cómo moverse internamente.
- `desvios_cercanos.md`: Posibles "day trips" o visitas a pueblos y lugares cercanos.

### Carpeta `recursos/`
Contiene información transversal útil para todo el viaje:
- `apps_utiles.md`
- `documentos.md` (Visas, ETIAS, seguros)
- `packing_list.md` (Qué llevar)
- `asistencia_al_viajero_comparativa.md`
- `frases_utiles.md`

## 3. Estado Actual y Tareas Pendientes
La estructura básica (carpetas, archivos e investigación preliminar) está **completada**. 
Todas las tareas accionables y reservas pendientes están centralizadas en **`CHECKLIST.md`**. Si vas a trabajar en reservas o trámites, ese es el archivo a consultar y actualizar.

## 4. Convenciones a seguir por los agentes
- Al actualizar reservas o tareas, modificar siempre `CHECKLIST.md`.
- Al agregar información específica de una ciudad, respetar los nombres de los 4 archivos estándar dentro de la carpeta correspondiente.
- Tener presente las advertencias y reglas de supervivencia mencionadas en `TIPS_VIAJE.md` al sugerir itinerarios (ej. horarios de la "Riposo" en Italia, anticipación crítica para atracciones específicas).
- Responder siempre en español, según las reglas del usuario.