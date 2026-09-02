# Instalar en otro ordenador

Este proyecto se desarrolló en un equipo concreto, así que conviene dejar claro
qué es específico de aquel entorno y qué funciona en cualquier máquina Windows.

**Resumen: nada en los scripts operativos está atado a un usuario concreto.**
La guía de instalación ([`INSTALLATION.md`](INSTALLATION.md)) sirve tal cual en
cualquier ordenador. Este documento explica por qué, y qué rutas de la
documentación son solo ejemplos.

---

## Auditoría de portabilidad

Búsqueda en todo el repositorio de rutas atadas a un usuario o a una máquina.

| Categoría | Qué significa | Dónde aparece |
| --- | --- | --- |
| `INTENTIONAL` | Es un dato de procedencia: registra dónde se capturó un artefacto. Debe conservarse | `versions/0.7.0/fingerprint.json`, `versions/0.7.0/target-version.json` |
| `EXAMPLE_ONLY` | Ruta de ejemplo en documentación o en un informe histórico | Informes de `versions/0.7.0/reports/`, ejemplos de esta documentación |
| `VERSION_SPECIFIC` | Ligado a QuPath 0.7.0 a propósito, no a un usuario | `tools/es_translations.py`, `tools/apply_translations.py` |
| `USER_SPECIFIC_BUG` | Rompería la instalación en otro equipo | **Ninguno** |

**Resultado: cero rutas de usuario fijas en scripts operativos.**

Cómo resuelve cada componente las rutas:

| Componente | Mecanismo |
| --- | --- |
| `runtime/update-qupath-es.ps1` | `[Environment]::GetFolderPath('UserProfile')` |
| `tools/qupath_version_migrator.py` | `Path.home() / "AppData" / "Local"` |
| `versions/*/runtime/*.groovy` | `System.getProperty('user.home')` |
| Raíz del repositorio | Se deriva de `$PSScriptRoot`, no está fijada |

Puedes comprobarlo tú mismo:

```powershell
cd C:\qupath-es
Select-String -Path runtime\*.ps1,runtime\*.groovy,tools\*.py -Pattern 'C:\\Users\\'
```

No debe devolver nada.

Hay además una prueba automática que lo vigila: si alguien introduce una ruta
absoluta de usuario o una variable de entorno global en un script operativo, la
suite falla (`tests/test_runtime_locale.py`).

---

## Rutas que verás en la documentación

Son **ejemplos**. Sustitúyelas por las tuyas.

| Ejemplo en los documentos | Qué es realmente |
| --- | --- |
| `C:\qupath-es` | Donde clonaste o extrajiste este repositorio. Puede ser cualquier carpeta |
| `C:\Users\<usuario>\AppData\Local\QuPath-0.7.0` | Donde instalaste QuPath. En comandos usa `$env:LOCALAPPDATA` |
| `%USERPROFILE%\QuPath` | Tu directorio de usuario de QuPath. Lo crea QuPath al abrirse |

En PowerShell, para ver las tuyas:

```powershell
$env:USERPROFILE
$env:LOCALAPPDATA
```

Los scripts no necesitan que se las digas: las calculan solos. Solo tendrás que
indicar rutas si tienes **varias** instalaciones de QuPath o si instalaste
QuPath fuera de `%LOCALAPPDATA%`:

```powershell
.\runtime\update-qupath-es.ps1 -QuPathPath "D:\Programas\QuPath-0.7.0"
```

---

## Requisitos en una máquina nueva

| Requisito | Comprobación | Si falta |
| --- | --- | --- |
| Windows 10 u 11 | — | Los scripts son para Windows |
| PowerShell 5.1 o 7 | `$PSVersionTable.PSVersion` | Windows 10/11 ya traen 5.1 |
| QuPath 0.7.0 | Abrirlo una vez | [qupath.github.io](https://qupath.github.io/) |
| Python 3 en el `PATH` | `python --version` | O usa la [instalación manual](INSTALLATION.md#apéndice-instalación-manual-sin-python) |
| Git (opcional) | `git --version` | Puedes descargar el ZIP |

El actualizador se ha probado con **Windows PowerShell 5.1** y con
**PowerShell 7**. No usa sintaxis exclusiva de PowerShell 7, y hay una prueba
automática que lo verifica.

Las herramientas Python usan **solo la biblioteca estándar**: no hay que
instalar paquetes. Requieren Python 3.7 o superior por el uso de
`from __future__ import annotations`; se han desarrollado y probado con Python
3.14.

---

## Permisos

No hace falta ser administrador:

- la traducción se instala en tu perfil de usuario;
- las preferencias se registran a través de QuPath, en la parte del registro
  correspondiente al usuario actual (`HKCU`);
- no se modifican variables de entorno del sistema ni de la máquina.

Si tu organización restringe la ejecución de scripts:

```powershell
powershell -ExecutionPolicy Bypass -File .\runtime\update-qupath-es.ps1
```

Afecta solo a esa ejecución.

---

## Varios usuarios en el mismo ordenador

La traducción se instala **por usuario**, porque vive en el directorio de
usuario de QuPath. Cada persona debe ejecutar la instalación en su propia
sesión. El repositorio puede estar en una carpeta compartida y ser de solo
lectura para ellos: el actualizador solo escribe en `backups\` y `logs\`, así
que si el repositorio es de solo lectura, cópialo a una carpeta con permiso de
escritura.

---

## Despliegue en varios equipos

Procedimiento sugerido:

1. Verifica en cada equipo que la versión de QuPath es la misma:

   ```powershell
   .\runtime\update-qupath-es.ps1
   ```

   Comprueba la línea `Detected QuPath` y `GUI jar SHA-256`. Si el hash del JAR
   difiere entre equipos, no es la misma compilación.

2. Instala:

   ```powershell
   .\runtime\update-qupath-es.ps1 -Apply
   ```

3. Registra en cada equipo: versión de QuPath, hash del bundle instalado y
   fecha. El registro de `logs\` ya contiene todo eso.

No hay instalador desatendido: cada `-Apply` comprueba que QuPath esté cerrado,
lo cual requiere una persona. Es deliberado.
