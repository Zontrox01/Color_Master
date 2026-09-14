# ColorMaster — Estado del proyecto y mapa de archivos

Última actualización: incorporación de la carga perezosa de la base de datos de pigmentos (índice ligero + un Excel por fabricante+tipo).

## Resumen de dónde estamos

- ✅ **Arquitectura de datos de pigmentos rediseñada** para que la app siga siendo rápida aunque la base de datos crezca a miles de colores:
  - `database/pigment_index.xlsx`: archivo diminuto (una fila por combinación marca+tipo) que se carga siempre al arrancar.
  - Un Excel por fabricante+tipo (`golden_convertido.xlsx`, `winsor_acuarela_convertido.xlsx`, etc.), que solo se carga en memoria cuando el usuario decide explorar ese catálogo concreto.
  - Cada pigmento tiene un **`pigment_id` estable** (`marca__tipo__nombre` normalizado), generado por `utils/conversor_lab_hex.py`, que no cambia aunque se añadan o reordenen fabricantes.
  - La paleta del usuario se guarda en SQLite de forma **autocontenida**: cuando se añade un pigmento se copian ahí mismo su nombre, marca, tipo, hex y opacidad. Esto significa que mostrar la paleta guardada o calcular una mezcla **nunca** necesita releer ningún Excel de fabricante, sin importar cuántos haya en el índice ni cuántos tenga cada uno. Probado: leer una paleta de 4 pigmentos de 2 fabricantes distintos tarda ~0.0002s.
  - `pigment_data.xlsx` (el Excel maestro consolidado de la versión anterior) queda **obsoleto para la aplicación** — ya no lo usa ningún código. Se conserva solo como referencia/backup.
