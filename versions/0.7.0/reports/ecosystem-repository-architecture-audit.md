# Auditoría de arquitectura de repositorio para el ecosistema

Auditoría **de solo lectura** del estado real de `qupath-es` y diseño de la
arquitectura con la que debe evolucionar hacia una infraestructura de
localización de QuPath **y de su ecosistema de extensiones**, mantenible durante
5-10 años.

> **Esta auditoría no implementa nada.** Los dos únicos ficheros escritos son
> este informe y su compañero
> [`ecosystem-repository-architecture-audit.json`](ecosystem-repository-architecture-audit.json).
> No se ha creado `components/`, ni registro, ni lockfile, ni fork, ni parche,
> ni submódulo; no se ha tocado el runtime, ni CI, ni las traducciones, ni los
> tests existentes.

**Idioma:** este informe está en castellano, como `README.md`, `CONTRIBUTING.md`
y `docs/`, porque es un documento de decisión para personas. Los demás ficheros
de `reports/` están en inglés porque son salidas de herramientas de medición.

## Cómo leer la evidencia

| Grado | Significado |
| --- | --- |
| **FACT** | Medido en esta sesión sobre binarios instalados, el árbol de fuentes local o la API de GitHub. |
| **OBSERVED** | Leído en fuentes o documentación upstream, sin ejecución propia. |
| **INFERRED** | Deducido de hechos verificados; no observado directamente. |
| **RECOMMENDED** | Decisión de diseño propuesta por esta auditoría. |
| **UNKNOWN** | No verificable con los medios de esta sesión. Se declara, no se rellena. |

---

## 1. Identificación de la auditoría

| Campo | Valor |
| --- | --- |
| **Fecha** | 2026-09-02 (hora local de la máquina auditora) |
| **Repositorio** | <https://github.com/LABVETNEB/qupath-es> |
| **Ruta local** | `C:\qupath-es` |
| **Rama** | `main` (sincronizada con `origin/main`) |
| **HEAD auditado** | `120eb53b1c48571cdb828fbb985ed260c728b163` |
| **Último commit** | `120eb53 docs: align the protection table with the admin-bypass note` |
| **Working tree** | **Limpio** — `git status --porcelain` sin salida |
| **Versión de QuPath objetivo** | 0.7.0 |
| **Build de QuPath** | 2026-02-25 16:06 |
| **Commit upstream de QuPath** | `04ccfa4` |
| **Python** | 3.14.5 |
| **Tests (baseline)** | **147 / 147 OK** |

### Artefactos congelados verificados

| Fichero | SHA-256 medido | Esperado | |
| --- | --- | --- | --- |
| `versions/0.7.0/base/qupath-gui-strings.properties` | `796EFC44…D45D2D` | `796EFC44…D45D2D` | ✅ |
| `versions/0.7.0/dist/qupath-gui-strings_es.properties` | `E4A966C9…C4128FC19` | `E4A966C9…C4128FC19` | ✅ |
| `versions/0.7.0/work/translation.tsv` | `D28002B4…88C7849C` | (no especificado en el encargo; registrado aquí como línea base) | — |

Estado del bundle principal: **894 / 894 claves**, `REVIEWED` 884, `KEEP_EN` 10,
`PENDING` 0, `DRAFT` 0, `BLOCKED` 0.

---

## 2. Estructura actual del repositorio (FACT)

71 ficheros versionados. `.git` ocupa 809 KB; el árbol de trabajo, 1,5 MB.

```
qupath-es/
├─ README.md  CONTRIBUTING.md  SECURITY.md  NOTICE.md  LICENSE
├─ .gitattributes  .gitignore
├─ .github/           workflows/ci.yml, CODEOWNERS, plantillas
├─ docs/              10 guías en castellano (ARCHITECTURE, INSTALLATION, …)
├─ tools/             9 módulos Python, solo biblioteca estándar
├─ tests/             7 ficheros, 147 tests
├─ runtime/           update-qupath-es.ps1, probe-locale-capability.groovy
└─ versions/
   ├─ supported-versions.json
   └─ 0.7.0/
      ├─ base/        bundle canónico inglés  (INMUTABLE)
      ├─ dist/        bundle español generado (INSTALABLE)
      ├─ work/        translation.tsv         (FUENTE DE VERDAD)
      ├─ runtime/     scripts Groovy de arranque y sondas
      ├─ reports/     15 informes .md/.json/.txt
      ├─ fingerprint.json
      └─ target-version.json
```

**Forma:** un único eje, el de la versión de QuPath. **No existe eje de
componente.** El repositorio está diseñado, con mucha precisión, para localizar
*un* bundle de *una* aplicación.

### 2.1 Fortalezas que hay que preservar (FACT)

1. **Fuente de verdad por clave.** `work/translation.tsv` tiene una fila por
   clave con estado, lote, revisor y fecha. La trazabilidad es por clave, no por
   fichero.
2. **El artefacto instalado es generado, nunca editado.** El generador
   transforma el bundle base línea a línea y hay una *prueba de identidad*: con
   todos los valores en inglés debe reproducir el base **byte a byte**.
3. **Inmutabilidad verificada, no prometida.** `fingerprint.json` guarda los
   SHA-256 y hay un job de CI y un test que los comprueban.
4. **Política de locale explícita y justificada.** Solo se cambia `DISPLAY`;
   `FORMAT` se queda en `en_US` para no alterar separadores decimales. Es una
   decisión de seguridad de datos, y está documentada.
5. **Migrador entre versiones con política conservadora.** Una traducción se
   reutiliza solo si coinciden texto inglés, firma de marcadores y firma
   estructural. Una sugerencia no es una aprobación.
6. **Validación en dos capas** antes de instalar: estructural y lingüística.
7. **Cero dependencias de terceros** en el utillaje.
8. **`.gitattributes` protege los bytes** con `-text` en `base/` y `dist/`.
9. **Los invariantes son ejecutables**: 147 tests en verde.

Esta base es de calidad poco común. La arquitectura propuesta **no la sustituye:
la extiende por un eje que hoy no existe.**

### 2.2 Limitaciones frente al objetivo (FACT)

1. No hay dónde registrar 12 extensiones, su compatibilidad ni su procedencia.
2. El TSV y el generador están acoplados a **un** bundle (el principal de la GUI).
3. No hay metadatos de licencia, artefacto ni hash por componente de terceros.
4. No hay detección de cambios upstream fuera del bundle del Core.
5. CI son dos jobs monolíticos: sin filtros de ruta, sin matriz.
6. `supported-versions.json` registra versiones de QuPath, no componentes.
7. La distinción `SOURCE_OF_TRUTH` / `GENERATED` / `UPSTREAM_REFERENCE` está
   implícita en la costumbre y explícita solo para `base/`.

---

## 3. Corpus externo auditado (FACT)

13 componentes, auditados en su rama por defecto en la fecha de esta auditoría.

| # | id | Repositorio | Pri | Licencia | Release | Commit auditado | API QuPath declarada |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `dl-pixel-classifier` | uw-loci/qupath-extension-dl-pixel-classifier | P0 | Apache-2.0 | v0.8.5 | `cbf9bdeec4` | 0.7.0 |
| 2 | `tiatoolbox` | TissueImageAnalytics/tiatoolbox-qupath-extension | P0 | BSD-3-Clause | **ninguna** | `cb942b774c` | 0.6.0 |
| 3 | `instanseg` | qupath/qupath-extension-instanseg | P0 | Apache-2.0 | v0.1.7 | `90b260157f` | 0.6.0 |
| 4 | `cell-analysis-tools` | uw-loci/qupath-extension-cell-analysis-tools | P0 | Apache-2.0 | v0.11.2 | `fe05c0c9e8` | 0.7.0 |
| 5 | `training` | qupath/qupath-extension-training | P0 | Apache-2.0 | v0.1.1 | `bdd19fbcff` | 0.6.0 |
| 6 | `stardist` | qupath/qupath-extension-stardist | P0 | Apache-2.0 | v0.6.0 | `11b50db1d6` | 0.6.0 |
| 7 | `cellpose` | BIOP/qupath-extension-cellpose | P0/P1 | Apache-2.0 | v0.12.1 | `5d1481674b` | 0.7.0 |
| 8 | `wsinfer` | qupath/qupath-extension-wsinfer | P1 | Apache-2.0 | v0.4.0 | `13fe2dc337` | 0.6.0 |
| 9 | `djl` | qupath/qupath-extension-djl | P1 | Apache-2.0 | v0.4.3 | `58b6c022ca` | 0.6.0 |
| 10 | `bioimageio` | qupath/qupath-extension-bioimageio | P1 | Apache-2.0 | v0.2.0 | `5e6c1069ac` | 0.8.0-SNAPSHOT |
| 11 | `sam` | ksugar/qupath-extension-sam | P1 | GPL-3.0 | v0.9.1 | `cf328efbbb` | 0.6.0 |
| 12 | `image-export-toolkit` | uw-loci/qupath-extension-image-export-toolkit | P1 | Apache-2.0 | v1.2.8 | `35bdbf516b` | 0.7.0 |
| 13 | `qupath-core` | qupath/qupath | BASE | GPL-3.0 | v0.7.0 | `67cbf61999` | 0.7.0 (congelado) |

