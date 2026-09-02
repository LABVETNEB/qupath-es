# Instalación desde cero

Guía completa para un ordenador Windows donde todavía no hay nada preparado.
Está escrita para alguien que no ha participado en el desarrollo del proyecto.

Si ya tienes QuPath y el repositorio, usa el
[inicio rápido](QUICK_START.md).

---

## Qué vas a instalar

Dos cosas separadas:

1. **QuPath**, el programa, desde su web oficial. Nosotros no lo distribuimos.
2. **qupath-es**, este paquete de traducción, que se instala *junto* a QuPath
   sin modificarlo.

---

## Requisitos previos

| Requisito | Por qué | Cómo comprobarlo |
| --- | --- | --- |
| Windows 10 u 11 | Los scripts son PowerShell para Windows | — |
| PowerShell | Ejecuta el actualizador. Sirve el que trae Windows (5.1) | `$PSVersionTable.PSVersion` |
| Python 3 | El actualizador lo usa para identificar la versión de QuPath y validar la traducción | `python --version` |

Si no tienes Python y no quieres instalarlo, hay una
[instalación manual](#apéndice-instalación-manual-sin-python) al final.

No hace falta ser administrador: todo se escribe dentro de tu perfil de usuario.

---

## Paso 1 · Instalar QuPath

Descarga el instalador oficial desde <https://qupath.github.io/> e instálalo.

**Este proyecto soporta actualmente QuPath 0.7.0.** Si instalas otra versión, el
actualizador lo detectará y te dirá que aún no hay traducción para ella, en vez
de instalar algo incompatible.

Anota dónde queda instalado. La ubicación habitual es:

```
%LOCALAPPDATA%\QuPath-0.7.0
```

que en la práctica es `C:\Users\<tu-usuario>\AppData\Local\QuPath-0.7.0`.

**Abre QuPath una vez y ciérralo.** Así crea su directorio de usuario, que es
donde se instalará la traducción.

## Paso 2 · Obtener qupath-es

Dos opciones.

### Opción A · Con Git (recomendada si vas a actualizar)

```powershell
cd C:\
git clone https://github.com/LABVETNEB/qupath-es.git
```

Queda en `C:\qupath-es`.

### Opción B · Descargando el ZIP

1. Abre <https://github.com/LABVETNEB/qupath-es>.
2. Botón verde **Code** → **Download ZIP**.
3. Extrae el ZIP.
4. Renombra/mueve la carpeta resultante a una ruta **simple y sin espacios**.
   Se recomienda `C:\qupath-es`.

> La ruta `C:\qupath-es` es una recomendación, no una obligación: los scripts
> calculan sus propias rutas. Si usas otra, sustitúyela en todos los comandos.

## Paso 3 · Abrir PowerShell

Clic derecho en **Inicio** → **Terminal** (Windows 11) o
**Windows PowerShell** (Windows 10).

Si al ejecutar un script aparece un error de directivas de ejecución, usa:

```powershell
powershell -ExecutionPolicy Bypass -File .\runtime\update-qupath-es.ps1
```

Eso afecta solo a esa ejecución; no cambia la configuración del sistema.

## Paso 4 · Entrar al repositorio

```powershell
cd C:\qupath-es
```

## Paso 5 · Ejecutar el diagnóstico

**Cierra QuPath antes.**

```powershell
.\runtime\update-qupath-es.ps1
```

Es un *dry run*: **no escribe nada**. Solo detecta, comprueba e informa.

## Paso 6 · Interpretar el resultado

### Caso A · `Spanish release: AVAILABLE`

```
Detected QuPath:    0.7.0
Spanish release:    AVAILABLE
Bundle validation:  PASS
```

Tu versión está soportada. Continúa al paso 7.

### Caso B · `Spanish package for X.Y.Z: NOT READY`

Tu versión de QuPath es más nueva (o distinta) y todavía no tiene traducción
publicada. **No instales nada.** El actualizador no lo permitirá, y hace bien:
copiar una traducción de otra versión puede dejar la interfaz a medias o con
errores.

Opciones:

- Instalar QuPath 0.7.0, que sí está soportada; o
- preparar la migración si vas a mantener el proyecto, ver
  [`UPDATING_QUPATH_ES.md`](UPDATING_QUPATH_ES.md) y
  [`MAINTAINER_GUIDE.md`](MAINTAINER_GUIDE.md).

## Paso 7 · Instalar

Solo si el paso 6 dio `AVAILABLE`:

```powershell
.\runtime\update-qupath-es.ps1 -Apply
```

Qué hace, en orden:

1. Vuelve a validar la traducción. Si falla, **no instala**.
2. Comprueba que QuPath no esté abierto. Si lo está, se detiene y te pide
   cerrarlo a mano.
3. Crea una copia de seguridad en `backups\<fecha-hora>\`.
4. Copia el fichero de traducción al directorio de usuario de QuPath.
5. Recalcula el hash del fichero instalado y lo compara con el original.
6. Instala el script de arranque del idioma (necesario en 0.7.0) y registra
   las preferencias de QuPath.

## Paso 8 · Abrir QuPath

Abre **`QuPath-0.7.0.exe`**.

### Los dos ejecutables de QuPath

| Ejecutable | Para qué | ¿Uso normal? |
| --- | --- | --- |
| `QuPath-0.7.0.exe` | El programa | **Sí** |
| `QuPath-0.7.0 (console).exe` | Abre además una ventana de consola con los mensajes internos. Es el que usan las herramientas de diagnóstico de este proyecto | No |

Si abres el de consola por error, verás una ventana negra con texto. No pasa
nada: ciérrala y abre el normal.

## Paso 9 · Validación visual

Comprueba la barra de menús:

```
Archivo  Editar  Herramientas  Ver  Objetos  TMA  Medir
Automatizar  Analizar  Clasificar  Extensiones  Ventana  Ayuda
```

Y las pestañas del panel de análisis, a la izquierda:

```
Proyecto  Imagen  Anotaciones  Jerarquía  Flujo de trabajo
```

Abre también *Editar → Preferencias*: las categorías deben estar en castellano
(*Apariencia*, *General*, *Idioma y región*, *Visor*…).

### Comprobación importante: los números

Abre una imagen con calibración y mira el tamaño de píxel en la pestaña
*Imagen*. Debe mostrarse con **punto** decimal (`0.5`), no con coma.

Esto es deliberado: la traducción cambia **solo el idioma de la interfaz** y
deja intactos los formatos numéricos, para no alterar mediciones ni las
exportaciones a CSV.

---

## Qué queda en inglés, y por qué

El bundle principal está traducido al 100 % (894 de 894 claves). Aun así verás
frases en inglés. **No es un fallo de la instalación.**

QuPath 0.7.0 tiene textos escritos directamente dentro de su código, no en el
fichero de traducción. Ninguna traducción externa puede alcanzarlos. Ejemplos
confirmados en la pantalla inicial:

- `Image list`
- `Search entry in project`
- `Drag & drop an image file or project folder`

Además quedan fuera los diálogos de parámetros de los algoritmos (detección
celular, teselado, superpíxeles…), los nombres de algunos plugins, otras
extensiones con su propio fichero de idioma, y los botones estándar del sistema.

Distingue siempre dos cosas:

| Métrica | Qué mide | Valor en 0.7.0 |
| --- | --- | --- |
| **Cobertura del bundle principal** | Claves del fichero de traducción traducidas | 894 / 894 |
| **Cobertura de la aplicación** | Texto visible total en castellano | aproximadamente 50–60 % |

Detalle en [`FAQ.md`](FAQ.md) y en
`versions/0.7.0/reports/localization-coverage.md`.

---

## Apéndice: instalación manual sin Python

Si no puedes instalar Python, puedes hacerlo a mano. Pierdes la validación
automática y la detección de versión, así que **asegúrate de que tu QuPath es
exactamente 0.7.0**.

1. Localiza tu directorio de usuario de QuPath. Normalmente:

   ```
   %USERPROFILE%\QuPath
   ```

2. Crea la carpeta `localization` dentro si no existe.

3. Copia el fichero:

   ```
   versions\0.7.0\dist\qupath-gui-strings_es.properties
   ```

   a:

   ```
   %USERPROFILE%\QuPath\localization\qupath-gui-strings_es.properties
   ```

4. Copia el script de arranque:

   ```
   versions\0.7.0\runtime\qupath-es-startup.groovy
   ```

   a:

   ```
   %USERPROFILE%\QuPath\scripts\qupath-es-startup.groovy
   ```

5. Abre QuPath y ve a *Edit → Preferences → General → Startup script path*.
   Selecciona el script que acabas de copiar.

6. Ve a *Preferences → Extensions → QuPath user directory* y comprueba que
   apunta a `%USERPROFILE%\QuPath`.

7. Reinicia QuPath.

Para verificar que el fichero copiado es el correcto, su SHA-256 debe ser:

```
E4A966C90D1CE1368DE9EA21DECC7D9DBB0180087B60D3724690AAD4C128FC19
```

Puedes comprobarlo con:

```powershell
Get-FileHash "$env:USERPROFILE\QuPath\localization\qupath-gui-strings_es.properties" -Algorithm SHA256
```

---

## Siguientes pasos

- [Actualizar QuPath en el futuro](UPDATING_QUPATH_ES.md)
- [Si vuelve al inglés](REPAIR.md)
- [Problemas frecuentes](TROUBLESHOOTING.md)
- [Desinstalar](UNINSTALL.md)
