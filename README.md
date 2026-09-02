# QuPath ES

Localización castellana de la interfaz principal de QuPath, distribuida como
**bundle externo**. El código fuente, los JAR y el ejecutable de QuPath no se
modifican en ningún momento.

Proyecto no oficial. Véase [`NOTICE.md`](NOTICE.md) para procedencia y
licencia (GPL-3.0).

## Versión objetivo

| Item | Valor |
| --- | --- |
| QuPath | 0.7.0 |
| Build | 2026-02-25 16:06 |
| Commit upstream | `04ccfa4` |
| JAR de origen | `qupath-gui-fx-0.7.0.jar` |
| SHA-256 del JAR | `4C3DB78B5A3A1F519F3D8CD5BAC4C69E598B1E59D97E666C4BDD23C31164B968` |
| SHA-256 del bundle canónico | `796EFC44FC23369E4D7BDFDE69C0FA2A702051BF2F9D71399157B505E8D45D2D` |

## Estado

| Métrica | Valor |
| --- | --- |
| Claves del bundle principal | 894 |
| `REVIEWED` | 884 |
| `KEEP_EN` | 10 |
| `BLOCKED` / `PENDING` / `DRAFT` | 0 |
| Validador estructural | PASS (0 errores) |
| Auditoría lingüística | SAFE TO INSTALL (0 errores, 0 avisos) |
| Suite de pruebas | 71 tests OK |

**Cobertura del bundle principal de la GUI: 894/894.** Esto **no** significa
que toda la aplicación quede en castellano; véase
[`versions/0.7.0/reports/localization-coverage.md`](versions/0.7.0/reports/localization-coverage.md).

## Estructura

```
tools/                  pipeline de traducción y validación (Python 3.10+)
  properties_audit.py      analizador de Java .properties
  translation_validator.py validador estructural (claves, placeholders, escapes)
  translation_generator.py generador del bundle a partir del TSV
  es_translations.py       tabla de traducciones (fuente de verdad lingüística)
  apply_translations.py    vuelca las traducciones al TSV de trabajo
  linguistic_audit.py      auditoría lingüística y de calidad
  coverage_audit.py        auditoría de cobertura sobre la distribución instalada
tests/                  71 pruebas unitarias y de regresión
versions/0.7.0/
  base/                 bundle inglés canónico + MANIFEST + fingerprint (INMUTABLE)
  work/translation.tsv  fuente de verdad por clave (estado, revisor, fecha)
  dist/                 bundle español generado
  runtime/              script de arranque para el locale español
  reports/              validación, auditoría, cobertura, prueba E2E
```

El fichero `.properties` **se genera**; nunca se edita a mano. Para cambiar una
traducción se edita `tools/es_translations.py` y se regenera.

## Reconstruir y validar

```bash
python tools/apply_translations.py versions/0.7.0/work/translation.tsv
python tools/translation_generator.py generate \
    versions/0.7.0/base/qupath-gui-strings.properties \
    versions/0.7.0/work/translation.tsv \
    versions/0.7.0/dist/qupath-gui-strings_es.properties
python tools/translation_validator.py \
    versions/0.7.0/base/qupath-gui-strings.properties \
    versions/0.7.0/dist/qupath-gui-strings_es.properties
python tools/linguistic_audit.py \
    versions/0.7.0/base/qupath-gui-strings.properties \
    versions/0.7.0/work/translation.tsv \
    versions/0.7.0/dist/qupath-gui-strings_es.properties \
    --json versions/0.7.0/reports/global-translation-audit.json \
    --markdown versions/0.7.0/reports/global-translation-audit.md
python -m unittest discover -s tests -p "test_*.py"
```

## Actualizar QuPath

Cuando instales una versión nueva de QuPath, cierra QuPath y ejecuta:

```bash
.\runtime\update-qupath-es.ps1
```

Es un **diagnóstico que no escribe nada**. Detecta la versión instalada, indica
si existe paquete español para ella y qué haría a continuación. Guía completa en
[`docs/UPDATING_QUPATH_ES.md`](docs/UPDATING_QUPATH_ES.md).

El actualizador nunca copia la traducción anterior sobre una versión nueva sin
comparar claves, textos ingleses, *placeholders* y estructura, y nunca instala
una traducción que no haya pasado el validador.

## Instalación manual

1. Copiar `versions/0.7.0/dist/qupath-gui-strings_es.properties` a
   `<inicio>/QuPath/localization/`.
2. Copiar `versions/0.7.0/runtime/qupath-es-startup.groovy` a
   `<inicio>/QuPath/scripts/` y activarlo en
   *Preferences → General → Startup script path*.
3. Reiniciar QuPath.

El script de arranque es necesario porque el runtime que acompaña a QuPath
0.7.0 en Windows omite el módulo `jdk.localedata`, de modo que la preferencia
de idioma no puede persistirse entre reinicios. Detalle y verificación en
[`versions/0.7.0/reports/spanish-locale-runtime.md`](versions/0.7.0/reports/spanish-locale-runtime.md).

El script es **idempotente**: si el locale de presentación ya es español, no
cambia nada y lo registra como `alreadySpanish=true`.

### ¿Por qué un script y no una opción de la JVM?

Se probaron todas las alternativas menos invasivas —propiedades
`user.language.display`, `JAVA_TOOL_OPTIONS`, opciones del launcher jpackage,
`-D` de la CLI de QuPath— y **todas fallan**: `PathPrefs` ejecuta
`Locale.setDefault(Locale.US)` durante su inicialización estática, lo que
descarta cualquier locale fijado antes. Y la preferencia no puede persistirse
porque `LocaleConverter` serializa a nombres de visualización y este runtime
solo conoce 5 locales, todos ingleses. Evidencia completa y medidas en
[`versions/0.7.0/reports/pre-gui-locale-solution.md`](versions/0.7.0/reports/pre-gui-locale-solution.md).

Consecuencia: unas pocas cadenas resueltas durante la construcción de la
interfaz (tooltips de la barra de herramientas, nombres de herramientas de
dibujo, texto de marcador del visor) quedan en inglés. El desglose está en
[`versions/0.7.0/reports/locale-timing-audit.md`](versions/0.7.0/reports/locale-timing-audit.md).

### Textos que no son traducibles en 0.7.0

`Image list`, `Search entry in project` y
`Drag & drop an image file or project folder` **no son claves del bundle** en
0.7.0: son constantes compiladas en `ProjectBrowser.class` y
`ViewerManager.class`. Se externalizaron después de esta versión, así que
ningún mecanismo de localización externo puede traducirlas aquí.

## Formatos numéricos

Solo se cambia el locale de **presentación**. Los locales *default* y *format*
permanecen en `en_US`, de modo que el separador decimal sigue siendo el punto
y las mediciones exportadas no se ven afectadas. La prueba E2E lo verifica
(`formatSample=1234.50`, `formatUsesDot=true`).

## Revertir

- Desactivar el script de arranque en las preferencias, o
- borrar `<inicio>/QuPath/localization/qupath-gui-strings_es.properties`.

En ambos casos QuPath vuelve al inglés. La instalación de QuPath queda intacta.
