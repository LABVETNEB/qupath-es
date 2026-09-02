# Desinstalar o revertir

Hay tres cosas distintas que se pueden deshacer. Elige la que necesitas: no
hace falta borrar QuPath para quitar el castellano.

| Quiero… | Nivel |
| --- | --- |
| Volver a ver QuPath en inglés, conservando todo instalado | [Nivel A](#nivel-a--volver-al-inglés) |
| Quitar la traducción del ordenador | [Nivel B](#nivel-b--quitar-la-traducción) |
| Desinstalar QuPath | [Nivel C](#nivel-c--desinstalar-qupath) |

Ninguno de estos pasos toca tus imágenes, proyectos ni resultados.

---

## Nivel A · Volver al inglés

La opción menos invasiva. Todo sigue instalado y puedes volver al castellano
cuando quieras.

Con QuPath cerrado, desactiva el script de arranque:

1. Abre QuPath.
2. *Editar → Preferencias → General → Startup script path*.
3. Borra el valor (déjalo vacío).
4. Cierra y vuelve a abrir QuPath.

QuPath arrancará en inglés. El fichero de traducción sigue en su sitio.

Para volver al castellano, ejecuta:

```powershell
cd C:\qupath-es
.\runtime\update-qupath-es.ps1 -Repair
```

### Alternativa: restaurar una copia de seguridad

Si lo que quieres es volver al estado anterior a la última instalación:

```powershell
cd C:\qupath-es
.\runtime\update-qupath-es.ps1 -ListBackups
.\runtime\update-qupath-es.ps1 -Rollback
```

---

## Nivel B · Quitar la traducción

Deja QuPath exactamente como una instalación limpia.

Con QuPath **cerrado**:

```powershell
Remove-Item "$env:USERPROFILE\QuPath\localization\qupath-gui-strings_es.properties"
Remove-Item "$env:USERPROFILE\QuPath\scripts\qupath-es-startup.groovy"
```

Después, dentro de QuPath, vacía *Preferencias → General → Startup script path*
si tenía valor.

### Qué borra y qué no

| Se borra | No se toca |
| --- | --- |
| El fichero de traducción español | QuPath y sus JAR |
| El script de arranque del idioma | Tus proyectos e imágenes |
| — | El resto de tus preferencias de QuPath |
| — | Las copias de seguridad en `backups\` |

### Eliminar también el repositorio

Si ya no vas a mantener el proyecto en este ordenador, borra la carpeta
`C:\qupath-es` desde el Explorador de archivos.

> Antes de borrarla, comprueba que no contiene trabajo tuyo sin publicar
> (traducciones en curso en `versions\*\work\`, o copias en `backups\`).

---

## Nivel C · Desinstalar QuPath

**Solo si quieres eliminar el programa**, no la traducción.

Usa el desinstalador de Windows:

*Configuración → Aplicaciones → Aplicaciones instaladas → QuPath → Desinstalar*

Eso elimina el programa. **No** elimina:

- tu directorio de usuario de QuPath (`%USERPROFILE%\QuPath`), con tus scripts,
  extensiones y la traducción;
- tus proyectos e imágenes;
- tus preferencias.

Si además quieres eliminar el directorio de usuario, bórralo a mano después de
comprobar que no contiene nada que quieras conservar:

```
%USERPROFILE%\QuPath
```

---

## Comprobar que quedó limpio

```powershell
Test-Path "$env:USERPROFILE\QuPath\localization\qupath-gui-strings_es.properties"
Test-Path "$env:USERPROFILE\QuPath\scripts\qupath-es-startup.groovy"
```

Ambos deben devolver `False`.

Abre QuPath: la interfaz debe estar en inglés y los menús mostrar
`File  Edit  Tools  View  …`.

---

## Volver a instalar más adelante

Todo el proceso es reversible. Para reinstalar:

```powershell
cd C:\qupath-es
.\runtime\update-qupath-es.ps1
.\runtime\update-qupath-es.ps1 -Apply
```