> El commit auditado de `qupath-core` corresponde a su rama por defecto, que es
> **0.8.0-SNAPSHOT**. El objetivo congelado de este repositorio sigue siendo
> 0.7.0 / `04ccfa4`. Los dos números se registran por separado en el JSON.

### 3.1 Superficie de localización por componente (FACT)

| id | Bundle(s) | Claves | Mecanismo de resolución | ParameterList | PathClass | Ficheros Java / Groovy / Python |
| --- | --- | ---: | --- | ---: | ---: | --- |
| `dl-pixel-classifier` | `qupath/ext/dlclassifier/ui/strings` | 66 | `ResourceBundle.getBundle(String)` | 0 | 14 | 91 / 6 / 48 |
| `tiatoolbox` | `qupath/ext/tiatoolbox/ui/strings` | 106 | `ResourceBundle.getBundle(String)` | 0 | 4 | 24 / 3 / 5 |
| `instanseg` | `qupath/ext/instanseg/ui/strings` | 97 | `ResourceBundle.getBundle(String)` | 0 | 1 | 22 / 0 / 0 |
| `cell-analysis-tools` | `qupath/ext/qpcat/ui/strings` | 32 | `ResourceBundle.getBundle(String)` | 0 | 30 | 162 / 1 / 35 |
| `training` | `…/training/ui/strings` + `…/training/ui/tour` | 2 + 94 | `ResourceBundle.getBundle(String)` | 0 | 0 | 14 / 0 / 0 |
| `stardist` | **ninguno** | 0 | — | 0 | 1 | 4 / 4 / 0 |
| `cellpose` | **ninguno** | 0 | — | 0 | 7 | 6 / 4 / 1 |
| `wsinfer` | `qupath/ext/wsinfer/ui/strings` | 65 | `ResourceBundle.getBundle(String)` | 0 | 1 | 19 / 0 / 0 |
| `djl` | `qupath/ext/djl/ui/strings` | 46 | `ResourceBundle.getBundle(String)` | 0 | 1 | 7 / 0 / 0 |
| `bioimageio` | `qupath/ext/bioimageio/strings` | 29 | `ResourceBundle.getBundle(String)` | 0 | 2 | 4 / 0 / 0 |
| `sam` | **ninguno** | 0 | — | 0 | 8 | 32 / 2 / 0 |
| `image-export-toolkit` | `qupath/ext/quiet/ui/strings` | **611** | `ResourceBundle.getBundle(String)` | 0 | 0 | 77 / 0 / 0 |
| `qupath-core` | `qupath/lib/gui/localization/qupath-gui-strings` | **894** (0.7.0) | **`QuPathResourceControl`** | 76 ficheros | — | 1030 / 4 / 0 |

**Total de claves de bundle en las 12 extensiones: 1148.** Más de la mitad
(611) pertenecen a una sola extensión, `image-export-toolkit`.

### 3.2 Convención uniforme (FACT)

Las 12 extensiones comparten exactamente la misma forma:

- Gradle **Kotlin DSL**;
- plugin `io.github.qupath.qupath-extension-settings:0.2.1`;
- bloque `qupath { version = "…" }` en `settings.gradle.kts` (así se declara la
  API contra la que compilan: 0.6.0 en siete, 0.7.0 en cuatro, 0.8.0-SNAPSHOT en
  una);
- punto de entrada declarado en
  `META-INF/services/qupath.lib.gui.extensions.QuPathExtension`.

Esto es una **muy buena noticia para la escalabilidad**: un solo procedimiento
de auditoría, de compilación y de fork sirve para todo el corpus, hoy y con 100
extensiones.

---

## 4. Los cinco hallazgos que determinan la arquitectura

Estos hallazgos son el motivo de que la arquitectura recomendada sea la que es.
Sin ellos, cualquier diseño sería una preferencia estética.

### F1 — El directorio externo de localización es un espacio de nombres **plano** (FACT)

`QuPathResources.QuPathResourceControl.getShortPropertyFileName()` construye el
nombre del bundle y **descarta el paquete**, quedándose solo con el último
segmento:

```java
String bundleName = toBundleName(baseName, locale);        // qupath.ext.djl.ui.strings_es
int ind = bundleName.replace('.', '/').lastIndexOf('/');
String propertiesBaseName = bundleName.substring(ind + 1); // strings_es
return propertiesBaseName + ".properties";                 // strings_es.properties
```

Verificado en el código de 0.8.0-SNAPSHOT y confirmado en 0.7.0 por la presencia
de los mismos métodos (`getShortPropertyFileName`, `searchForBundlePath`,
`toBundleName`) en `qupath-gui-fx-0.7.0.jar`, y empíricamente por el fichero
plano que este proyecto ya instala en `<usuario>/QuPath/localization/`.

**Consecuencia:** **11 bundles del corpus se llaman `strings`** y colapsan todos
en el mismo fichero externo `strings_es.properties`. Dentro de la propia
instalación de 0.7.0 ya colisionan ocho más (`djl`, `openslide`,
`imagej/gui/scripts`, `training`, `fxtras`, `extensionmanager`, `logviewer`,
`javadocviewer`).

> **Como máximo una extensión puede servirse externamente. Nunca doce.**
> No es un problema de diseño de `qupath-es`: es una limitación estructural de
> QuPath, y ninguna organización de directorios en nuestro repositorio puede
> resolverla.

### F2 — Ninguna extensión del corpus es localizable externamente (FACT)

Las 10 extensiones que tienen bundle lo resuelven con la forma de **un solo
argumento**:

```java
private static final ResourceBundle resources =
        ResourceBundle.getBundle("qupath.ext.instanseg.ui.strings");
```

Ninguna aporta un `ResourceBundle.Control` de QuPath, y ninguna solicita
`Locale.Category.DISPLAY`. Esto tiene **dos** consecuencias independientes:

1. **El directorio externo nunca se consulta para ellas.** Solo el `Control` de
   QuPath busca en el sistema de archivos; sin él, la búsqueda termina en el
   classpath.
2. **Ni siquiera un bundle `_es` dentro del JAR sería seleccionado.** La forma de
   un argumento resuelve contra la locale por defecto, que bajo la política de
   este proyecto es `en_US` (solo se cambia `DISPLAY`). Sea `Locale.getDefault()`
   o `getDefault(Category.FORMAT)` —extremo que no se ha podido verificar por
   ejecución, ver U2— **ambas valen `en_US`**, así que la conclusión no depende
   de ese detalle.

> **Localizar cualquiera de estas 12 extensiones exige un cambio de código.**
> No basta con traducir un fichero. Este es el hecho más importante de toda la
> auditoría, y contradice la hipótesis natural de partida.

El único uso de la API de QuPath encontrado en el corpus es
`QuPathResources.getLocalizedResourceManager()` en `LaunchScriptCommand` de DJL,
y resuelve contra el bundle **principal**, no contra el suyo.

### F3 — Tres extensiones no tienen ningún ResourceBundle (FACT)

`stardist`, `cellpose` y `sam` no incluyen ningún `.properties` de interfaz. Su
texto visible está íntegramente en el código. Requieren **externalización previa**
antes de que exista siquiera algo que traducir.

### F4 — `ParameterList` es un problema del Core, no de las extensiones (FACT)

