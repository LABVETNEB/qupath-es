# Arquitectura

Documento técnico. Explica cómo funciona la localización por dentro, por qué
está construida así, y qué invariantes no deben romperse.

Público: desarrolladores y mantenedores. Para instalar, ver
[`INSTALLATION.md`](INSTALLATION.md).

---

## 1. Cómo carga QuPath una traducción externa

QuPath resuelve el texto de su interfaz a través de un `ResourceBundle` de Java
—un fichero `.properties` con pares `clave = valor`—. El bundle principal es:

```
qupath/lib/gui/localization/qupath-gui-strings.properties
```

y viaja dentro de `qupath-gui-fx-<versión>.jar`.

La clase `QuPathResources` instala un `ResourceBundle.Control` propio que amplía
la búsqueda estándar. Al pedir un bundle intenta, **en este orden**:

1. el *classpath* (dentro del JAR);
2. el *classpath* con el cargador de clases de QuPath (para extensiones);
3. **el sistema de archivos**, en dos directorios de localización.

El tercer paso es el que aprovecha este proyecto. Los directorios son:

| Prioridad | Ruta |
| --- | --- |
| 1 | `<directorio de usuario de QuPath>/localization` |
| 2 | `<directorio de los JAR>/localization` |

El fichero se lee explícitamente como **UTF-8**, así que los acentos y la `ñ` se
escriben directamente.

### Consecuencia importante

Como el *classpath* se consulta **primero**, un fichero externo **no puede
sobrescribir** un idioma que ya venga dentro del JAR. Sí puede **añadir** uno
que no exista. El español no existe, así que basta con colocar:

```
qupath-gui-strings_es.properties
```

en `<directorio de usuario>/localization`. Sin registro, sin manifiesto, sin
recompilar.

### Respaldo automático al inglés

La JVM asigna al bundle español el bundle raíz (inglés) como *padre*. Una clave
que falte en el español se resuelve en inglés, sin error. Eso hace viable una
traducción incremental.

**Excepción:** una clave presente pero con **valor vacío** no cae al inglés:
devuelve cadena vacía y el control aparece en blanco. Por eso el validador trata
los valores vacíos como error bloqueante.

---

## 2. Las tres configuraciones regionales

QuPath expone tres ajustes independientes:

| Preferencia | Categoría Java | Qué controla |
| --- | --- | --- |
| Idioma principal | ninguna → afecta a las dos | Todo |
| Interfaz de usuario | `Locale.Category.DISPLAY` | **El idioma de los textos** |
| Fechas y números | `Locale.Category.FORMAT` | Separador decimal, fechas |

Este proyecto cambia **solo `DISPLAY`**. `FORMAT` y el idioma principal se
quedan en `en_US`.

La razón es de seguridad de datos: en castellano de España el separador decimal
es la coma, lo que cambiaría cómo se muestran y exportan las mediciones. La
resolución del bundle usa `Locale.getDefault(Category.DISPLAY)`, así que traducir
la interfaz no exige tocar el formato.

---

## 3. El defecto de QuPath 0.7.0 en Windows

Dos problemas independientes impiden que QuPath 0.7.0 recuerde el español.

### 3.1 El runtime no conoce el español

El instalador de Windows incluye una imagen `jlink` de Java 25 con 24 módulos.
**`jdk.localedata` no está entre ellos.** Sin ese módulo, `java.base` solo aporta
la locale raíz e inglés:

```
availableLocales.total  = 5   (root, en, en_US, en_US_#Latn, en_US_POSIX)
availableLocales.spanish= 0
```

### 3.2 La preferencia no se puede guardar

El conversor de preferencias de QuPath serializa una `Locale` a su **nombre de
visualización** en inglés y la reconstruye buscando ese nombre entre las locales
disponibles:

| Operación | Resultado |
| --- | --- |
| `toString(es)` | `Spanish` |
| `fromString("Spanish")` | `null` |
| ida y vuelta `en_US` | correcta |
| ida y vuelta `es`, `es_ES`, `es_AR` | **falla** |

Como no hay ninguna locale española disponible, ninguna cadena puede almacenar
el español. Al reiniciar, la preferencia se lee como `null`.

### 3.3 Por qué no sirve fijarlo al arrancar la JVM

`PathPrefs`, al inicializarse, ejecuta `Locale.setDefault(Locale.US)`, que
reinicia **ambas** categorías. Cualquier locale fijado antes se descarta. Se
comprobó empíricamente: en una máquina cuyo sistema está en `es_AR`, la JVM
reporta `en_US` en cuanto `PathPrefs` se carga.

