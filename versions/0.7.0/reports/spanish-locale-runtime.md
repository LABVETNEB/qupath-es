# Spanish display locale on QuPath 0.7.0 for Windows - runtime finding

## Summary

The Windows distribution of QuPath 0.7.0 ships a trimmed Java runtime that
**omits the `jdk.localedata` module**. Without it the JVM knows only the ROOT
and English locales, so `Locale.getAvailableLocales()` reports no locale whose
language is `es`. As a consequence QuPath's locale preference cannot be
persisted and restored across restarts.

This is a limitation of the **bundled runtime image**. It is *not* a fault in
QuPath's `ResourceBundle` machinery and *not* a fault in our Spanish bundle -
both of which work correctly, as the end-to-end proof below shows.

---

## Environment

| Item | Value |
| --- | --- |
| Application | QuPath 0.7.0 (Windows) |
| Install path | `C:\Users\Nico\AppData\Local\QuPath-0.7.0` |
| Build | 2026-02-25 16:06 |
| Upstream commit | `04ccfa4` |
| Bundled Java | 25.0.2 (Eclipse Adoptium, jlink image) |
| Runtime path | `...\QuPath-0.7.0\runtime` |

---

## Root cause - verified

The `release` file of the bundled runtime lists **24 modules**:

```
java.base java.compiler java.datatransfer java.xml java.prefs java.desktop
java.instrument java.logging java.management java.security.sasl java.naming
java.rmi java.management.rmi java.net.http java.scripting java.security.jgss
java.transaction.xa java.sql java.sql.rowset java.xml.crypto java.se
jdk.management.agent jdk.unsupported jdk.zipfs
```

`jdk.localedata` is **absent**.

In a standard JDK, `java.base` carries locale data for the ROOT locale and
English only; every other language lives in `jdk.localedata`. A `jlink` image
built without that module therefore exposes a locale list restricted to
English. This is the documented behaviour of the module system, and it fully
accounts for the observed symptom.

Verification command (read-only):

```bash
grep -o 'jdk.localedata' \
  "C:/Users/Nico/AppData/Local/QuPath-0.7.0/runtime/release" \
  || echo "jdk.localedata NOT PRESENT"
```

---

## Observed behaviour

| Observation | Result |
| --- | --- |
| `Locale.getAvailableLocales()` filtered by `language == "es"` | count = 0 |
| `Locale.forLanguageTag("es")` | works - returns a usable `Locale` |
| Setting `PathPrefs.defaultLocaleDisplayProperty()` to that locale | works within the running process |
| `ResourceBundle` resolution for `es` | works - external bundle is found and read |
| Restart, then read `localeDisplay` back from preferences | `null` |
| Trying `es-ES` | serialises as `Spanish (Spain)`, round-trips to `null` |

### Why each of these is consistent with the root cause

- **Locale construction still works.** `Locale.forLanguageTag("es")` builds a
  `Locale` object from a language tag. It does not need CLDR data, so the
  missing module does not block it.
- **Bundle lookup still works.** `ResourceBundle` derives candidate file names
  from the locale's language tag (`qupath-gui-strings_es.properties`). Again,
  no CLDR data is required. This is why our translation displays correctly.
- **Persistence fails.** Restoring a stored locale involves resolving a
  serialised locale back to a known one. With no `es` locale available in the
  runtime, that resolution yields `null`, and the display preference is lost
  on the next launch.

### What must NOT be attempted

Because the cause is a missing runtime module, none of the following can fix
it, and all were ruled out:

- using `es_ES`, `es_AR` or `es_MX` instead of `es`;
- selecting Spanish from the Preferences drop-down (it is not listed);
- a custom `LocaleConverter`;
- any change to how the preference is stored.

---

## Workaround in use

A startup script assigns the display locale on every launch:

- Script: `<user home>\QuPath\scripts\qupath-es-startup.groovy`
- Versioned copy: `versions/0.7.0/runtime/qupath-es-startup.groovy`
- Enabled through: *Preferences -> General -> Startup script path*

It sets **only** the DISPLAY locale:

```groovy
PathPrefs.defaultLocaleDisplayProperty().set(Locale.forLanguageTag('es'))
```

It deliberately never touches `defaultLocaleProperty()` or
`defaultLocaleFormatProperty()`, so number and date formatting stay `en_US`.

Keep this workaround in place for as long as the shipped runtime lacks
`jdk.localedata`.

---

## End-to-end proof

Captured at `versions/0.7.0/reports/e2e-startup-proof.txt` from a real launch
with the complete 894-key bundle installed:

```
startupScript=PASS
localeDefault=en_US
localeFormat=en_US
localeDisplay=es
formatSample=1234.50
formatUsesDot=true
---
Menu.File=Archivo
Menu.Edit=Editar
Menu.Tools=Herramientas
Menu.View=Ver
Menu.Objects=Objetos
Menu.Measure=Medir
Menu.Automate=Automatizar
Menu.Analyze=Analizar
Menu.Classify=Clasificar
Menu.Extensions=Extensiones
Menu.Window=Ventana
Menu.Help=Ayuda
...
sampledKeys=40
missingKeys=0
```

Three things are proven by this:

1. **The bundle loads.** All 40 sampled keys resolve to Spanish; none falls
   back to English or raises `MissingResourceException`.
2. **UTF-8 works end to end.** Accented output (`Jerarquía`, `Añadir
   imágenes...`, `Rectángulo`, `Polilínea`) is rendered correctly, so the
   external file is read as UTF-8 by QuPath's resource control.
3. **Scientific formatting is untouched.** `formatSample=1234.50` with
   `formatUsesDot=true` confirms the decimal separator is still a point, and
   `localeDefault` / `localeFormat` both remain `en_US`.

---

## Three distinct things, kept separate

| Component | Status |
| --- | --- |
| Bundled Windows runtime (locale data) | **Defective for this purpose** - `jdk.localedata` omitted |
| QuPath `ResourceBundle` machinery | **Works correctly** - external bundle found, read as UTF-8, keys resolved |
| Our Spanish bundle | **Works correctly** - 894/894 keys, validator PASS |

---

## Possible upstream remedy

Rebuilding the Windows runtime image with `jdk.localedata` included (a `jlink`
`--add-modules` change in QuPath's packaging configuration) would make Spanish
selectable from the Preferences drop-down and persist across restarts,
removing the need for the startup script. That change belongs in QuPath's
build, not in this project, and is recorded here as a suggestion only.