| Ámbito | Ficheros con `ParameterList` | Llamadas `add*Parameter` | Con consulta de recursos |
| --- | ---: | ---: | ---: |
| Las 12 extensiones | **0** | — | — |
| QuPath 0.8.0-SNAPSHOT | 76 | 455 | **9** |

Aproximadamente el **98 %** de las etiquetas y textos de ayuda de `ParameterList`
siguen *hardcoded* incluso en la rama de desarrollo 0.8. Las extensiones modernas
construyen su interfaz con JavaFX/FXML y no usan `ParameterList` en absoluto.

Esto **reordena las prioridades** respecto de la hipótesis de partida: el
esfuerzo en `ParameterList` corresponde a un PR upstream al Core, no a trabajo
por extensión.

Y hay una buena noticia dentro: la firma separa clave y etiqueta,

```java
params.addDoubleParameter("thresholdPositive1", "Threshold 1+", t1, null, 0, tMax,
                          "Low positive intensity threshold");
//                         ^clave (NUNCA)      ^etiqueta       ...  ^texto de ayuda
```

de modo que un PR upstream puede externalizar etiqueta y ayuda **sin tocar la
clave**, que es exactamente el invariante que hay que proteger.

### F5 — QuPath 0.7.0 ya incluye un gestor de extensiones con catálogos (FACT)

`extensionmanager-1.1.1.jar` define un esquema formal, y QuPath consume un
catálogo oficial en
`https://raw.githubusercontent.com/qupath/qupath-catalog/refs/heads/main/catalog.json`.

| Modelo | Campos |
| --- | --- |
| `Catalog` | `name`, `description`, `extensions[]` |
| `Extension` | `name`, `description`, `author`, `homepage`, `starred`, `releases[]` |
| `Release` | `name`, `mainUrl`, `requiredDependencyUrls[]`, `optionalDependencyUrls[]`, `javadocUrls[]`, `versionRange` |
| `VersionRange` | `min`, `max`, `excludes[]` |

Estado local en `<usuario>/QuPath/extensions/catalogs/registry.json`.
**Restricción dura:** los `mainUrl` solo pueden apuntar a `github.com` o
`maven.scijava.org`, y solo por `https`.

**Consecuencia:** existe un canal de distribución sancionado upstream. Nuestro
registro no debe competir con él, sino **poder proyectarse a él**.

### F6 — QuPath 0.8 casi triplica el bundle principal (FACT)

**894** claves en 0.7.0 frente a **2610** en la rama por defecto
(0.8.0-SNAPSHOT). La migración traerá del orden de **1716 claves nuevas**. Es,
con diferencia, el mayor consumo de esfuerzo previsible del proyecto, y debe
planificarse como una versión propia, no simultanearse con las primeras
extensiones.

### F7 — Dos componentes del corpus ya viajan dentro de QuPath 0.7.0 (FACT)

`qupath-extension-djl` **0.4.2** y `qupath-extension-training` **0.1.0** están en
la instalación (frente a 0.4.3 y 0.1.1 upstream). No son extensiones que el
usuario instale: son parte de la distribución, con versión fijada por QuPath. Su
política de versión es la del Core, no la suya propia. La arquitectura debe
poder expresar esa diferencia.

---

## 5. Requisitos que la arquitectura debe cumplir

| # | Requisito |
| --- | --- |
| R01 | Los artefactos congelados de 0.7.0 no cambian ni de bytes ni de ruta. |
| R02 | El eje de versión de QuPath y el eje de componente son independientes. |
| R03 | Ningún código fuente upstream se copia al repositorio. |
| R04 | Todo componente es reproducible desde repo + tag + commit + hash de artefacto. |
| R05 | La traducción es independiente del sistema de construcción del componente. |
| R06 | Los identificadores funcionales están protegidos por tests, no por convención. |
| R07 | Auditar una actualización upstream cuesta en proporción al diff. |
| R08 | CI ejecuta solo lo afectado por un cambio. |
| R09 | La licencia y la procedencia son consultables por máquina. |
| R10 | `AUDITED` / `TRANSLATED` / `VALIDATED` / `DISTRIBUTED` son independientes. |
| R11 | Ningún fichero generado puede confundirse con una fuente canónica. |
| R12 | Los directorios crecen O(componentes + versiones), no O(componentes × versiones). |
| R13 | La arquitectura puede proyectarse al esquema de catálogo del Extension Manager. |
| R14 | Un tercero responde «qué hay soportado» sin leer código. |
| R15 | Ningún directorio ceremonial ni vacío. |

---

## 6. Alternativas evaluadas

No se dio ninguna por buena de antemano. Se compararon diez.

| id | Alternativa | Veredicto |
| --- | --- | --- |
| A1 | Statu quo ampliado (solo `versions/`) | Rechazada: no cubre el objetivo |
| A2 | Directorio plano `extensions/<id>/` en la raíz | Rechazada: pierde el eje de versión |
| A3 | Version-major: `versions/<v>/extensions/<id>/` | Rechazada: duplicación estructural |
| **A4** | **Component-major + lockfile por versión** | **RECOMENDADA** |
| A5 | Git submodules por upstream | Descartada |
| A6 | Git subtree por upstream | Descartada |
| A7 | Vendorizar el código fuente | Descartada salvo excepción justificada |
| A8 | Monorepo con los forks dentro de `qupath-es` | Descartada |
| **A9** | **Repositorios satélite para forks + referencia por metadatos** | **RECOMENDADA como complemento** |
| A10 | Solo registro, sin directorios por componente | Descartada como arquitectura; adoptada como capa |

### 6.1 Matriz comparativa

Escala 1 (malo) a 5 (bueno). Los criterios son los 17 del encargo, agrupados
donde miden lo mismo.

| Criterio | A1 | A2 | A3 | **A4** | A5 | A6 | A7 | A8 | **A9** | A10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mantenibilidad | 1 | 3 | 2 | **5** | 2 | 2 | 1 | 1 | **4** | 2 |
| Actualización desde upstream | 1 | 2 | 2 | **5** | 3 | 2 | 1 | 2 | **4** | 2 |
| Trazabilidad | 2 | 3 | 4 | **5** | 4 | 4 | 2 | 3 | **5** | 3 |
| Reproducibilidad | 2 | 3 | 4 | **5** | 5 | 4 | 2 | 3 | **5** | 2 |
| Aislamiento entre extensiones | 1 | 4 | 4 | **5** | 4 | 2 | 2 | 1 | **5** | 3 |
| Facilidad de tests | 3 | 4 | 3 | **5** | 2 | 2 | 2 | 2 | **4** | 3 |
| Migración futura de QuPath | 2 | 1 | 3 | **5** | 3 | 3 | 2 | 2 | **4** | 2 |
| Mínima duplicación | 4 | 4 | 1 | **5** | 4 | 1 | 1 | 2 | **5** | 5 |
| Mínimo crecimiento del repo | 5 | 4 | 2 | **5** | 3 | 1 | 1 | 1 | **5** | 5 |
| Detección de cambios upstream | 1 | 2 | 2 | **5** | 3 | 3 | 2 | 3 | **4** | 2 |
| Seguridad | 4 | 4 | 4 | **5** | 3 | 3 | 2 | 2 | **4** | 4 |
| Integridad del bundle principal | 5 | 4 | 4 | **5** | 4 | 2 | 2 | 1 | **5** | 5 |
| Comprensibilidad | 5 | 5 | 3 | **4** | 2 | 3 | 3 | 2 | **3** | 4 |
| Escalabilidad a 100 | 1 | 3 | 1 | **5** | 2 | 1 | 1 | 1 | **4** | 2 |
| Facilidad para mantenedores humanos | 4 | 4 | 2 | **4** | 2 | 2 | 2 | 1 | **3** | 3 |
| Compatibilidad (expresar versión↔versión) | 1 | 1 | 5 | **5** | 3 | 3 | 3 | 3 | **4** | 3 |
| Trazabilidad legal | 2 | 3 | 3 | **5** | 4 | 3 | 1 | 2 | **5** | 4 |
| **Total (85 máx.)** | 44 | 54 | 49 | **83** | 53 | 41 | 30 | 32 | **73** | 54 |

### 6.2 Por qué se descartan submodules, subtree y vendoring

