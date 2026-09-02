# Solución de problemas

Tabla de referencia. Para el caso concreto «QuPath volvió al inglés», hay una
guía dedicada en [`REPAIR.md`](REPAIR.md).

**Primer paso ante casi cualquier problema**, con QuPath cerrado:

```powershell
cd C:\qupath-es
.\runtime\update-qupath-es.ps1
```

No escribe nada y suele identificar la causa por sí solo. Cada ejecución deja
un registro en `logs\`.

---

## Idioma

### QuPath abre completamente en inglés

| | |
| --- | --- |
| **Causa probable** | Preferencias perdidas, o la traducción no está instalada |
| **Diagnóstico** | El *dry run* avisa de preferencias incompletas, o `Installed bundle: not installed` |
| **Solución** | `-Repair`; si faltan ficheros, `-Apply` |

Ver [`REPAIR.md`](REPAIR.md).

### QuPath abre parcialmente en inglés

| | |
| --- | --- |
| **Causa probable** | Comportamiento normal de QuPath 0.7.0 |
| **Diagnóstico** | Los menús y pestañas están en castellano, pero algunos textos sueltos no |
| **Solución** | Ninguna. No es un fallo |

Los menús, acciones, pestañas y preferencias se traducen. Quedan fuera los
textos escritos dentro del código de QuPath, los diálogos de parámetros de los
algoritmos y las extensiones con su propio fichero de idioma.

### `Image list` sigue en inglés

### `Search entry in project` sigue en inglés

### `Drag & drop an image file or project folder` sigue en inglés

| | |
| --- | --- |
| **Causa** | Estos tres textos **no son claves de traducción** en QuPath 0.7.0: están compilados dentro de `ProjectBrowser` y `ViewerManager` |
| **Diagnóstico** | Confirmado por inspección de los JAR instalados |
| **Solución** | Ninguna posible desde fuera. Se externalizaron en versiones posteriores a 0.7.0 |

No lo reportes como error de instalación: ninguna traducción externa puede
cambiarlos en esta versión.

### Los números pasaron a usar coma decimal

| | |
| --- | --- |
| **Causa** | Se cambió *Idioma principal* o *Fechas y números* en las preferencias |
| **Diagnóstico** | El *dry run* muestra `Number format: 1234,50 (decimal point: False)` |
| **Solución** | *Preferencias → Idioma y región*: poner **Idioma principal** y **Fechas y números** en `English (United States)`. Cambiar solo **Interfaz de usuario** |

Esto importa: la coma decimal afecta a mediciones y exportaciones CSV.

---

## Detección de QuPath

### El script dice `No usable QuPath installation was found`

| | |
| --- | --- |
| **Causa probable** | QuPath está instalado fuera de `%LOCALAPPDATA%` |
| **Solución** | Indica la ruta: `-QuPathPath "C:\ruta\a\QuPath-0.7.0"` |

### El script detecta varias versiones

```
Several QuPath installations were found:
  0.7.0  ...\QuPath-0.7.0
  0.8.0  ...\QuPath-0.8.0