- ✅ Fase 0 (investigación + conversor Lab→HEX): script funcionando. 5 fuentes activas: Golden, Winsor & Newton (acuarela + óleo) y Schmincke (81 colores de muestra inicial, ver aviso sobre fiabilidad más abajo), y **Daniel Smith Acuarela (214 colores, datos oficiales reales)** = **295 pigmentos en total**.
- ⏸️ Ampliar a catálogos completos de cada marca: aparcado por decisión del usuario, se retoma más adelante. Añadir un fabricante nuevo ahora es: generar su Excel con el conversor → añadir una entrada en `database/build_index.py` → ejecutarlo.
- ✅ `core/color_math.py`, `core/mixer.py`: completos y probados (ver detalle más abajo, sin cambios funcionales en este paso salvo que `Pigment.id` ahora es el `pigment_id` estable en vez de un entero).
- ✅ `database/db_manager.py`: reescrito para el nuevo esquema autocontenido (ver "Esquema SQLite" más abajo).
- ✅ `ui/palette_manager.py`: reescrito. Ahora tiene: selector de paleta activa (Nueva/Renombrar/Eliminar), un explorador de catálogo (combo con el índice + botón "Cargar" + lista con checkboxes) y una sección "Mi paleta" que siempre lee directo de SQLite.
- ✅ `utils/history.py`, `ui/history_dialog.py`: sin cambios, siguen funcionando igual.
- ✅ `utils/exporters.py`: **completo y probado generando PDFs reales** (no solo compilado — pude ejecutar reportlab en este entorno). Incluye color master + complementario con toda su info (RGB/HSV/HSL/CMYK), los 5 gradientes (con las filas partidas automáticamente en dos si hay muchos colores, para que el hex no se corte), tabla de la paleta del usuario, la mezcla sugerida, e historial reciente de colores y mezclas. Corregido tras inspección visual: el símbolo Δ no lo soporta la fuente base de reportlab (aparecía en blanco) — se usa "dE" en su lugar dentro del PDF. Integrado en `main_window.py` con el botón "Exportar a PDF" (abre un diálogo para elegir dónde guardar).
- ✅ `utils/history.py`: ampliado con `export_to_file()`/`import_from_file()` (JSON, sin límite de registros) y `clear_all()`. Probado: exportar, borrar y volver a importar recupera exactamente lo mismo; importar dos veces suma en vez de duplicar-reemplazar. `log_color`/`log_mix` ahora aceptan una `fecha` explícita para preservarla al importar.
- ✅ `ui/main_window.py`: las opciones de historial (antes un botón suelto) ahora viven en una sección "Historial" con 4 botones: Ver, Guardar en archivo, Cargar desde archivo, Borrar. Borrar pregunta primero si se quiere guardar (Sí/No/Cancelar); si se cancela el guardado, tampoco se borra. Cargar pregunta Añadir/Sustituir/Cancelar; si se elige Sustituir, antes ofrece guardar el historial actual (misma lógica que Borrar) antes de reemplazarlo. ⚠️ Pendiente de probar la ejecución real en Windows.
- ✅ **El usuario ya puede añadir un fabricante nuevo o una tinta a uno existente**, sin tocar ningún Excel. Diseño (ver conversación para el razonamiento completo):
  - Tabla nueva `pigmentos_personalizados` en el mismo SQLite del usuario (no en los Excel de `database/`, para que funcione aunque la app se instale en una carpeta de solo lectura).
  - `pigment_id` con prefijo `custom__` para que nunca choque con uno oficial.
  - `ui/add_pigment_dialog.py` (nuevo): diálogo con marca/tipo/nombre, dos modos de color (hex directo con el mismo selector que el master, o valores L\*a\*b\* si el usuario tiene una ficha técnica), opacidad, fiabilidad (1-5, el usuario autoevalúa cuánto se fía de su propio dato) y fuente.
  - `ui/palette_manager.py`: botón "+ Añadir fabricante o tinta"; el desplegable "Explorar catálogo" fusiona el índice oficial con los catálogos personalizados (si coincide marca+tipo, se combinan en una sola entrada con el conteo de "N oficiales + M tuyos"; si la marca es 100% nueva, aparece como entrada propia).
  - Refactor de paso: la conversión L\*a\*b\*→hex y la generación de `pigment_id` se movieron a `core/color_math.py` (`lab_to_hex`, `make_pigment_id`), reutilizadas tanto por `utils/conversor_lab_hex.py` como por el diálogo nuevo. Probado que el refactor no cambió ningún resultado (regresión verificada byte a byte contra los archivos anteriores).
  - Probado de extremo a extremo (sin Qt): cargar un catálogo oficial, añadir una tinta a ese mismo fabricante, recargar y verla fusionada; y crear un fabricante 100% nuevo, verlo aparecer en el desplegable combinado. Todo persiste entre reinicios.
  - ⚠️ Pendiente de probar la ejecución real de la UI en Windows.