Los tres resuelven el mismo problema —«tener el código upstream a mano»— y el
proyecto **no tiene ese problema**: para auditar, traducir y verificar basta con
`repo + tag + commit + SHA-256`, que es exactamente lo que un lockfile guarda,
con dos órdenes de magnitud menos de coste.

| | **Submodules (A5)** | **Subtree (A6)** | **Vendoring (A7)** |
| --- | --- | --- | --- |
| **Ventajas** | Referencia exacta a un commit; no copia bytes en este repo | Clon único, sin pasos extra | Todo disponible sin red |
| **Desventajas** | 13 hoy, 100 mañana; los usuarios necesitan `--recursive`; un tag borrado upstream rompe el clon | Copia el código upstream **a nuestro historial**, para siempre | Duplicación masiva; deriva silenciosa; trazabilidad legal frágil |
| **Impacto en CI** | Checkout lento y frágil | Checkout pesado | Alto |
| **Impacto para usuarios** | Alto: clonar deja de ser trivial | Medio: repo grande | Medio |
| **Actualización upstream** | `git submodule update` | `subtree pull`, conflictivo | Resincronización manual |
| **Riesgo de divergencia** | Bajo | Alto | Muy alto |
| **Tamaño del repo** | Medio (índices) | **Muy alto e irreversible** | **Muy alto e irreversible** |
| **Complejidad operativa** | Alta | Alta | Alta |
| **Reproducibilidad** | Alta | Alta | Aparente, no real |
| **Veredicto** | **Descartado** | **Descartado** | **Descartado** salvo excepción |

**Cuantificación:** los artefactos del corpus incluyen JAR de 16 MB
(`dl-pixel-classifier`, `cell-analysis-tools`) y árboles de 255 ficheros. Con
vendoring, cada sincronización de cada componente añade peso **permanente** al
historial. Con 100 componentes, el repositorio pasaría de megabytes a cientos de
megabytes sin aportar ninguna capacidad que el lockfile no dé ya.

**Única excepción admisible para copiar fuente**, que debe justificarse por
escrito en el PR:

1. upstream archivado o borrado, sin espejo, con el componente aún en uso;
2. una licencia que obligue a redistribuir la fuente junto al binario que
   nosotros publiquemos;
3. un fragmento mínimo necesario para un test de regresión — nunca el árbol
   completo.

---

## 7. Arquitectura recomendada

> **Dos ejes independientes, unidos por un lockfile, con los forks fuera del
> repositorio.**

El eje `versions/<versión-de-QuPath>/` se conserva **intacto**: es el que protege
los artefactos congelados. Se añade un eje `components/<id>/` **independiente de
la versión de QuPath**. Los une `versions/<v>/components.lock.json`.

La razón es simple y es la que descarta A3: **la traducción de una extensión
depende de la versión de la extensión, no de la de QuPath.** Cellpose 0.12.1
puede ser compatible con 0.7.0 y con 0.8.0; su traducción es la misma. Ponerla
bajo el eje de QuPath la duplicaría y la haría divergir.

### 7.1 Árbol completo propuesto

```
qupath-es/
├─ components/                              # EJE COMPONENTE (independiente de QuPath)
│  ├─ README.md                             # cómo se lee y se amplía este eje
│  ├─ registry.json                         # SOURCE_OF_TRUTH · identidad de cada componente
│  └─ <component-id>/                       # se crea SOLO cuando hay contenido real
│     ├─ component.json                     # SOURCE_OF_TRUTH · manifiesto del componente
│     ├─ audits/
│     │  └─ <upstream-commit>.json          # UPSTREAM_REFERENCE · instantánea inmutable
│     ├─ l10n/
│     │  └─ <upstream-tag>/
│     │     ├─ <bundle-id>.tsv              # SOURCE_OF_TRUTH · traducción por clave
│     │     └─ dist/
│     │        └─ <basename>_es.properties  # GENERATED · nunca se edita a mano
│     └─ patches/
│        └─ <upstream-tag>/
│           └─ NNNN-descripcion.patch       # solo si es imprescindible
│
├─ versions/                                # EJE QUPATH (existente · INTACTO)
│  ├─ supported-versions.json               # INTACTO
│  └─ 0.7.0/
│     ├─ base/  dist/  work/  runtime/  reports/    # INTACTOS
│     ├─ fingerprint.json  target-version.json      # INTACTOS
│     └─ components.lock.json               # GENERATED_REVIEWED · pines certificados
│
├─ schemas/                                 # contratos verificables por test
│  ├─ component-registry.schema.json
│  ├─ component.schema.json
│  └─ components-lock.schema.json
│
├─ catalog/
│  └─ catalog.json                          # GENERATED · proyección al Extension Manager (DIFERIDO)
│
├─ tools/  tests/  docs/  runtime/          # existentes, se amplían sin reescribirse
└─ README.md  CONTRIBUTING.md  NOTICE.md  SECURITY.md  LICENSE
```

### 7.2 Función de cada directorio

| Ruta | Por qué existe |
| --- | --- |
| `components/` | El eje que hoy falta. Existe porque la traducción y la auditoría dependen de la versión **del componente**. |
| `components/registry.json` | Identidad estable y de cambio lento: id, repo, propietario, licencia, prioridad, punto de entrada. Se lee para saber **qué existe**. |
| `components/<id>/component.json` | Manifiesto: bundles, rutas relevantes para detectar cambios, identificadores protegidos, política de fork. Se lee para saber **cómo se trata**. |
| `components/<id>/audits/` | Una instantánea por commit auditado. **Inmutable**: es la referencia contra la que se calcula el diff upstream. Sin ella, cada actualización obliga a reauditar todo. |
| `components/<id>/l10n/<tag>/` | Traducción anclada a una release del componente. Un TSV por bundle, con el mismo modelo de estados que el Core. |
| `components/<id>/l10n/<tag>/dist/` | Bundle generado. Mismo contrato que `versions/*/dist/`: se genera, no se edita. |
| `components/<id>/patches/` | Series de parches mínimas, con destino upstream declarado. **Solo existe si hay parches reales** (R15). |
| `versions/<v>/components.lock.json` | La unión de los dos ejes: qué versión de cada componente está certificada para esa versión de QuPath, con hash de artefacto. |
| `schemas/` | Sin esquema, un registro se degrada en texto libre en seis meses. Son contratos con test. |
| `catalog/catalog.json` | Proyección generada al esquema del Extension Manager (F5). **Diferido** hasta que exista al menos un artefacto distribuible. |

**Lo que deliberadamente NO se crea:** ningún directorio por componente sin
contenido real; ningún submódulo, subtree ni copia de código upstream; ningún
fork dentro de este repositorio; ningún binario de terceros.

---

## 8. Metadatos, fuente de verdad y clasificación de ficheros

### 8.1 Clasificación

| Clase | Qué es | Ejemplos |
| --- | --- | --- |
| `SOURCE_OF_TRUTH` | Se edita a mano; se revisa; nada lo regenera | `components/registry.json`, `components/*/component.json`, `**/l10n/**/*.tsv`, `versions/*/work/translation.tsv`, `docs/*` |
| `UPSTREAM_REFERENCE` | Capturado de un tercero; **inmutable** | `versions/*/base/*`, `components/*/audits/*.json` |
| `GENERATED` | Se produce a partir de lo anterior; nunca se edita | `versions/*/dist/*.properties`, `components/*/l10n/*/dist/*`, `catalog/catalog.json` |
| `GENERATED_REVIEWED` | Se genera, pero requiere aprobación humana | `versions/*/components.lock.json` |
| `HUMAN_READABLE_REPORT` | Presenta datos, no los define | `versions/*/reports/*.md` |
| `CACHE` / `TEMPORARY` | No entra en Git | cubiertos por `.gitignore` |
| `RELEASE_ARTIFACT` | **No se almacena**; se referencia por URL + SHA-256 | JAR de extensión |

**Regla dura:** los hechos destinados a máquinas viven en JSON/TSV; el Markdown
los presenta y los explica, pero **nunca los define**. Este mismo informe cumple
la regla: su gemelo JSON es el dato, este documento es la lectura.

### 8.2 Cómo se impide editar por error un fichero generado