Ambiguous installation. Re-run with -Version or -QuPathPath.
```

| | |
| --- | --- |
| **Causa** | Hay más de un QuPath instalado. El actualizador **no elige por ti** |
| **Solución** | `-Version 0.7.0` o `-QuPathPath "..."` |

### `jar name says X, manifest says Y`

| | |
| --- | --- |
| **Causa** | La instalación es inconsistente: el nombre del JAR y su manifiesto discrepan |
| **Diagnóstico** | Aparece en `Version evidence` |
| **Solución** | Reinstala QuPath desde el instalador oficial. No fuerces la instalación de la traducción |

### `gui jar is not readable as a zip`

| | |
| --- | --- |
| **Causa** | El JAR está corrupto o la descarga quedó a medias |
| **Solución** | Reinstala QuPath |

### No existe `QuPath-x.y.z (console).exe`

| | |
| --- | --- |
| **Consecuencia** | La sonda de capacidades no puede ejecutarse |
| **Diagnóstico** | `Capability probe unavailable` |
| **Solución** | No bloquea la instalación: el actualizador asume el modo conservador (`STARTUP_FALLBACK`) y avisa |

---

## Instalación

### `Spanish package for X.Y.Z: NOT READY`

| | |
| --- | --- |
| **Causa** | Tu versión de QuPath no tiene traducción publicada |
| **Solución** | Usa una versión soportada, o prepara la migración: [`UPDATING_QUPATH_ES.md`](UPDATING_QUPATH_ES.md) |

**No copies a mano el bundle de otra versión.** Puede tener claves que no
existen, faltar claves nuevas, o traer marcadores incompatibles.

### `Refusing to install an unvalidated translation`

| | |
| --- | --- |
| **Causa** | La traducción de esa versión tiene entradas `PENDING`, `DRAFT` o `BLOCKED`, o no pasa el validador |
| **Solución** | Es correcto: una traducción parcial no se instala. Ver [`MAINTAINER_GUIDE.md`](MAINTAINER_GUIDE.md) |

### `QuPath is running. Close QuPath manually and run this again.`

| | |
| --- | --- |
| **Causa** | Hay un proceso de QuPath abierto y el actualizador necesita escribir |
| **Solución** | Cierra QuPath desde su ventana |

El actualizador **nunca** cierra procesos por su cuenta, a propósito: podrías
perder trabajo sin guardar.

Si crees que no está abierto, comprueba:

```powershell
Get-Process | Where-Object { $_.ProcessName -like 'QuPath*' }
```

Puede quedar un proceso de consola de una ejecución anterior. Ciérralo desde su
ventana.

### `Hash mismatch after copy`

| | |
| --- | --- |
| **Causa** | El fichero copiado no coincide con el original: disco lleno, antivirus, permisos |
| **Solución** | El actualizador aborta y no da la instalación por buena. Revisa espacio en disco y vuelve a intentarlo |

### El hash del bundle no coincide con el esperado

```powershell
Get-FileHash "$env:USERPROFILE\QuPath\localization\qupath-gui-strings_es.properties" -Algorithm SHA256
```

Debe dar `E4A966C9...4C128FC19` para 0.7.0. Si no, reinstala con `-Apply`.

### `Python 3.10+ is required but was not found on PATH`

| | |
| --- | --- |
| **Causa** | Python no está instalado o no está en el `PATH` |
| **Solución** | Instala Python 3, o usa la [instalación manual](INSTALLATION.md#apéndice-instalación-manual-sin-python) |

Comprueba con `python --version`.

---

## PowerShell

### `No se puede cargar el archivo ... porque la ejecución de scripts está deshabilitada`

```powershell
powershell -ExecutionPolicy Bypass -File .\runtime\update-qupath-es.ps1
```

Afecta solo a esa ejecución.

### La consola se queda bloqueada y no acepta comandos

| | |
| --- | --- |
| **Causa** | Se lanzó `QuPath-x.y.z (console).exe` en primer plano y sigue ejecutándose |
| **Solución** | Cierra esa ventana de QuPath. La consola volverá a responder |

No uses `Ctrl+C` sobre QuPath si tienes trabajo sin guardar: ciérralo desde su
interfaz.

### Abrí `QuPath-0.7.0 (console).exe` por error

No pasa nada. Es el lanzador de diagnóstico: hace lo mismo pero además muestra
una ventana de consola con los mensajes internos. Ciérrala y abre
`QuPath-0.7.0.exe`.

---

## Recuperación

### Quiero volver al estado anterior

```powershell
.\runtime\update-qupath-es.ps1 -ListBackups
.\runtime\update-qupath-es.ps1 -Rollback
```

O una copia concreta:

```powershell
.\runtime\update-qupath-es.ps1 -Rollback -BackupId 20260902-134500
```

### Quiero quitar la traducción del todo

Ver [`UNINSTALL.md`](UNINSTALL.md).

---

## Recoger información para pedir ayuda

Si vas a abrir una incidencia, adjunta:

1. La salida completa del *dry run*.
2. El registro correspondiente de `logs\`.
3. La versión de QuPath y de PowerShell:

   ```powershell
   $PSVersionTable.PSVersion
   ```

4. El hash del bundle instalado, si existe.

No incluyen datos personales: rutas, versiones y hashes.
