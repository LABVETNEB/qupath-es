# Preguntas frecuentes

## Sobre el proyecto

### ¿Es un proyecto oficial de QuPath?

No. Es un proyecto independiente, sin relación con el equipo de QuPath ni con
la Universidad de Edimburgo. Se distribuye bajo [GPL-3.0](../LICENSE) porque
deriva de recursos de QuPath, que también es GPL-3.0. Ver
[`NOTICE.md`](../NOTICE.md).

### ¿Modifica QuPath?

No. No se toca ningún JAR, ni el código, ni el ejecutable, ni el runtime de
Java. La traducción se instala como un fichero externo, en tu directorio de
usuario, usando un mecanismo que QuPath ofrece precisamente para esto.

### ¿Puede romper mis proyectos?

No. La traducción solo cambia texto de la interfaz. No toca proyectos, imágenes
ni datos.

### ¿Modifica mis imágenes o mis análisis?

No. No interviene en el procesamiento de imágenes ni en los algoritmos.

### ¿Cambia el separador decimal?

**No, y es deliberado.** QuPath distingue tres configuraciones regionales:
idioma principal, idioma de interfaz, y formato de fechas y números. Este
proyecto cambia **solo la de interfaz**. Las otras dos se quedan en
`English (United States)`, así que el separador decimal sigue siendo el punto y
las exportaciones CSV no cambian.