1. Los generados viven bajo `dist/` o llevan `.lock.` en el nombre.
2. Hay un test que regenera y compara; una edición manual lo rompe.
3. `CODEOWNERS` exige revisión del mantenedor en las rutas sensibles.

---

## 9. Versionado

**Principio:** la compatibilidad es una **relación**, no un atributo. Vive en el
lockfile, no dentro del componente.

```
qupath_version
  └─> component_id
       └─> upstream_tag
            └─> upstream_commit
                 └─> artifact + artifact_sha256
                      └─> localization_revision
                           └─> validation_status
```

Una versión nueva de QuPath crea `versions/<nueva>/` con su base congelada y su
propio `components.lock.json`. **Los componentes no se tocan** salvo que su
propia versión cambie. Certificar QuPath 0.8.0 con las mismas versiones de
extensión es un fichero nuevo, no 100 directorios nuevos.

Coste conocido de la próxima migración (F6): **894 → 2610 claves**.

---

## 10. Registro (`registry`)

**Fichero:** `components/registry.json` · **Clase:** `SOURCE_OF_TRUTH`

| Campo | Contenido |
| --- | --- |
| `id` | Identificador estable, kebab-case. **Decisión costosa de revertir.** |
| `canonical_name` | Nombre del repositorio upstream |
| `repository`, `owner` | Procedencia |
| `type` | `QUPATH_CORE` \| `QUPATH_EXTENSION` |
| `priority` | `P0` \| `P1` \| … |
| `role` | Para qué sirve, en una línea |
| `license` | SPDX |
| `build_system`, `entry_point` | Cómo se construye y cómo lo carga QuPath |
| `satellite_fork` | Repositorio del fork, si existe; `null` si no |
| `first_registered` | Fecha de alta |

**Por qué este nombre y esta ubicación.** «Registry» es el término que usa el
propio Extension Manager de QuPath para su estado local (`registry.json`), de
modo que el vocabulario ya resulta familiar en el ecosistema. Se coloca bajo
`components/` —y no en la raíz— para que el eje al que pertenece sea evidente.

Nombres descartados y por qué:

- `extensions-registry.json` — excluye a QuPath Core, que **no** es una extensión
  pero sí debe aparecer con su procedencia y su licencia.
- `versions/0.7.0/extensions/registry.json` — ata la identidad de un componente a
  una versión de QuPath, que es justo lo que A4 evita.

---

## 11. Lockfile

**Fichero:** `versions/<qupath-version>/components.lock.json` ·
**Clase:** `GENERATED_REVIEWED`

Su función es **reproducir exactamente el estado auditado y certificado** para
una versión de QuPath.

| Campo | Contenido |
| --- | --- |
| `qupath_version`, `qupath_upstream_commit` | A qué QuPath pertenece este pin |
| `upstream_tag`, `upstream_commit` | Qué versión exacta del componente |
| `artifact_name`, `artifact_url`, `artifact_sha256` | Qué binario, verificable |
| `declared_qupath_api` | Lo que el componente dice soportar |
| `localization_revision` | Qué revisión de traducción corresponde |
| `audit_status`, `translation_status`, `validation_status`, `distribution_status` | Estados **independientes** |
| `fork_repo`, `fork_tag`, `patches[]` | Divergencia, si la hay |
| `last_audited` | Cuándo |

**Por qué este nombre.** El sufijo `.lock.json` comunica de inmediato «no editar
a mano, regenerar». Se coloca **dentro** de `versions/<v>/` porque un pin solo
tiene sentido respecto de una versión de QuPath; en la raíz, `extensions.lock.json`
no expresaría a qué QuPath pertenece.

**Política de nulos:** `artifact_sha256 = null` es legítimo cuando el upstream no
publica release — el caso real de `tiatoolbox` (F9). Entonces el pin es solo por
commit, y el esquema debe admitirlo en vez de forzar un dato inventado.

---

## 12. Política para QuPath Core

QuPath Core **no es un componente más**: es el sustrato del que depende todo lo
demás. Diferencias sustantivas:

1. Su bundle **sí** es alcanzable externamente — único caso del corpus (F2).
2. Su base congelada **define la identidad de una versión** del repositorio.
3. Concentra el problema de `ParameterList` (F4).
4. Define la infraestructura de `PathClass`, mediciones y modelos que los tests
   deben proteger.
5. Un fork del Core es la última opción posible, y **hoy no se contempla**.

**Ubicación: se queda donde está, en `versions/<v>/`.** No se mueve a
`components/`. Mover la base congelada cambiaría rutas verificadas por
`fingerprint.json`, por `CODEOWNERS` y por los tests, sin ganar nada.

**Presencia en el registro:** aparece en `components/registry.json` con
`type = QUPATH_CORE`, para que un tercero encuentre su procedencia y su licencia
en el mismo sitio que las demás — pero **sin directorio propio** bajo
`components/`.

Lo que debe quedar registrado del Core: repositorio, versión, commit upstream,
build, ResourceBundles, `ParameterList`, UI hardcoded, menús, acciones, API de
extensiones, infraestructura de mediciones, `PathClass`, infraestructura de
modelos y APIs de localización.

---

## 13. Política para extensiones: integrar ≠ vendorizar

| **A. Integrar en el sistema de localización** (sí) | **B. Copiar su código fuente** (no) |
| --- | --- |
| URL del repositorio, propietario upstream | |
| commit, tag, release | |
| artefacto y su SHA-256 | |
| compatibilidad con QuPath | |
| licencia, sistema de construcción, punto de entrada | |
| ResourceBundles, cadenas, auditoría, traducciones | |
| tests, parches, cobertura, mecanismo de instalación | |

Copiar la fuente **duplica, deriva y rompe la trazabilidad legal**. Solo se
justifica en los tres casos del apartado 6.2, y siempre con justificación
escrita en el PR.

---

## 14. Forks

**Principio: un fork es deuda.** Se contrae solo cuando no hay alternativa menos
invasiva, y se paga con un PR upstream.

| Orden | Opción | Invasividad | Veredicto |
| --- | --- | --- | --- |
| 1 | **D.** PR upstream para externalizar cadenas y adoptar un cargador consciente de `DISPLAY` | 1 | **Preferida.** Resuelve el problema para todos los idiomas, no solo el nuestro |
| 2 | **E.** Extensión auxiliar propia de localización | 2 | Limitada: **no puede** cambiar cómo otra extensión resuelve su bundle (F2) |
| 3 | **B.** Mantener solo parches contra upstream | 3 | Útil como paso intermedio **y como contenido del PR** |
| 4 | **C.** Fork independiente en `LABVETNEB/<nombre>-es` | 4 | Aceptable cuando upstream no responde; aislado en un satélite |
| 5 | **A.** Modificar el código dentro de `qupath-es` | 5 | **Rechazada**: convierte un repo de localización en un monorepo Java |

**Nomenclatura:** `LABVETNEB/<nombre-del-repo-upstream>-es`.
**Estado actual: ningún fork existe, y ninguno se crea en esta fase.**

Prohibiciones que se mantienen: no se modifica un JAR instalado; no se
descompila y reempaqueta un JAR como solución de producción.

---

## 15. Parches

**Ubicación:** `components/<id>/patches/<upstream-tag>/NNNN-descripcion.patch`

- Mínimos y con destino upstream **declarado**.
- Deben aplicar limpiamente sobre el commit auditado; hay un test que lo comprueba.
- Un parche que lleva dos releases sin proponerse upstream se revisa o se retira.
- **Nunca** parchean identificadores funcionales: solo capas de presentación.

El fork es el vehículo; el parche es el contenido. **Lo que se conserva es el
parche.**

---

## 16. Licencias y trazabilidad legal

`qupath-es` es GPL-3.0. El corpus mezcla tres licencias:

| Licencia | Componentes |
| --- | --- |
| Apache-2.0 | 10 extensiones |
| BSD-3-Clause | `tiatoolbox` |
| GPL-3.0 | `sam`, `qupath-core` |

Por cada integración debe poder conocerse: repositorio, licencia, commit de
origen, artefacto, modificaciones, estado de redistribución y estado de fork.
Identidad y licencia en `registry.json`; lo efectivamente redistribuido, en el
lockfile. `NOTICE.md` gana una entrada por componente **en cuanto se
redistribuya algo suyo**, no antes.

