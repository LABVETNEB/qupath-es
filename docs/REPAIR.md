# QuPath volvió al inglés

Guía específica para el fallo más frecuente: la traducción estaba funcionando y
de repente la interfaz aparece en inglés.

---

## Causa más habitual

QuPath guarda dos preferencias de las que depende el castellano:

| Preferencia | Para qué sirve |
| --- | --- |
| **directorio de usuario** (`userPath`) | Le dice a QuPath dónde buscar el fichero de traducción |
| **script de arranque** (`startupScriptPath`) | Aplica el idioma español cada vez que arranca |

Un **restablecimiento de preferencias** borra ambas. Puede ocurrir por:

- pulsar *Editar → Restablecer preferencias* en QuPath;
- arrancar QuPath con la opción `--reset`;
- experimentar con las opciones de *Idioma y región*.

Al perderse esas preferencias, QuPath deja de encontrar la traducción y vuelve
al inglés. **Los ficheros siguen en su sitio**: solo se perdió la configuración
que los conecta.

---

## Solución

Con QuPath **cerrado**:

```powershell
cd C:\qupath-es
.\runtime\update-qupath-es.ps1 -Repair
```

Salida esperada:

```
Repair
======
Re-registering QuPath preferences (user directory, startup script)...
Preferences restored.
```

Abre QuPath. Debería volver a estar en castellano.

`-Repair` **no reinstala nada** que ya esté bien: solo vuelve a registrar las
preferencias que faltan.

---

## Antes de reparar: diagnóstico

Si prefieres ver qué pasa antes de tocar nada:

```powershell
cd C:\qupath-es
.\runtime\update-qupath-es.ps1
```

Fíjate en la sección **Locale capability**. Si aparece:

```
QuPath preferences look incomplete (user directory or startup script unset).
Run with -Repair to restore them.
```

es exactamente este caso.

---

## Tabla de síntomas

| Síntoma | Causa probable | Diagnóstico | Solución |
| --- | --- | --- | --- |
| Todo en inglés de golpe, antes funcionaba | Preferencias restablecidas | El diagnóstico avisa de preferencias incompletas | `-Repair` |
| Todo en inglés tras actualizar QuPath | Versión nueva sin traducción, o preferencias nuevas | El diagnóstico muestra otra versión detectada | Ver [UPDATING_QUPATH_ES.md](UPDATING_QUPATH_ES.md) |
| Todo en inglés y el fichero no está | Se borró el bundle | El diagnóstico dice `Installed bundle: not installed` | `-Apply` |
| Menús en castellano pero *algunas* frases en inglés | Comportamiento normal de 0.7.0 | — | Nada que reparar, ver [FAQ](FAQ.md#por-qué-hay-frases-que-siguen-en-inglés) |
| Los números pasaron a usar coma decimal | Se cambió *Idioma principal* o *Fechas y números* | *Preferencias → Idioma y región* | Poner ambos en `English (United States)` |

---

## Si `-Repair` dice que faltan ficheros

```
Missing files - run -Apply first:
  bundle: ...\QuPath\localization\qupath-gui-strings_es.properties
```

Significa que no es un problema de preferencias sino de instalación. Ejecuta:

```powershell
.\runtime\update-qupath-es.ps1 -Apply
```

---

## Si `-Repair` no arregla nada

1. Comprueba que estás abriendo `QuPath-0.7.0.exe` y no otra instalación de
   QuPath que tengas en el equipo.
2. Ejecuta el diagnóstico y comprueba que `Detected QuPath` coincide con la
   versión que abres.
3. Si hay varias instalaciones, indica cuál:

   ```powershell
   .\runtime\update-qupath-es.ps1 -QuPathPath "C:\ruta\a\QuPath-0.7.0"
   ```

4. Consulta [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).

---

## Volver atrás

Si algo quedó peor que antes, cada `-Apply` deja una copia de seguridad:

```powershell
.\runtime\update-qupath-es.ps1 -ListBackups
.\runtime\update-qupath-es.ps1 -Rollback
```

Las copias **nunca** se borran automáticamente.