Por eso no funcionan `-Duser.language.display=es`, `JAVA_TOOL_OPTIONS`, las
opciones del lanzador jpackage ni el parámetro `-D` de la línea de comandos de
QuPath: la propiedad llega, pero se descarta.

### 3.4 La solución: script de arranque

QuPath ejecuta opcionalmente un script Groovy al iniciar. El de este proyecto
asigna únicamente `DISPLAY`:

```groovy
PathPrefs.defaultLocaleDisplayProperty().set(Locale.forLanguageTag('es'))
```

`Locale.forLanguageTag("es")` funciona aunque la locale no sea enumerable,
porque construye el objeto a partir de la etiqueta de idioma sin necesitar datos
CLDR. Y la resolución del bundle también funciona, porque deriva el nombre del
fichero de la etiqueta de idioma.

El script es **idempotente**: si `DISPLAY` ya es español, no hace nada. Así
seguirá siendo seguro cuando una versión futura resuelva el problema por sí
misma.

### 3.5 Coste: el momento en que se aplica

El script se ejecuta al final de la construcción de la interfaz. Los textos
enlazados de forma reactiva se actualizan; los que se resuelven una sola vez
durante el arranque no.

Medición sobre las 894 claves de 0.7.0:

| Clasificación | Claves |
| --- | --- |
| Reactivas (se actualizan al cambiar el idioma) | 368 |
| No rastreables estáticamente | 348 |
| Resueltas una sola vez | 123 |
| Mixtas | 55 |

De las 31 clases que solo hacen resolución estática, únicamente cuatro se
construyen durante el arranque: la barra de herramientas, los nombres de las
herramientas de dibujo, el texto de marcador del visor y los mensajes de inicio.
El coste visible real es, por tanto, unos pocos *tooltips*.

Informe completo: `versions/0.7.0/reports/locale-timing-audit.md`.

---

## 4. El pipeline de traducción

La regla central: **el fichero `.properties` es un artefacto generado; nunca se
edita a mano.**

```
base/qupath-gui-strings.properties   (inglés canónico, INMUTABLE)
                │
                ├──> work/translation.tsv      (fuente de verdad, por clave)
                │        │
                │        │  tools/es_translations.py  (tabla lingüística)
                │        ▼
                │    tools/apply_translations.py
                │        │
                ▼        ▼
        tools/translation_generator.py
                │
                ▼
      dist/qupath-gui-strings_es.properties
                │
                ├──> tools/translation_validator.py   (estructura)
                └──> tools/linguistic_audit.py        (lengua y calidad)
```

### El TSV como fuente de verdad

`versions/<v>/work/translation.tsv` tiene una fila por clave:

| Columna | Contenido |
| --- | --- |
| `key` | Clave, inmutable |
| `en` | Valor inglés original |
| `es` | Traducción |
| `state` | Estado del ciclo de vida |
| `batch` | Lote de trabajo |
| `reviewer` | Quién revisó |
| `rev_date` | Fecha de revisión |
| `qupath_ver` | Versión de QuPath |
| `issues` | Incidencias abiertas |
| `notes` | Notas |

Esto da trazabilidad por clave sin ensuciar el fichero instalado.

### Estados

| Estado | Significado | ¿Permite release? |
| --- | --- | --- |
| `PENDING` | Sin traducir | No |
| `DRAFT` | Traducido, sin revisar | No |
| `REVIEWED` | Revisado lingüísticamente | Sí |
| `VERIFIED_UI` | Comprobado dentro de QuPath | Sí |
| `KEEP_EN` | Deliberadamente idéntico al inglés | Sí |
| `BLOCKED` | Requiere una decisión | No |

`KEEP_EN` existe para que la comprobación «idéntico al inglés» siga siendo útil:
sin él, términos como `TMA` o `Bio-Formats` la harían ruidosa para siempre.

### El generador preserva la estructura

`translation_generator.py` transforma el fichero base **línea a línea**,
sustituyendo solo los valores. Conserva comentarios, orden y claves. Detecta
además la *deriva* del inglés: si el `en` del TSV no coincide con el bundle base,
aborta.

Prueba de identidad: con todos los valores en inglés, el generador debe
reproducir el bundle base **byte a byte**.

---

## 5. Validación

Dos capas, ambas obligatorias antes de instalar.

### Validador estructural (`translation_validator.py`)

Protege el contrato con el runtime:

| Comprobación | Severidad |
| --- | --- |
| Fingerprint del base | Error |
| Codificación UTF-8, sin BOM | Error |
| Claves duplicadas | Error |
| Valores vacíos | Error |
| Marcadores `{n}` de `MessageFormat` | Error |
| Marcadores de `java.util.Formatter` | Error |
| Apóstrofos sin duplicar junto a `{n}` | Error |
| Equilibrio de llaves, saltos de línea, tabuladores | Error |
| Carácter de reemplazo U+FFFD, caracteres de control | Error |
| Claves faltantes o sobrantes | Aviso |

