# qupath-es

**Localización al castellano de la interfaz de [QuPath](https://qupath.github.io/).**

Proyecto **no oficial**, sin relación con el equipo de QuPath ni con la
Universidad de Edimburgo. Licencia [GPL-3.0](LICENSE) · procedencia en
[`NOTICE.md`](NOTICE.md).

---

## ¿Qué es esto?

Un paquete de traducción que hace que los menús, paneles, diálogos y
preferencias de QuPath aparezcan en castellano, más las herramientas para
instalarlo, verificarlo y mantenerlo cuando salgan versiones nuevas de QuPath.

### Qué hace

- Instala un fichero de traducción **externo** que QuPath carga al arrancar.
- Detecta la versión de QuPath instalada y comprueba si hay traducción para ella.
- Valida la traducción antes de instalarla.
- Hace copia de seguridad antes de sustituir nada, y permite deshacer.

### Qué NO hace

- **No modifica QuPath.** Ni sus JAR, ni su código, ni su ejecutable, ni su runtime.
- **No descarga ni instala QuPath.** Eso lo haces tú desde la web oficial.
- **No cambia los formatos numéricos.** El separador decimal sigue siendo el
  punto y las mediciones exportadas no varían. Esto es deliberado: cambiarlo
  podría alterar análisis.
- **No toca tus imágenes, proyectos ni resultados.**
- **No cierra QuPath.** Si está abierto cuando hace falta escribir, avisa y se
  detiene.

---

## Versiones soportadas

| Versión QuPath | Estado | Bundle principal | Modo de locale |
| --- | --- | --- | --- |
| **0.7.0** | Estable | **894 / 894** claves | `STARTUP_FALLBACK` |

*Modo de locale* indica cómo se aplica el idioma. En QuPath 0.7.0 el runtime de
Java que acompaña al programa no incluye los datos regionales del español, así
que la preferencia de idioma no se puede guardar entre reinicios; se usa un
pequeño script de arranque que aplica el idioma cada vez. Explicación completa
en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

> **894/894 no significa que toda la aplicación esté en castellano.**
> Ese número es la cobertura del *bundle* principal de la interfaz. QuPath 0.7.0
> contiene además textos escritos directamente en el código, que ninguna
> traducción externa puede alcanzar. Ver
> [limitaciones conocidas](docs/FAQ.md#por-qué-hay-frases-que-siguen-en-inglés).

---

## Empezar

| Quiero… | Ir a |
| --- | --- |
| Instalarlo rápido, ya tengo QuPath | [`docs/QUICK_START.md`](docs/QUICK_START.md) |
| Instalarlo desde cero, paso a paso | [`docs/INSTALLATION.md`](docs/INSTALLATION.md) |
| Instalarlo en otro ordenador | [`docs/THIRD_PARTY_INSTALLATION.md`](docs/THIRD_PARTY_INSTALLATION.md) |
| Actualizar QuPath sin perder el castellano | [`docs/UPDATING_QUPATH_ES.md`](docs/UPDATING_QUPATH_ES.md) |
| QuPath volvió al inglés | [`docs/REPAIR.md`](docs/REPAIR.md) |
| Algo no funciona | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) |
| Quitar la traducción | [`docs/UNINSTALL.md`](docs/UNINSTALL.md) |
| Dudas frecuentes | [`docs/FAQ.md`](docs/FAQ.md) |
| Entender cómo funciona por dentro | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Colaborar o mantener el proyecto | [`docs/MAINTAINER_GUIDE.md`](docs/MAINTAINER_GUIDE.md) |

### Resumen en tres comandos

Con QuPath **cerrado**, en PowerShell:

```powershell
cd C:\qupath-es
.\runtime\update-qupath-es.ps1
```

Ese primer comando es un **diagnóstico que no escribe nada** (*dry run*). Si
informa `Spanish release: AVAILABLE`, instala con:

```powershell
.\runtime\update-qupath-es.ps1 -Apply
```

Si QuPath vuelve al inglés en algún momento:

```powershell
.\runtime\update-qupath-es.ps1 -Repair
```

---

## Requisitos

**Para instalar y usar la traducción:**

- Windows 10 u 11.
- QuPath instalado (versión oficial, desde qupath.github.io).
- PowerShell: sirve **Windows PowerShell 5.1** (el que trae Windows) o
  PowerShell 7.
- **Python 3** en el `PATH`. El actualizador lo usa para detectar la versión de
  QuPath y validar la traducción. Si no quieres instalar Python, existe una
  [instalación manual sin Python](docs/INSTALLATION.md#apéndice-instalación-manual-sin-python).

**Para desarrollar o mantener:**

- Lo anterior, más Git.
- Sin dependencias de terceros: las herramientas usan solo la biblioteca
  estándar de Python.

---

## Estado del proyecto

| Métrica | Valor |
| --- | --- |
| Claves del bundle principal (0.7.0) | 894 |
| `REVIEWED` | 884 |
| `KEEP_EN` (deliberadamente en inglés) | 10 |
| `BLOCKED` / `PENDING` / `DRAFT` | 0 |
| Validador estructural | PASS |
| Auditoría lingüística | SAFE TO INSTALL |
| Suite de pruebas | 141 tests |

Huellas de los artefactos de 0.7.0:

```
base   (inglés canónico)  796EFC44FC23369E4D7BDFDE69C0FA2A702051BF2F9D71399157B505E8D45D2D
dist   (español)          E4A966C90D1CE1368DE9EA21DECC7D9DBB0180087B60D3724690AAD4C128FC19
```

---

## Estructura del repositorio

```
runtime/         actualizador y sondas (lo que ejecuta el usuario)
tools/           motor de traducción, validación y migración (Python)
tests/           141 pruebas
versions/0.7.0/  bundle canónico, traducción, bundle generado e informes
docs/            esta documentación
backups/         copias de seguridad creadas por -Apply (no se borran solas)
logs/            registro de cada ejecución (no versionado)
```

Detalle en [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