- ✅ **Estilos claro/oscuro con acentos pastel**: completo. `resources/light_theme.qss` y `resources/dark_theme.qss` (lavanda/menta, con contraste adaptado en el oscuro), cargados desde `ui/theme.py`. `main.py` aplica el claro por defecto al arrancar. Botón "🌙 Modo oscuro" / "☀️ Modo claro" arriba del todo en el panel izquierdo, que alterna al instante. Probado: ambos `.qss` cargan sin errores y tienen las llaves balanceadas; no he podido verlo renderizado en pantalla (sin PySide6 aquí), así que la valoración visual final la haces tú.
- ✅ **Daniel Smith Acuarela añadido: 214 colores, fiabilidad 5/5**. Fuente: datos **oficiales reales** del propio fabricante en danielsmith.com — la tabla pública "CIE Lab Coordinates" (Lab de ~220 colores single-pigment, sin necesidad de cuenta ni login) cruzada por nombre con su PDF oficial "Pigment Characteristics" (transparencia: Opaque/Semi-Opaque/Semi-Transparent/Transparent, mapeada a opacidad numérica). Verificado visualmente: Ultramarine Blue, Burnt Sienna, Titanium White, etc. dan hex coherentes con el color real. Índice actualizado: **295 pigmentos en total** entre 5 fuentes.
- ⏹️ **Ampliación de la base de datos: pausada por decisión del usuario.** Resumen de la investigación (13 fabricantes comprobados de la lista original): solo **Daniel Smith** publica sus propias coordenadas Lab en abierto, sin login. El resto (Schmincke, Winsor & Newton, Holbein, Sennelier, Old Holland, M. Graham, Michael Harding, Van Gogh, Isaro, A. Gallo, Roman Szmal, Daler-Rowney, Mijello, Cotman) solo ofrece cartas de color en PDF/imagen sin valores numéricos, o los tiene bloqueados detrás de una cuenta en artistpigments.org (confirmado que el bloqueo es real incluso en páginas de color individuales, no solo en la vista general). Se encontró un diccionario de Winsor & Newton con licencia libre (MIT, Aubrey Jaffer 2010) con Lab real, pero se descartó por usar nomenclatura genérica/antigua no verificable contra el catálogo actual. **Estado final: 214 pigmentos (solo Daniel Smith) en el índice**, todos de fiabilidad 5/5. Se retoma cuando el usuario decida, con el mismo criterio estricto de "solo fuentes verificables, si no hay, se descarta".
- ✅ **`ui/add_pigment_dialog.py` mejorado**: los campos Marca y Tipo ya no son un combo editable de texto libre (que podía crear duplicados por errores de tecleo, ej. "Golden" vs "golden "). Ahora son un par de radio buttons cada uno: "Existente" (con desplegable de los valores ya presentes en la base de datos, opción por defecto) o "Nuevo" (con campo de texto en blanco). Si no hay ningún fabricante todavía en la base de datos, arranca automáticamente en modo "nuevo". También se corrigió un bug de alternancia entre "Elegir color directamente" / "Introducir valores L*a*b*" (los radios no se excluían mutuamente de forma fiable) agrupándolos explícitamente con `QButtonGroup` — se hizo lo mismo con los de marca y tipo por robustez.
- ✅ **Búsqueda por nombre dentro del catálogo cargado**: campo de texto encima de la lista en "Explorar catálogo" (`ui/palette_manager.py`), filtra en vivo sin distinguir mayúsculas/minúsculas, sin tocar la paleta guardada ni recargar el Excel. Se limpia automáticamente al cargar un catálogo nuevo. Probado con los 214 colores reales de Daniel Smith.
- ⏳ Detalles finos de `palette_manager.py` / `add_pigment_dialog.py`: pendiente de revisar más adelante (lo mencionaste tras probar "añadir tinta").

## Estructura de carpetas

```
ColorMaster/
├── FILES.md
├── requirements.txt
├── main.py                       # punto de entrada (carga traducción es_ES de Qt)
├── ui/
│   ├── __init__.py
│   ├── main_window.py            # layout de 3 paneles + control de nº de colores por gradiente
│   ├── color_selector.py         # selector tipo Photoshop, swatch clicable, hex/RGB/CMYK
│   ├── gradient_widget.py        # fila de N rectángulos + hex debajo
│   ├── palette_manager.py        # explorador de catálogo (oficial + personalizado) + paleta
│   ├── add_pigment_dialog.py     # añadir fabricante nuevo o tinta a uno existente
│   ├── theme.py                  # ✅ NUEVO — carga/aplica los .qss claro/oscuro
│   └── history_dialog.py         # diálogo con pestañas: historial de colores y mezclas
├── core/
│   ├── __init__.py
│   ├── color_math.py             # conversiones + gradientes + complementario + lab_to_hex + make_pigment_id
│   ├── mixer.py                  # pseudo-K-M por canal, delta_e76, suggest_mix()
│   └── models.py                 # (pendiente, probablemente ya no haga falta)
├── database/
│   ├── __init__.py
│   ├── db_manager.py             # paletas + pigmentos_personalizados (ver esquema abajo)
│   ├── build_index.py            # ✅ NUEVO — regenera pigment_index.xlsx (ejecutar al añadir un fabricante)
│   ├── pigment_index.xlsx        # ✅ NUEVO — índice ligero (marca, tipo, archivo, num_colores, fiabilidad, fuente)
│   ├── pigment_data.xlsx         # ⚠️ OBSOLETO para la app — ya no lo lee ningún código, solo referencia
│   ├── golden_convertido.xlsx           # Golden / Acrílico — 24 colores, con columna pigment_id
│   ├── winsor_acuarela_convertido.xlsx  # Winsor & Newton / Acuarela — 23 colores
│   ├── schmincke_convertido.xlsx        # Schmincke / Acuarela — 17 colores
│   ├── winsor_oleo_convertido.xlsx      # Winsor & Newton / Óleo — 17 colores
│   ├── daniel_smith_acuarela_convertido.xlsx  # ✅ Daniel Smith / Acuarela — 214 colores, fiabilidad 5
│   └── user_palettes/
│       └── user_palette.db       # SQLite generado automáticamente al primer arranque
├── utils/
│   ├── __init__.py
│   ├── conversor_lab_hex.py      # genera hex + pigment_id estable
│   ├── exporters.py              # ✅ HECHO Y PROBADO — exportación a PDF (reportlab)
│   └── history.py                # historial de colores y mezclas (SQLite)
├── resources/
│   ├── light_theme.qss           # ✅ tema claro, acentos pastel
│   └── dark_theme.qss            # ✅ tema oscuro, mismos acentos
└── data_sources/                 # CSV originales tal como se encontraron
```

