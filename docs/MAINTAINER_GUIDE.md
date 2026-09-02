# Guía del mantenedor

Para quien vaya a corregir traducciones, preparar una versión nueva de QuPath o
publicar una release.

Antes de tocar nada, lee [`ARCHITECTURE.md`](ARCHITECTURE.md): explica los
invariantes que no deben romperse.

---

## Puesta en marcha

```powershell
git clone https://github.com/LABVETNEB/qupath-es.git
cd qupath-es
python -m unittest discover -s tests -p "test_*.py"
```

Deben pasar todas las pruebas antes de empezar. Sin dependencias de terceros:
solo Python 3.7+ y su biblioteca estándar.

---

## Regla número uno

**El fichero `.properties` es un artefacto generado. Nunca se edita a mano.**

Para cambiar una traducción se edita `tools/es_translations.py` y se regenera.
Si editas el `.properties` directamente, el siguiente `build` deshará tu cambio
sin avisar.

---

## Corregir una traducción existente

1. Edita la entrada en `tools/es_translations.py`.

2. Vuelca los cambios al TSV y regenera:

   ```powershell
   python tools\apply_translations.py versions\0.7.0\work\translation.tsv
   python tools\translation_generator.py generate `
       versions\0.7.0\base\qupath-gui-strings.properties `
       versions\0.7.0\work\translation.tsv `
       versions\0.7.0\dist\qupath-gui-strings_es.properties
   ```

3. Valida:

   ```powershell
   python tools\translation_validator.py `
       versions\0.7.0\base\qupath-gui-strings.properties `
       versions\0.7.0\dist\qupath-gui-strings_es.properties
   ```

   Debe terminar en `Result: PASS` con `Total errors: 0`.

4. Audita la lengua:

   ```powershell
   python tools\linguistic_audit.py `
       versions\0.7.0\base\qupath-gui-strings.properties `
       versions\0.7.0\work\translation.tsv `
       versions\0.7.0\dist\qupath-gui-strings_es.properties `
       --json versions\0.7.0\reports\global-translation-audit.json `
       --markdown versions\0.7.0\reports\global-translation-audit.md
   ```

   Debe terminar en `Verdict: SAFE TO INSTALL`.

5. Pasa las pruebas y actualiza el hash publicado:

   ```powershell
   python -m unittest discover -s tests -p "test_*.py"
   Get-FileHash versions\0.7.0\dist\qupath-gui-strings_es.properties -Algorithm SHA256
   ```

   Si el bundle cambió, hay que actualizar el hash en `README.md`,
   `versions/supported-versions.json` y `tests/test_runtime_locale.py`.

---

## Convenciones de traducción

- Castellano técnico neutro, comprensible en España y Latinoamérica.
- Tratamiento impersonal o de usted; nunca tuteo.
- Infinitivo en órdenes de menú: «Abrir imagen», no «Abre imagen».
- Mayúscula solo en la inicial: «Crear proyecto», no «Crear Proyecto».
- Comillas angulares « » cuando haga falta entrecomillar.
- Terminología fija: anotación, detección, célula, núcleo, medición,
  clasificación, visor, jerarquía, flujo de trabajo, superposición, tesela,
  submuestreo, cilindro TMA (no «núcleo TMA», que chocaría con *nucleus*).
- Acrónimos y marcas se conservan: TMA, ROI, DAB, H&E, GeoJSON, ImageJ,
  Bio-Formats, OpenSlide, Groovy, QuPath.

### Marcadores

- `{0}`, `{1}`, `{0,number}` se pueden **reordenar** libremente: el índice es
  explícito.
- `%s`, `%d` **no** se pueden reordenar salvo que uses `%1$s`, `%2$d`.
- En cualquier clave que contenga `{n}`, un apóstrofo literal debe escribirse
  duplicado (`''`), o mejor evitarse usando comillas angulares.

### `KEEP_EN`

Úsalo cuando el valor español deba ser **idéntico** al inglés a propósito:
acrónimos, nombres de producto, etiquetas numéricas. Añádelo al conjunto
`KEEP_EN` de `tools/es_translations.py`. El invariante es: el conjunto de
valores idénticos al inglés debe coincidir exactamente con el conjunto
`KEEP_EN`.

---

## Preparar una versión nueva de QuPath

Cuando salga QuPath 0.8.x, 0.9.x…

### 1. Instalar la versión nueva y capturar

Con QuPath cerrado:

```powershell
.\runtime\update-qupath-es.ps1 -PrepareMigration
```

Esto hace, en orden:

1. extrae el bundle inglés canónico del JAR instalado, byte a byte;
2. escribe `versions/<nueva>/fingerprint.json`;
3. crea `versions/<nueva>/{base,work,dist,reports,runtime}`;
4. compara con la versión anterior traducida;
5. genera `versions/<nueva>/work/translation.tsv`;
6. genera los informes de migración.

Salida típica:

```
Migration analysis 0.7.0 -> 0.8.0
  reusable            849
  source changed      26
  new                 40
  removed             15
  placeholder changes 2
  structure changes   2
  blocked             4

Safe automatic migration: 92.4%

Next action: review/translate 70 entries before release.
No files were installed.
```

Los ficheros de `base/` son **inmutables**. Si ya existen, el comando se niega a
recapturar sin `-Force`.