**Regla dura:** ningún artefacto de terceros se redistribuye sin licencia,
commit de origen y hash registrados.

---

## 17. Artefactos y hashes

- **Nunca se almacenan binarios en Git.** Se referencian por `artifact_url`,
  `artifact_name` y `artifact_sha256`.
- Un test verifica el hash cuando hay red; sin red, verifica la forma.
- **Restricción upstream (F5):** el Extension Manager solo acepta releases en
  `github.com` y `maven.scijava.org`, por `https`. Cualquier plan de distribución
  debe respetarlo — y las releases de nuestros satélites lo cumplen por
  construcción.
- Si el upstream no publica release, el pin es por commit y
  `artifact_sha256 = null` (F9).

---

## 18. Actualización desde upstream

Modelo, deliberadamente igual al que el proyecto ya usa para el Core:

```
commit auditado A   (components/<id>/audits/A.json)
   └─> upstream avanza a B
        └─> diff A..B limitado a component.json:relevant_paths
             ├─ clasificar ficheros (bundle / FXML / código UI / script / metadatos de modelo)
             ├─ detectar claves nuevas, eliminadas y con inglés cambiado
             ├─ detectar cambios en identificadores protegidos
             ├─ detectar cambio de compatibilidad declarada
             ├─ reutilizar traducciones seguras según la política del migrador
             ├─ marcar SOURCE_CHANGED / PLACEHOLDER_SIGNATURE_CHANGED / STRUCTURE_CHANGED
             ├─ escribir una instantánea de auditoría nueva
             └─> ejecutar los tests del componente
```

**La decisión de diseño más importante de esta capa:** se **reutiliza la máquina
de estados de `tools/qupath_version_migrator.py`** en lugar de inventar una
segunda política. Ya está escrita, probada y es conservadora por defecto. Una
sola política de reutilización para el Core y para las extensiones.

**Control de coste (R07):** el diff se limita a `relevant_paths` declaradas en el
manifiesto del componente, de modo que un cambio en el README de una extensión no
dispara ninguna reauditoría.

---

## 19. Clasificación de cadenas

Toda cadena detectada se clasifica en tres dimensiones. La fila vive en el TSV,
que gana dos columnas respecto del modelo del Core.

**Funcional (`class`)**
`USER_VISIBLE_SAFE` · `USER_VISIBLE_CONTEXT_REQUIRED` · `MACHINE_IDENTIFIER` ·
`FILE_FORMAT_IDENTIFIER` · `MODEL_IDENTIFIER` · `MEASUREMENT_IDENTIFIER` ·
`PATHCLASS_IDENTIFIER` · `LOG_ONLY` · `DEVELOPER_ONLY` · `UNKNOWN`

**Superficie (`surface`)**
`MAIN_BUNDLE` · `OTHER_RESOURCE_BUNDLE` · `EXTENSION_RESOURCE_BUNDLE` ·
`EXTENSION_HARDCODED` · `CORE_HARDCODED` · `PARAMETERLIST` · `FXML` ·
`GROOVY_SCRIPT` · `PYTHON_SCRIPT` · `PLUGIN_METADATA` · `MODEL_METADATA` ·
`LOG_MESSAGE` · `MEASUREMENT_NAME` · `PATHCLASS_NAME` · `EXTERNAL_LIBRARY` ·
`OPERATING_SYSTEM` · `UNSUPPORTED` · `UNKNOWN`

**Estratégica**
`TRANSLATABLE_EXTERNAL` · `TRANSLATABLE_EXTENSION_RESOURCE` ·
`TRANSLATABLE_WITH_EXTENSION_FORK` · `TRANSLATABLE_ONLY_WITH_CORE_FORK` ·
`RUNTIME_PATCH_POSSIBLE` · `DO_NOT_TRANSLATE` · `UNKNOWN`

**Regla dura:** una fila con `class = UNKNOWN` **nunca** se traduce
automáticamente y **bloquea** la release del componente. `UNKNOWN` no es un
estado de tránsito silencioso: es una pregunta pendiente para una persona.

Aplicando la clasificación estratégica al corpus real:

| Clase estratégica | Componentes |
| --- | --- |
| `TRANSLATABLE_EXTERNAL` | `qupath-core` (**ya hecho**: 894/894) |
| `TRANSLATABLE_WITH_EXTENSION_FORK` | `dl-pixel-classifier`, `tiatoolbox`, `instanseg`, `cell-analysis-tools`, `training`, `wsinfer`, `djl`, `bioimageio`, `image-export-toolkit` |
| Requiere externalización previa | `stardist`, `cellpose`, `sam` |
| `TRANSLATABLE_ONLY_WITH_CORE_FORK` | `ParameterList` del Core, hasta que exista PR upstream |

Ejemplo de la distinción que gobierna todo:

```groovy
println("Training started")                        // USER_VISIBLE_SAFE
getMeasurementList().get("Nucleus: Area")          // MEASUREMENT_IDENTIFIER → DO_NOT_TRANSLATE
```

---

## 20. `ParameterList`

Prioridad alta en el encargo; la evidencia la **reubica** (F4): 0 usos en las 12
extensiones, 76 ficheros y 455 llamadas en el Core.

Se auditan `addTitleParameter`, `addStringParameter`, `addDoubleParameter`,
`addIntParameter`, `addBooleanParameter`, `addChoiceParameter`,
`addEmptyParameter`, `addParameter`, `setDescription`, `setHelpText`.

Y se distingue **siempre**:

| Elemento | ¿Traducible? |
| --- | --- |
| `parameter key` | **Nunca** |
| `display label` | Sí |
| `description` | Sí |
| `help text` | Sí |

```
Correcto:    Learning rate  →  Tasa de aprendizaje
Prohibido:   learningRate   →  tasaAprendizaje
```

La única excepción sería que upstream introdujera una capa formal de
localización que garantizase compatibilidad. Hoy no existe.

---

## 21. Protección de identificadores

**Nunca se traducen:** nombres de clases, packages Java, métodos, variables,
enums internos, nombres de fichero, rutas, claves JSON/YAML/XML, propiedades
consumidas por código, argumentos CLI, flags, identificadores y nombres de
modelos, IDs, checkpoints, engines, arquitecturas, claves de configuración,
regex, canales consumidos programáticamente, nombres de medición, `PathClass`
persistidas, encabezados esperados por scripts, parameter keys, nombres de
funciones, comandos Groovy y Python, imports, URLs, hashes, UUID, nombres de
repositorio y de artefacto, extensiones de fichero, tensor names, input/output
node names y weights.

**Mediciones — precaución extrema.** Cadenas como `Nucleus: Area`,
`Cell: Area`, `Nucleus: Circularity` o `Detection probability` pueden ser claves
consumidas por scripts, clasificadores, exportaciones y proyectos. **No se
traducen** salvo que se demuestre que existe una capa de presentación
independiente; en ese caso se traduce **solo esa capa**. En la duda:
`DO_NOT_TRANSLATE`.

**`PathClass`.** `Tumor`, `Stroma`, `Positive`, `Negative` y demás no se traducen
mientras no se demuestre separación entre id interno y nombre visible. Si no la
hay, se conserva el identificador original. El corpus tiene aquí un riesgo
concreto y medido: `cell-analysis-tools` (30 ficheros), `dl-pixel-classifier`
(14), `sam` (8), `cellpose` (7).

**Modelos de IA.** No se modifica nada que un engine consuma. Solo descripciones
visuales, y solo con capa segura.

**Cómo se hace cumplir:** la lista se declara en
`components/<id>/component.json` y **se verifica por test**, no por convención.
Un identificador protegido que cambie hace fallar CI. Esta es la diferencia entre
una política y un documento.

---

## 22. Tests

**Globales (siempre)**

- el bundle canónico no cambia (ya existe);
- los identificadores no cambian;
- ningún binario upstream se modifica;
- ningún comando peligroso en scripts (ya existe);
- UTF-8 sin BOM;
- metadatos válidos contra esquema;
- ids únicos;
- repositorios válidos;
- hashes con forma válida;
- compatibilidad declarada coherente;
- **integridad referencial** `registry` ↔ lockfiles ↔ directorios.

**Por extensión**