## Esquema SQLite (`database/user_palettes/user_palette.db`)

```sql
CREATE TABLE palettes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    fecha_creacion TEXT NOT NULL
);

-- Autocontenida a propósito: NO es solo una referencia a un id externo.
-- Guarda todo lo necesario para mostrar la paleta y calcular mezclas
-- sin volver a tocar ningún Excel de fabricante.
CREATE TABLE paleta_pigmentos (
    paleta_id INTEGER NOT NULL,
    pigmento_id TEXT NOT NULL,      -- pigment_id estable
    marca TEXT NOT NULL,
    tipo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    hex TEXT NOT NULL,
    opacidad REAL NOT NULL DEFAULT 1.0,
    cantidad_aproximada TEXT,
    fecha_anadido TEXT NOT NULL,
    PRIMARY KEY (paleta_id, pigmento_id),
    FOREIGN KEY (paleta_id) REFERENCES palettes(id) ON DELETE CASCADE
);
```

## Cómo añadir un fabricante nuevo (flujo actualizado)

```powershell
# 1. Convertir el CSV/Excel de origen (genera hex + pigment_id automáticamente)
python utils/conversor_lab_hex.py --input data_sources/mi_fabricante.csv --output database/mi_fabricante_convertido.xlsx --fuente "Mi Fabricante Official" --marca "Mi Fabricante" --fiabilidad 5

# 2. Añadir una entrada en database/build_index.py (lista SOURCES) con marca, tipo y el nombre del archivo

# 3. Regenerar el índice
python database/build_index.py
```

La aplicación detectará el fabricante nuevo en el desplegable "Explorar catálogo" la próxima vez que arranque, sin que el arranque se vuelva más lento (el índice sigue siendo pequeño).

## API de `core/color_math.py`

```python
from core import color_math as cm

info = cm.ColorInfo.from_hex("#3B82F6")  # .rgb .hsv .hsl .cmyk .complementary
cm.gradient_brightness("#3B82F6", n)   # -> lista de n hex (n entre 3 y 27)
cm.gradient_saturation("#3B82F6", n)
cm.gradient_hue("#3B82F6", n)
cm.gradient_lightness("#3B82F6", n)
cm.gradient_transition("#3B82F6", "#F59E0B", n)
```

## API de `core/mixer.py`

```python
from core import mixer as mx

# Pigment.id es ahora el pigment_id estable (string), no un entero.
pigments = [mx.Pigment.from_row(row_dict) for row_dict in ...]  # de un Excel o de db.get_pigments()

result = mx.suggest_mix("#7A5C3E", pigments, max_pigments=4)
result.as_percentages()   # -> [(Pigment, 30.0), (Pigment, 68.0), ...]
result.resulting_hex
result.delta_e             # < 3 = buena coincidencia

mx.delta_e76(hex_a, hex_b)
mx.mix_pigments([(pigment, proporcion), ...])
```

## API de `database/db_manager.py`