### 2. Revisar el informe

`versions/<nueva>/reports/migration-from-<anterior>.md` clasifica cada clave:

| Caso | Qué pasó | Qué hacer |
| --- | --- | --- |
| `A_REUSE` | Inglés idéntico | Nada |
| `E_KEEP_EN` | Deliberadamente inglés, sin cambios | Nada |
| `B_SOURCE_CHANGED` | Cambió el texto inglés | Re-revisar; la traducción anterior está solo como referencia |
| `E_KEEP_EN_SOURCE_CHANGED` | Era `KEEP_EN` y cambió el inglés | Decidir si sigue procediendo dejarlo en inglés |
| `F_PLACEHOLDER_CHANGED` | Cambió la firma de marcadores | **Obligatorio revisar**. Único caso que puede provocar una excepción en ejecución |
| `G_STRUCTURE_CHANGED` | Cambiaron escapes o estructura | Revisar |
| `C_NEW` | Clave nueva | Traducir |
| removed | Desapareció | Archivada en `work/retired.tsv`; se recupera sola si vuelve |

### 3. Traducir lo pendiente

Trabajo lingüístico, no automatizable. Prioriza por visibilidad: menús,
acciones, preferencias, visor, paneles, comandos, diálogos, textos de ayuda.

Al terminar, ninguna fila debe quedar en `PENDING`, `DRAFT` ni `BLOCKED`.

### 4. Generar, validar y auditar

Igual que en «Corregir una traducción existente», cambiando `0.7.0` por la
versión nueva.

### 5. Registrar la versión

Añade la entrada a `versions/supported-versions.json`. Es un registro
**orientativo**: el actualizador siempre lo contrasta con la instalación real.
Hay una prueba que verifica que coincide con los artefactos reales.

### 6. Regenerar los informes de cobertura

```powershell
python tools\coverage_audit.py "$env:LOCALAPPDATA\QuPath-<nueva>\app" `
    --json versions\<nueva>\reports\localization-coverage.json `
    --main-bundle-keys <n>

python tools\locale_timing_audit.py "$env:LOCALAPPDATA\QuPath-<nueva>\app" `
    versions\<nueva>\base\qupath-gui-strings.properties `
    --json versions\<nueva>\reports\locale-timing-audit.json
```

Compara con la versión anterior: si QuPath externalizó más cadenas, la cobertura
de la aplicación debería mejorar.

### 7. Comprobar el modo de locale

```powershell
.\runtime\update-qupath-es.ps1
```

Si la versión nueva incluye `jdk.localedata` y el conversor de preferencias
hace ida y vuelta correctamente, el modo será `LOCALE_MODE_NATIVE` y el script
de arranque dejará de instalarse. En ese caso, documenta el cambio.

---

## Release gate

Una versión **no** se publica ni se instala hasta cumplir **todo**:

| Criterio | Valor exigido |
| --- | --- |
| `PENDING` | 0 |
| `DRAFT` | 0 |
| `BLOCKED` | 0 |
| Validador estructural | PASS, 0 errores |
| Auditoría lingüística | `SAFE TO INSTALL` |
| Número de claves | Idéntico al base |
| Orden de claves | Idéntico al base |
| Claves faltantes / sobrantes / duplicadas | 0 |
| Errores de marcadores | 0 |
| Errores estructurales | 0 |
| Valores vacíos accidentales | 0 |
| Codificación | UTF-8 válido, sin BOM |
| Suite de pruebas | Todas OK |

Comprobación rápida:

```powershell
python tools\qupath_version_migrator.py status --repo . --version 0.7.0
```

Debe devolver `"releasable": true` con `"blockers": []`.

El actualizador aplica este mismo criterio: `-Apply` se niega si no se cumple.

---

## Pruebas

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

| Fichero | Qué protege |
| --- | --- |
| `test_properties_audit.py` | El analizador de `.properties` y el bundle canónico |
| `test_translation_validator.py` | Marcadores, entrecomillado, escapes, códigos de salida |
| `test_translation_generator.py` | Generación e identidad byte a byte |
| `test_linguistic_audit.py` | Glosario, acrónimos, falsos positivos, detección de versión |
| `test_repository_integrity.py` | Fingerprints y normalización de finales de línea en Git |
| `test_runtime_locale.py` | Script de arranque, ausencia de estado global, hash del JAR |
| `test_version_migrator.py` | Política de migración, detección, compatibilidad de PowerShell |

Si corriges un fallo, **añade una prueba de regresión**. Varias de las que hay
existen precisamente por eso.

---

## Qué no hacer

- No edites `versions/*/base/*`. Es inmutable y hay una prueba que lo comprueba.
- No edites el `.properties` de `dist/`. Se genera.
- No relajes el validador para que pase una versión nueva. Si aparece un formato
  que no entiende, **amplía primero el validador y añade pruebas**.
- No cambies `FORMAT` ni el idioma principal a español.
- No añadas comandos que cierren procesos o modifiquen configuración global: hay
  pruebas que lo impiden.
- No instales una traducción parcial como release.

---

## Publicar

```powershell
git status
git diff --stat
git diff
```

Verifica expresamente que `versions/*/base/` no aparece en el diff. Después:

```powershell
git add -A
git commit
git push origin main
```