- parameter keys sin cambios;
- model IDs sin cambios;
- nombres de medición sin cambios;
- `PathClass` sin cambios;
- marcadores preservados;
- paridad estructural del ResourceBundle;
- solo cambian cadenas de presentación;
- los parches aplican limpiamente;
- la referencia upstream es reproducible;
- el hash del artefacto coincide.

---

## 23. CI

**No se implementa en esta fase.** Diseño propuesto:

- **Jobs globales**, siempre: esquemas, unicidad, integridad referencial,
  fingerprint (ya existe), UTF-8, identificadores.
- **Jobs por componente**, activados por ruta.
- **Job de detección**: calcula los componentes afectados desde las rutas del
  diff (`components/<id>/**`, `versions/<v>/components.lock.json`) y emite una
  **matriz dinámica**.

Respuestas a las tres preguntas del encargo:

> **¿Cómo evitar ejecutar todo el ecosistema si solo cambia Cellpose?**
> El job de detección ve que el diff toca únicamente `components/cellpose/**` y
> emite una matriz de un solo elemento. Corren los jobs globales (baratos, sobre
> ficheros pequeños) y el de Cellpose.

> **¿Cómo identificar qué extensión afecta un PR?**
> Por el prefijo de ruta `components/<id>/`. No hace falta heurística: la
> estructura **es** la respuesta. Esta es una de las razones de A4 frente a A10.

> **¿Cómo escalar CI con 100 extensiones?**
> Los jobs globales son O(1) en número y recorren ficheros pequeños. Los jobs por
> componente solo se activan por ruta, así que un PR típico sigue costando lo
> mismo con 12 que con 100. El único job que crece es la detección de deriva
> upstream, que se ejecuta **programado** y con límite de concurrencia, no en
> cada PR.

---

## 24. Escalabilidad

| Extensiones | Directorios de componente | Entradas por lockfile | Crecimiento estimado del repo | CI por PR | Carga para mantenedores | Veredicto |
| ---: | --- | ---: | --- | --- | --- | --- |
| 12 | ≤ 12 (creación perezosa; hoy 1-2) | 13 | ~1 MB sobre los 1,5 MB actuales | Bajo | Asumible por una persona | **Cómodo** |
| 25 | ≤ 25 | 26 | ~3-5 MB | Bajo | Una persona con revisión compartida | **Cómodo** |
| 50 | ≤ 50 | 51 | ~10-15 MB | Bajo por PR | Requiere automatizar la deriva | **Viable** |
| 100 | ≤ 100 | 101 | ~25-40 MB tras varios años | Bajo por PR | Exige priorización explícita | **Viable** |

**Comparación decisiva:** con A3 (version-major), 100 extensiones × 5 versiones
de QuPath = **500 directorios**, con la traducción duplicada en cada uno. Por eso
se descarta.

**El verdadero cuello de botella a 100 extensiones no es la arquitectura: es la
revisión lingüística humana.** La arquitectura debe permitir decir «este
componente está `AUDITED` pero no `TRANSLATED`» sin que eso sea un fallo — y por
eso los cuatro estados son independientes (R10).

---

## 25. Ventajas de la arquitectura recomendada

1. Preserva íntegramente la inversión actual: nada se mueve ni se renombra.
2. Crecimiento O(componentes + versiones).
3. La traducción vive donde vive su causa; la compatibilidad, también.
4. Certificar una versión de QuPath es **un fichero**, no una migración.
5. Aislamiento total entre extensiones: un PR toca un prefijo de ruta.
6. Ningún código de terceros entra en el repositorio.
7. Trazabilidad legal por construcción.
8. Reproducibilidad verificable: repo + tag + commit + hash.
9. Proyectable al canal de distribución oficial de QuPath (F5).
10. Los forks quedan aislados en satélites y no contaminan este repositorio.
11. Reutiliza el migrador y el validador ya probados en lugar de duplicar política.

## 26. Desventajas y qué se hace con ellas

| Desventaja | Mitigación |
| --- | --- |
| Hay que leer **dos** ficheros para responder «qué hay certificado» | `components/README.md` lo explica en cinco líneas; un `tools/status.py` puede imprimir la vista unida |
| Exige disciplina de esquema | Los esquemas son tests: la disciplina se automatiza |
| Más repositorios que gobernar cuando haya satélites | Solo se crean cuando un fork es inevitable; `registry.json` los enlaza |
| La proyección a catálogo es un artefacto generado más que mantener | Se difiere hasta que exista algo distribuible |
| La detección de deriva upstream depende de la red | Job programado, no bloqueante en PR |

---

## 27. Decisiones costosas de revertir

Estas merecen deliberación antes del primer PR:

1. **Adoptar submodules, subtree o vendoring** — reescribe el historial y es
   muy difícil de deshacer. *(Recomendación: no hacerlo.)*
2. **Elegir el eje version-major para los componentes** — obligaría a una
   migración masiva más adelante.
3. **Publicar un catálogo bajo una URL** — los usuarios la fijan y deja de poder
   cambiarse.
4. **Fijar los ids de componente** — quedan referenciados por lockfiles, forks,
   informes y rutas. *Por eso el primer PR es precisamente el que los fija: es la
   única decisión irreversible de esta etapa y conviene tomarla explícitamente.*
5. **El esquema de nombres de los forks satélite.**

## 28. Decisiones que conviene postergar

1. Si publicar catálogo propio — requiere al menos un artefacto distribuible.
2. Si construir una extensión auxiliar propia — su alcance real está limitado
   por F2.
3. Si versionar en Git los `.properties` generados de extensión o construirlos
   en CI.
4. Firma y notarización de los JAR forkeados.
5. Soporte de locales distintos de `es`.
6. Si el lockfile debe incluir dependencias transitivas de cada extensión.

---

## 29. Transición desde la arquitectura actual

1. **Nada de lo existente se mueve ni se renombra.**
2. El eje `components/` se añade en paralelo; `versions/` queda intacto.
3. El primer lockfile se añade a `versions/0.7.0/` sin tocar los artefactos
   congelados.
4. El utillaje se **generaliza**, no se reescribe: `translation_generator.py` y
   `translation_validator.py` ya operan sobre un par (base, dist) y admiten otros
   bundles.
5. `docs/ARCHITECTURE.md` gana una sección nueva; sus ocho invariantes actuales
   **no cambian**.

---

## 30. Hoja de ruta

Secuencia de PR pequeños, cada uno reversible por sí solo.

| PR | Título | Crea / modifica | Riesgo |
| ---: | --- | --- | --- |
| 1 | **Capa de identidad** | `schemas/component-registry.schema.json`, `components/registry.json`, `components/README.md`, `tests/test_component_registry.py` | Muy bajo |
| 2 | Capa de fijación para 0.7.0 | `schemas/components-lock.schema.json`, `versions/0.7.0/components.lock.json`, `tests/test_components_lock.py` | Bajo |
| 3 | Instantáneas de auditoría de los 13 | `components/<id>/component.json`, `components/<id>/audits/<commit>.json`, `tools/component_audit.py` | Bajo |
| 4 | Detector de deriva upstream | `tools/upstream_watch.py` + tests | Bajo |
| 5 | **Piloto de localización de una extensión** (sin fork) | `components/instanseg/l10n/v0.1.7/…` + tests | Bajo |
| 6 | PR upstream a QuPath: API de bundles de extensión | En `qupath/qupath`; aquí solo se registra su estado | Medio |
| 7 | Primer satélite de fork y su release, si el PR upstream no avanza | `LABVETNEB/qupath-extension-instanseg-es` | Medio |
| 8 | CI con matriz dinámica por rutas | `.github/workflows/ci.yml` | Medio |
| 9 | Proyección a catálogo del Extension Manager | `catalog/catalog.json`, `tools/catalog_projection.py` | Medio |
| 10 | Andamiaje de `versions/0.8.0/` cuando QuPath 0.8 se publique | — | Alto por volumen (1716 claves nuevas) |

**Por qué el piloto (PR 5) es `instanseg`:** 97 claves —volumen manejable pero
representativo—, mantenido por la propia organización QuPath (mayor probabilidad
de que el PR upstream prospere), bundle limpio y sin dependencia de Python. Mide
el coste real por clave antes de comprometerse con las 1148 del corpus.

