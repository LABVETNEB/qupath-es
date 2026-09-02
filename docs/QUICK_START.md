# Inicio rápido

Para quien ya tiene **QuPath 0.7.0 instalado** y el repositorio `qupath-es`
descargado. Si partes de cero, usa
[`INSTALLATION.md`](INSTALLATION.md).

Tiempo estimado: 5 minutos.

---

## Antes de empezar

- [ ] QuPath **cerrado**. El actualizador se niega a escribir si está abierto.
- [ ] Sabes dónde está el repositorio. Los ejemplos usan `C:\qupath-es`; si lo
      tienes en otro sitio, cambia esa ruta.
- [ ] Python 3 disponible. Compruébalo con `python --version`.

---

## 1. Abrir PowerShell

Clic derecho en el botón **Inicio** → **Terminal** (Windows 11) o
**Windows PowerShell** (Windows 10).

No hace falta ejecutarlo como administrador: todo ocurre dentro de tu perfil de
usuario.

## 2. Entrar al repositorio

```powershell
cd C:\qupath-es
```

## 3. Diagnóstico (no escribe nada)

```powershell
.\runtime\update-qupath-es.ps1
```

Esto es un **dry run**: solo mira y te informa.

Salida esperada (los hashes son largos; aquí se abrevian):

```
QuPath Spanish Update Manager
=============================
Detected QuPath:    0.7.0
Installation:       ...\AppData\Local\QuPath-0.7.0
Version evidence:   jar_name=0.7.0, manifest=0.7.0, directory_name=0.7.0

Spanish package
===============
Declared status:    stable
Canonical bundle:   894 keys
Translation states: REVIEWED=884  KEEP_EN=10
Spanish release:    AVAILABLE
Bundle validation:  PASS

Locale capability
=================
Locale mode:        LOCALE_MODE_STARTUP_FALLBACK

Dry run
=======
Action that WOULD be performed: back up the current bundle and install this release.

No files were installed.
```

**Lo que importa es la línea `Spanish release:`**

| Dice | Significa | Siguiente paso |
| --- | --- | --- |
| `AVAILABLE` | Hay traducción validada para tu versión | Continúa al paso 4 |
| `NOT READY` | Tu versión de QuPath aún no está traducida | Ver [actualizaciones](UPDATING_QUPATH_ES.md) |

## 4. Instalar

```powershell
.\runtime\update-qupath-es.ps1 -Apply
```

Esto:

1. comprueba otra vez que la traducción es válida;
2. hace una copia de seguridad en `backups\<fecha-hora>\`;
3. copia el fichero de traducción a tu directorio de usuario de QuPath;
4. verifica que la copia tiene el mismo hash que el original;
5. instala el script de arranque del idioma y registra las preferencias.

## 5. Abrir QuPath

Abre **`QuPath-0.7.0.exe`**.

> No abras `QuPath-0.7.0 (console).exe`. Ese es el lanzador de diagnóstico:
> abre una ventana de consola y lo usan las herramientas internas. Para el uso
> normal siempre el primero.

## 6. Comprobar

La barra de menús debe mostrar:

```
Archivo  Editar  Herramientas  Ver  Objetos  TMA  Medir
Automatizar  Analizar  Clasificar  Extensiones  Ventana  Ayuda
```

Y las pestañas del panel de análisis:

```
Proyecto  Imagen  Anotaciones  Jerarquía  Flujo de trabajo
```

Si lo ves así, ya está.

---

## Verificación adicional (opcional)

Vuelve a ejecutar el diagnóstico:

```powershell
.\runtime\update-qupath-es.ps1
```

Ahora debería decir:

```
The installed bundle already matches this release.
Action that WOULD be performed: none
```

Y comprueba que **los números no han cambiado**: abre una imagen y mira el
tamaño de píxel en la pestaña *Imagen*. Debe usar **punto** decimal
(`0.5`, no `0,5`). Si usa coma, algo modificó el locale de formato; ver
[TROUBLESHOOTING](TROUBLESHOOTING.md).

---

## Algunas frases siguen en inglés

Es lo esperado, no un fallo de instalación. QuPath 0.7.0 tiene textos escritos
directamente en su código que ninguna traducción externa puede cambiar, por
ejemplo `Image list`, `Search entry in project` y
`Drag & drop an image file or project folder`.

Explicación en la [FAQ](FAQ.md#por-qué-hay-frases-que-siguen-en-inglés).

---

## Si algo falla

- QuPath sigue en inglés → [`REPAIR.md`](REPAIR.md)
- Cualquier otro problema → [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
- Quitar la traducción → [`UNINSTALL.md`](UNINSTALL.md)