```python
from database.db_manager import DBManager

db = DBManager()
pid, nombre = db.get_or_create_default_palette()

db.list_palettes()
db.create_palette("Paleta viaje")
db.rename_palette(pid, "Nuevo nombre")
db.delete_palette(pid)                 # CASCADE: borra también sus pigmentos

db.get_pigment_ids(pid)                # -> set de pigment_id (str)
db.get_pigments(pid)                   # -> lista de dicts completos (nombre, marca, tipo, hex, opacidad...)
db.add_pigment(pid, pigment_id, marca, tipo, nombre, hex_color, opacidad)
db.remove_pigment(pid, pigment_id)
db.set_pigments(pid, [dict, ...])      # reemplaza toda la paleta de golpe
```

## API de `utils/history.py`

```python
from utils.history import HistoryManager

h = HistoryManager()
h.log_color("#3B82F6", tipo="master")
h.log_mix("#7A5C3E", "#7B583B", 2.77, [{"nombre":.., "marca":.., "porcentaje":..}])

h.get_color_history(limit=50, tipo="master")   # limit=None -> todo, sin límite
h.get_mix_history(limit=50)                    # limit=None -> todo, sin límite
h.clear_color_history()
h.clear_mix_history()
h.clear_all()                                   # ambos a la vez
h.export_to_file("historial.json")              # todo el historial, sin límite
h.import_from_file("historial.json")            # SUMA al historial actual (no reemplaza)
```

## Cómo probarlo en tu máquina

```powershell
pip install -r requirements.txt
python main.py
```

En el panel derecho: elige un fabricante+tipo del desplegable "Explorar catálogo" y pulsa "Cargar" — verás sus colores con checkbox. Márcalos para añadirlos a "Mi paleta". Cambia a otro fabricante y sigue añadiendo. La sección "Mi paleta" de abajo siempre muestra todo lo añadido, venga de donde venga. "Calcular mezcla óptima" usa toda esa paleta.

Si algo falla, pásame el traceback completo.

## Decisiones de diseño acordadas (resumen para no perder contexto)

- **Layout**: panel izquierdo (selector master/master2 + historial), panel central (gradientes), panel derecho (explorador de catálogo + mi paleta + mezclas).
- **Selector de color**: tipo Photoshop, swatch clicable, hex/RGB/CMYK, traducido al español vía `qtbase_es.qm`.
- **Gradientes**: brillo (HSV V), saturación (HSV S), tono (rotación 360°), luminosidad (HSL L), y transición master→master2. Nº de colores por gradiente configurable (3-27, por defecto 10).
- **Mezclas**: pseudo-Kubelka-Munk por canal RGB ponderado por opacidad (no hay reflectancia espectral real disponible). Hasta 4 pigmentos, ΔE < 3 = buena coincidencia.
- **Base de datos de pigmentos**: índice ligero + un Excel por fabricante+tipo, carga perezosa. Columna de fiabilidad (1-5) según la fuente.
- **Paleta de usuario**: SQLite, autocontenida, múltiples paletas con nombre, pigmentos añadidos desde cualquier fabricante explorado.
- **Historial**: colores seleccionados y mezclas calculadas, en SQLite.
- **Estilo UI**: claro/oscuro con acentos pastel — pendiente.
- **Entorno**: Python 3.10.6, PySide6 6.11.2, Windows 11.

## API de `utils/exporters.py`

```python
from utils.exporters import export_report

export_report(
    "informe.pdf",
    master_hex="#3B82F6",
    master2_hex="#F59E0B",
    gradients={"Brillo": [...], "Saturación": [...], ...},  # nombre -> lista de hex
    palette_name="Mi paleta",
    palette_pigments=db.get_pigments(pid),   # tal cual, misma forma
    mix_result={"target_hex":.., "resulting_hex":.., "delta_e":.., "componentes":[...]},
    recent_colors=history.get_color_history(limit=20),
    recent_mixes=history.get_mix_history(limit=20),
)
```
Todos los parámetros excepto `master_hex` son opcionales — cada sección del PDF se omite si no se pasa el dato correspondiente.


