# Actualizar QuPath conservando el castellano

Esta guía explica qué hacer cuando instalas una versión nueva de QuPath.

**Este sistema no descarga ni instala QuPath.** Tú instalas la versión oficial;
después este actualizador adapta la localización española de forma segura.

---

## Caso normal: la versión ya está soportada

1. Instala la nueva versión oficial de QuPath.
2. **Cierra QuPath.**
3. Abre PowerShell.
4. `cd C:\qupath-es`
5. Ejecuta el diagnóstico:

```bash
.\runtime\update-qupath-es.ps1
```

Verás algo así:

```
Detected QuPath:    0.7.0
Spanish release:    AVAILABLE
Bundle validation:  PASS
Locale mode:        LOCALE_MODE_STARTUP_FALLBACK

Dry run
=======
Installed bundle:   E4A966C9...
The installed bundle already matches this release.

No files were installed.
```

6. Si hace falta instalar o reinstalar:

```bash
.\runtime\update-qupath-es.ps1 -Apply
```

7. Abre QuPath. La interfaz debe salir en castellano.

---

## Caso: versión nueva todavía no traducida

El diagnóstico dirá `Spanish package for X.Y.Z: NOT READY`.

Prepara el espacio de trabajo de migración:

```bash
.\runtime\update-qupath-es.ps1 -PrepareMigration
```

Esto:

- extrae el bundle inglés canónico **del JAR instalado** (no de Internet);
- calcula su huella y la registra en `versions\<nueva>\fingerprint.json`;
- compara clave por clave con la versión anterior;
- construye `versions\<nueva>\work\translation.tsv` reutilizando **solo** lo que
  es seguro reutilizar;
- genera un informe en `versions\<nueva>\reports\migration-from-<anterior>.md`.

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

Workspace prepared: C:\qupath-es\versions\0.8.0

Next action: review/translate 70 entries before release.
No files were installed.
```

**Importante:** una traducción parcial **nunca** se instala como release. Hasta
que no queden entradas `PENDING`, `DRAFT` ni `BLOCKED`, y el validador dé PASS,
`-Apply` se negará a instalar. Mientras tanto sigues usando la versión anterior
de QuPath con su castellano, o QuPath nuevo en inglés.

La traducción de las entradas nuevas es trabajo lingüístico y se hace en una
sesión de desarrollo (ver `README.md`), no desde este script.

---

## Si la interfaz vuelve al inglés de golpe

Casi siempre es porque QuPath perdió las preferencias (un *Reset preferences*
las borra). Repáralo sin reinstalar nada:

```bash
.\runtime\update-qupath-es.ps1 -Repair
```

---

## Volver atrás

```bash
.\runtime\update-qupath-es.ps1 -ListBackups
.\runtime\update-qupath-es.ps1 -Rollback
.\runtime\update-qupath-es.ps1 -Rollback -BackupId 20260902-134500
```

Cada `-Apply` crea antes una copia de seguridad en `backups\<timestamp>\`. Las
copias **nunca** se borran automáticamente.

Para volver al inglés sin tocar nada más: borra
`%USERPROFILE%\QuPath\localization\qupath-gui-strings_es.properties`, o desactiva
el script de arranque en *Preferences → General → Startup script path*.

---

## Todos los comandos

| Comando | Qué hace |
| --- | --- |
| `.\runtime\update-qupath-es.ps1` | Diagnóstico. **No escribe nada.** |
| `-Apply` | Instala el bundle español ya validado |
| `-PrepareMigration` | Captura una versión nueva y construye el espacio de migración |
| `-Repair` | Restaura las preferencias perdidas |
| `-CreateShortcut` | Crea el acceso directo «QuPath Español» |
| `-RemoveShortcut` | Elimina ese acceso directo |
| `-StartMenu` | Con los dos anteriores, actúa también sobre el menú Inicio |
| `-Rollback` | Restaura la copia de seguridad más reciente |
| `-ListBackups` | Lista las copias disponibles |
| `-Version 0.8.0` | Fuerza una versión concreta |
| `-QuPathPath "C:\..."` | Apunta a una instalación concreta |
| `-BackupId <id>` | Elige la copia a restaurar |
| `-Force` | Permite recapturar una versión ya capturada. **Nunca** salta la validación |

---

## Qué garantiza el actualizador

- **Nunca** modifica los JAR de QuPath, su código fuente ni su ejecutable.
- **Nunca** cierra QuPath. Si está abierto, aborta y te pide cerrarlo a mano.
- **Nunca** descarga ni instala QuPath.
- **Nunca** instala una traducción que no haya pasado el validador.
- **Nunca** copia a ciegas la traducción anterior sobre una versión nueva.
- Solo escribe en el directorio de usuario de QuPath, y solo con `-Apply`.
- Cada ejecución deja un registro en `logs\`.

---

## Política de migración (resumen)

Para cada clave de la versión nueva:

| Situación | Estado resultante | Se reutiliza |
| --- | --- | --- |
| La clave existe y el inglés es **idéntico** | `REVIEWED` | Sí, automáticamente |
| Era `KEEP_EN` y el inglés no cambió | `KEEP_EN` | Sí |
| El inglés **cambió** | `DRAFT` + `SOURCE_CHANGED` | Solo como referencia |
| Era `KEEP_EN` y el inglés cambió | `DRAFT` + `KEEP_EN_NEEDS_REVIEW` | Solo como referencia |
| Cambió la firma de *placeholders* | `BLOCKED` + `PLACEHOLDER_SIGNATURE_CHANGED` | No |
| Cambiaron los escapes o la estructura | `BLOCKED` + `STRUCTURE_CHANGED` | No |
| Clave nueva | `PENDING` | No |
| Clave eliminada | Archivada en `work\retired.tsv` | No se añade |

La firma de *placeholders* compara los marcadores `MessageFormat` (`{0}`,
`{0,number}`) como multiconjunto —reordenarlos es seguro— y los de
`java.util.Formatter` (`%s`, `%d`, `%1$s`, `%n`, `%%`) como secuencia ordenada,
porque son posicionales salvo que lleven índice explícito.

Cuando una versión nueva externaliza una cadena que en 0.7.0 estaba *hardcoded*,
el migrador adjunta la traducción española conocida como **sugerencia**, pero la
entrada sigue en `PENDING`: una sugerencia no es una aprobación.

---

## Modo de locale

El actualizador **mide** las capacidades de cada instalación en lugar de
suponerlas:

- `LOCALE_MODE_NATIVE` — el runtime conoce el español y QuPath puede guardar la
  preferencia. Se selecciona el idioma en *Preferences → Language & region →
  User-interface* y **no** se instala el script de arranque.
- `LOCALE_MODE_STARTUP_FALLBACK` — el runtime no incluye `jdk.localedata`, así
  que la preferencia no persiste. Se instala el script de arranque idempotente.

QuPath 0.7.0 está en el segundo caso. Si una versión futura corrige el runtime,
el actualizador lo detectará solo y dejará de instalar el *workaround*.

En **ambos** modos, los locales *default* y *format* permanecen en `en_US`, de
modo que el separador decimal sigue siendo el punto y las mediciones exportadas
no cambian.