#### Sobre los marcadores

- **`MessageFormat`** (`{0}`, `{0,number}`): se comparan como **multiconjunto**.
  Reordenarlos es seguro, porque el índice es explícito.
- **`java.util.Formatter`** (`%s`, `%d`, `%n`, `%%`): se comparan como
  **secuencia ordenada**, porque son posicionales salvo que lleven índice
  (`%1$s`).

El tokenizador de `Formatter` excluye deliberadamente el *flag* espacio. Es
sintaxis válida de Java, pero en textos de interfaz un `%` seguido de espacio es
casi siempre un porcentaje literal (`400% (downsample = 0.25)`). Incluirlo
producía nueve falsos positivos en el bundle de 0.7.0.

- **Apóstrofos**: en `MessageFormat` un `'` abre una zona literal. Un apóstrofo
  sin duplicar puede anular un marcador. El validador analiza el entrecomillado
  real y marca como error solo la pérdida efectiva de un marcador.

### Auditoría lingüística (`linguistic_audit.py`)

Busca lo que la estructura no ve: acrónimos perdidos, deriva del glosario, inglés
residual, puntuación española (`¿`, `¡`), truncamientos, *mojibake*, estados sin
revisar. Emite `SAFE TO INSTALL` o `DO NOT INSTALL`.

---

## 6. Migración entre versiones

`tools/qupath_version_migrator.py` adapta la traducción a una versión nueva.

### Política

Una traducción se reutiliza automáticamente **solo** si coinciden las tres cosas:
el texto inglés, la firma de marcadores y la firma estructural.

| Situación | Estado | ¿Se reutiliza? |
| --- | --- | --- |
| Inglés idéntico | `REVIEWED` | Sí |
| `KEEP_EN`, inglés idéntico | `KEEP_EN` | Sí |
| Inglés cambiado | `DRAFT` + `SOURCE_CHANGED` | Solo como referencia |
| `KEEP_EN`, inglés cambiado | `DRAFT` + `KEEP_EN_NEEDS_REVIEW` | Solo como referencia |
| Firma de marcadores cambiada | `BLOCKED` + `PLACEHOLDER_SIGNATURE_CHANGED` | No |
| Estructura cambiada | `BLOCKED` + `STRUCTURE_CHANGED` | No |
| Clave nueva | `PENDING` | No |
| Clave eliminada | archivada en `work/retired.tsv` | No se añade |

Cuando una versión nueva externaliza un texto que antes estaba en el código, el
migrador adjunta la traducción conocida como **sugerencia**, pero la entrada
sigue en `PENDING`. Una sugerencia no es una aprobación.

### Captura del bundle canónico

Siempre desde el JAR **instalado**, nunca de Internet, byte a byte, con
`fingerprint.json`. Los ficheros de `base/` son **inmutables**: el migrador se
niega a sobrescribirlos sin `--force`.

---

## 7. Detección de la versión instalada

Tres fuentes independientes:

1. `Implementation-Version` del `META-INF/MANIFEST.MF` — **autoritativa**;
2. el nombre del JAR;
3. el nombre del directorio — solo como contraste.

Si discrepan, se informa en vez de elegir. Si hay varias instalaciones, el
actualizador **no elige**: exige `-Version` o `-QuPathPath`.

---

## 8. Invariantes

Romper cualquiera de estos es un fallo:

1. `versions/*/base/*` es inmutable. Su SHA-256 está en `fingerprint.json` y hay
   una prueba que lo vigila.
2. Las claves nunca se traducen ni se reordenan. Solo los valores.
3. Los marcadores se preservan exactamente.
4. `FORMAT` y el idioma principal permanecen en `en_US`.
5. Nunca se modifica QuPath: ni JAR, ni código, ni ejecutable, ni runtime.
6. Nada se instala sin pasar el validador y la auditoría lingüística.
7. Nunca se cierra un proceso ni se toca configuración global de la máquina.
8. El `.properties` se genera; jamás se edita a mano.

---

## 9. Un detalle de Git que importa

Los bundles se almacenan con `-text` en `.gitattributes`, es decir **byte a
byte**. Es imprescindible: los SHA-256 documentados se calculan sobre esos bytes
y el fichero se instala tal cual. Si Git normalizara los finales de línea, un
clon nuevo produciría un hash distinto y la comprobación de *fingerprint*
fallaría.

`tests/test_repository_integrity.py` lo vigila.