**Por qué el PR 6 es la pieza de mayor apalancamiento:** una sola API en el Core
que sea consciente de `DISPLAY` y libre de colisiones desbloquearía las **once**
extensiones con bundle a la vez, y evitaría once forks. Es la diferencia entre
mantener once repositorios durante diez años y no mantener ninguno.

---

## 31. Primer PR recomendado

**Título:** `components: registro de identidad del ecosistema (solo metadatos)`

**Por qué este y no otro.** Es puramente aditivo, no toca nada congelado, no
depende de ninguna decisión aún abierta, y ya aporta valor: responde «qué hay
soportado» sin leer código. Y fija los ids de componente, que es la **única
decisión costosa de revertir** de esta etapa — mejor tomarla de forma explícita,
en un PR pequeño y revisable, que dejarla caer implícitamente en un PR grande.

### Ficheros que **debe crear**

```
schemas/component-registry.schema.json
components/registry.json
components/README.md
tests/test_component_registry.py
```

### Ficheros que **puede modificar**

```
docs/ARCHITECTURE.md      (sección nueva: los dos ejes)
```

### Ficheros que **NO debe tocar**

```
versions/0.7.0/base/qupath-gui-strings.properties
versions/0.7.0/base/qupath-gui-strings_en.properties
versions/0.7.0/base/MANIFEST.MF
versions/0.7.0/dist/qupath-gui-strings_es.properties
versions/0.7.0/work/translation.tsv
versions/0.7.0/fingerprint.json
versions/0.7.0/target-version.json
versions/supported-versions.json
versions/0.7.0/reports/*          (salvo añadir informes nuevos)
versions/0.7.0/runtime/*
runtime/*
tools/*
tests/*                           (los siete ficheros existentes)
.github/workflows/ci.yml
.gitattributes
```

### Criterios de aceptación

- Los 147 tests siguen pasando, más los nuevos.
- Los SHA-256 congelados no cambian.
- `git diff --stat` muestra únicamente los ficheros del PR.

---

## 32. Usabilidad: qué debe poder responder un tercero

| Pregunta | Dónde se responde |
| --- | --- |
| ¿Qué versión de QuPath usa? | `versions/supported-versions.json` |
| ¿Qué extensiones están soportadas? | `components/registry.json` |
| ¿Qué versión de cada extensión corresponde? | `versions/<v>/components.lock.json` |
| ¿Qué estado de traducción existe? | `translation_status` en el lockfile |
| ¿Cómo se instala? | `docs/INSTALLATION.md` |
| ¿Qué permanece en inglés? | `reports/localization-coverage.md` y este informe |
| ¿Qué requiere fork o parche? | `fork_repo` / `patches[]` en el lockfile |
| ¿Qué es experimental y qué está validado? | `distribution_status` y `validation_status` |

**Los estados no se mezclan.** Una extensión puede estar `AUDITED` sin estar
`TRANSLATED`; otra puede estar `TRANSLATED` sin estar `VALIDATED`. Hoy, tras esta
auditoría, **las 12 extensiones están `AUDITED` y ninguna está `TRANSLATED`**.

---

## 33. Riesgos

| id | Sev. | Riesgo | Mitigación |
| --- | --- | --- | --- |
| K1 | **Alta** | Upstream no acepta los PR de externalización y los forks se vuelven permanentes | La traducción vive en TSV independientes del build: un fork se reduce a regenerar y reconstruir. Se limita el número de forks priorizando P0 |
| K2 | **Alta** | Traducir una cadena que en realidad es un identificador consumido por scripts o modelos | `class = UNKNOWN` bloquea; identificadores protegidos declarados y verificados por test |
| K3 | **Alta** | La migración a 0.8 (894 → 2610) consume todo el esfuerzo disponible | Planificarla como versión propia; no simultanearla con las primeras extensiones |
| K4 | Media | Deriva de los forks release tras release | Parches mínimos, rebase por tag, revisión obligatoria si un parche vive dos releases |
| K5 | Media | Mezcla de licencias al redistribuir artefactos de terceros | Licencia, commit y hash obligatorios en el lockfile; `NOTICE.md` por componente |
| K6 | Media | Registro y lockfiles divergen de la realidad sin que nadie lo note | Test de integridad referencial y job programado de deriva |
| K7 | Baja | `tiatoolbox` no publica releases | Pin por commit y `artifact_sha256 = null`, contemplado por el esquema |
| K8 | Baja | Contaminar el bundle principal al ampliar el utillaje a varios bundles | Los artefactos de 0.7.0 están congelados y vigilados por fingerprint y CI |

---

## 34. Lo que no se ha podido verificar

Se declara, no se rellena.

| id | Pregunta | Estado | Impacto |
| --- | --- | --- | --- |
| U1 | Comportamiento real de cada extensión sobre 0.7.0 en ejecución | `NOT_VERIFIED` | Auditoría estática; no se instaló ni ejecutó ninguna extensión |
| U2 | Categoría de locale exacta de `ResourceBundle.getBundle(String)` | `NOT_VERIFIED` | **Ninguno** sobre la conclusión: `getDefault()` y `getDefault(FORMAT)` valen ambas `en_US` bajo la política del proyecto |
| U3 | Reparto exacto visible/no visible en las extensiones sin bundle | `NOT_VERIFIED` | Requiere revisión literal por literal, en el piloto de cada componente |
| U4 | Nombres de medición y `PathClass` concretos por extensión | `NOT_VERIFIED` | Se enumerarán en `component.json` durante el PR 3 |
| U5 | Compatibilidad real con 0.7.0 más allá de lo declarado | `PARTIALLY_VERIFIED` | Se conoce la API declarada (0.6.0 ×7, 0.7.0 ×4, 0.8.0-SNAPSHOT ×1); no verificada en ejecución |
| U6 | Si el equipo de QuPath aceptaría una API de bundles de extensión | `UNKNOWN` | Abrir discusión upstream antes de escribir el PR 6 |

La razón de U2 es concreta: la imagen `jlink` que QuPath distribuye no incluye
`jshell` ni un JDK, y no hay Java en el `PATH` de la máquina auditora.

---

## 35. Conclusión

La hipótesis natural de partida —«crear una carpeta `extensions/` y traducir sus
`.properties`»— **no funciona**, y la auditoría lo demuestra con dos hechos
medidos: el espacio de nombres externo es plano y colisiona en once bundles
(F1), y ninguna de las doce extensiones resuelve su bundle por una vía que el
directorio externo pueda alcanzar (F2).

De ahí se sigue lo demás. El activo duradero de `qupath-es` no van a ser ficheros
`.properties` de extensión: van a ser **la capa de metadatos** (qué existe, qué
es alcanzable, qué está congelado), **la fuente de verdad de traducción en TSV**
—independiente del sistema de construcción y por tanto superviviente a cualquier
fork— y **la relación con upstream**. La arquitectura recomendada está diseñada
alrededor de eso: dos ejes independientes, unidos por un lockfile, sin una sola
línea de código ajeno dentro del repositorio.

Y preserva por completo lo ya invertido: **894 / 894 claves**, artefactos
canónicos intactos, 147 tests en verde.

---

## Anexo · Correspondencia con el encargo

Este informe cubre los 51 puntos solicitados en el orden de sus secciones:
1-8 → §1 · 9 → §2 · 10 → §2.1 · 11 → §2.2 · 12 → §3 · 13 → §3.1 y JSON
`components[]` · 14 → §5 · 15 → §6 · 16 → §6.1 · 17 → §7 · 18 → §7.1 ·
19 → §7.2 · 20-21 → §8 · 22 → §9 · 23 → §10 · 24 → §11 · 25 → §12 ·
26 → §13 · 27 → §14 · 28 → §15 · 29-31 → §6.2 · 32 → §16 · 33-34 → §17 ·
35 → §18 · 36 → §19 · 37 → §20 · 38 → §21 · 39 → §22 · 40 → §23 · 41 → §24 ·
42 → §33 · 43 → §25 · 44 → §26 · 45 → §27 · 46 → §28 · 47 → §29 · 48 → §30 ·
49-51 → §31.

Los datos que este documento presenta viven, en forma estructurada, en
[`ecosystem-repository-architecture-audit.json`](ecosystem-repository-architecture-audit.json).
Si ambos discrepan, **el JSON es el dato** y este Markdown es la lectura.