Si en algún momento ves comas decimales, alguien cambió *Idioma principal* o
*Fechas y números* a mano. Ver [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

---

## Cobertura

### ¿Por qué hay frases que siguen en inglés?

Porque no todas las frases de QuPath están en el fichero de traducción.

Hay que distinguir dos cosas:

| Métrica | Qué mide | Valor en 0.7.0 |
| --- | --- | --- |
| **Cobertura del bundle principal** | Cuántas claves del fichero de traducción están traducidas | **894 / 894** |
| **Cobertura de la aplicación** | Cuánto del texto visible total aparece en castellano | aproximadamente **50–60 %** |

Lo que queda fuera:

1. **Textos escritos dentro del código de QuPath.** En 0.7.0, por ejemplo
   `Image list`, `Search entry in project` y
   `Drag & drop an image file or project folder`. No son claves de traducción:
   están compilados. Se externalizaron en versiones posteriores.
2. **Diálogos de parámetros de los algoritmos** (detección celular, teselado,
   superpíxeles, características de forma…). Es el bloque más grande.
3. **Nombres y descripciones de algunos plugins**, que se usan como texto de menú.
4. **Otras extensiones** con su propio fichero de idioma (OpenSlide, el ejecutor
   de scripts de ImageJ, Deep Java Library…).
5. **Botones estándar** (*OK*, *Cancel*, *Yes*, *No*) y los diálogos de archivo
   del sistema operativo.

El detalle, con números medidos sobre los JAR instalados, está en
`versions/0.7.0/reports/localization-coverage.md`.

### ¿Se puede traducir el resto?

Los puntos 1 a 3 requieren cambios en el propio QuPath: no hay forma de
alcanzarlos desde un fichero externo. El punto 4 necesitaría un fichero de
traducción por extensión. El punto 5 depende de Java y del sistema operativo.

### ¿894/894 significa que está todo traducido?

Significa que el fichero de traducción principal está completo. No significa
que toda la aplicación esté en castellano. Ver arriba.

---

## Uso

### ¿Puedo usarlo con otra versión de QuPath?

Solo con las versiones que tengan traducción publicada. Ahora mismo, **0.7.0**.

Si instalas otra versión, el actualizador la detectará y dirá `NOT READY` en
lugar de instalar algo incompatible. No copies el fichero a mano entre
versiones: las claves cambian entre releases.

### ¿Qué pasa cuando actualizo QuPath?

Ejecutas el actualizador y él decide. Ver
[`UPDATING_QUPATH_ES.md`](UPDATING_QUPATH_ES.md).

Resumen: si la versión nueva está soportada, `-Apply`. Si no, el actualizador
prepara el trabajo de migración pero **no instala una traducción parcial**.

### ¿Puedo volver al inglés?

Sí, en cualquier momento y sin desinstalar nada. Ver
[`UNINSTALL.md`](UNINSTALL.md).

### ¿Puedo instalarlo en otro ordenador?

Sí. Nada está atado a un usuario concreto. Ver
[`THIRD_PARTY_INSTALLATION.md`](THIRD_PARTY_INSTALLATION.md).

### ¿Por qué hace falta un script de arranque?

Porque el runtime de Java que acompaña a QuPath 0.7.0 en Windows no incluye los
datos regionales del español. Sin ellos, QuPath no puede **guardar** el español
como idioma de interfaz: al reiniciar se pierde. El script lo aplica en cada
arranque.

Es específico de esta versión. El actualizador **mide** cada instalación: si una
versión futura corrige el runtime, dejará de instalar el script y bastará con
seleccionar el idioma en las preferencias.

### ¿Puedo elegir español desde las preferencias de QuPath?

En 0.7.0 no aparece en la lista, por lo anterior. El script de arranque lo
aplica por ti.

---

## Requisitos

### ¿Necesito Python?

Para el actualizador, **sí**: lo usa para identificar la versión de QuPath y
validar la traducción antes de instalarla.

Si no puedes instalarlo, hay una
[instalación manual](INSTALLATION.md#apéndice-instalación-manual-sin-python) que
no lo requiere, a cambio de perder esas comprobaciones.

### ¿Qué versión de Python?

Python 3.7 o superior. Las herramientas usan **solo la biblioteca estándar**: no
hay que instalar paquetes. Se han desarrollado y probado con Python 3.14.

### ¿Necesito Git?

No. Puedes descargar el repositorio como ZIP desde GitHub. Git es cómodo si
quieres recibir actualizaciones del proyecto.

### ¿Necesito PowerShell 7?

No. Funciona con **Windows PowerShell 5.1**, el que viene con Windows 10 y 11.
También funciona con PowerShell 7. Ambos están probados.

### ¿Necesito permisos de administrador?

No.

---

## Seguridad y confianza

### ¿Cómo sé que el fichero instalado es el correcto?

Cada instalación verifica el hash SHA-256 después de copiar y aborta si no
coincide. Puedes comprobarlo tú:

```powershell
Get-FileHash "$env:USERPROFILE\QuPath\localization\qupath-gui-strings_es.properties" -Algorithm SHA256
```

Para 0.7.0 debe dar:

```
E4A966C90D1CE1368DE9EA21DECC7D9DBB0180087B60D3724690AAD4C128FC19
```

### ¿El script puede cerrar QuPath o apagar el equipo?

No. No contiene ninguna orden de cerrar procesos, reiniciar ni apagar, y hay
pruebas automáticas que lo verifican. Si QuPath está abierto cuando hace falta
escribir, se detiene y te pide cerrarlo tú.

### ¿Qué se guarda en los registros?

Fecha, versión de QuPath, rutas, hashes, acciones y resultado. Sin datos
personales. Están en `logs\` y no se suben al repositorio.

### ¿Se puede deshacer una instalación?

Sí. Cada `-Apply` crea antes una copia en `backups\<fecha-hora>\`, y las copias
no se borran automáticamente:

```powershell
.\runtime\update-qupath-es.ps1 -ListBackups
.\runtime\update-qupath-es.ps1 -Rollback
```

---

## Colaborar

### ¿Puedo corregir una traducción?

Sí. No edites el fichero `.properties`: se genera. Ver
[`MAINTAINER_GUIDE.md`](MAINTAINER_GUIDE.md).

### ¿Puedo añadir otro idioma?

La arquitectura lo permitiría —el mecanismo de QuPath admite cualquier
`_xx.properties`—, pero este repositorio está organizado en torno al castellano.
Habría que generalizar las herramientas.
