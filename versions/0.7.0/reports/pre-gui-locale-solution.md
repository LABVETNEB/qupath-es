# Setting the Spanish display locale before QuPath builds its GUI

**Conclusion first: on QuPath 0.7.0 with its bundled runtime this is not
achievable from outside the application.** Every external mechanism was tested
and each is blocked by one of two independent defects in the shipped build.
The startup script therefore stays, now as an idempotent fallback.

This document records what was tested, what was measured, and why the
remaining gap is upstream work rather than configuration.

---

## 1. The original problem statement, and what turned out to be wrong with it

The task began from the observation that three strings stay in English on the
start screen:

- `Image list`
- `Search entry in project`
- `Drag & drop an image file or project folder`

and from the hypothesis that they are translated keys that a late locale switch
fails to refresh.

**That hypothesis is false, and it is worth stating plainly before anything
else.** Those three strings are not resource keys in QuPath 0.7.0. They are
string constants compiled into the classes:

| String | Class in `qupath-gui-fx-0.7.0.jar` |
| --- | --- |
| `Image list` | `qupath/lib/gui/panes/ProjectBrowser.class` |
| `Search entry in project` | `qupath/lib/gui/panes/ProjectBrowser.class` |
| `Drag & drop an image file or project folder` | `qupath/lib/gui/viewer/ViewerManager.class` |

The suggested key names (`Panes.ProjectBrowser.imageList`,
`Panes.ProjectBrowser.searchEntry`,
`Viewer.ViewerManager.dragAndDropWithoutProject`) do exist - but only in the
**0.8 development line**, where a large externalisation pass added the `Panes.*`
and `Viewer.*` prefixes. QuPath 0.7.0's bundle contains **neither prefix**:

```
$ grep -c '^Panes\.'  versions/0.7.0/base/qupath-gui-strings.properties   -> 0
$ grep -c '^Viewer\.' versions/0.7.0/base/qupath-gui-strings.properties   -> 0
```

and a live lookup raises `MissingResourceException`
(`versions/0.7.0/reports/pre-gui-locale-baseline.txt`).

**No locale mechanism, at any point in the lifecycle, can translate those three
strings on 0.7.0.** They require the upstream externalisation that landed after
this release.

---

## 2. Two independent blockers

### Blocker A - the runtime has no Spanish locale

```
availableLocales.total=5
availableLocales.spanish=0
```

The five locales are `""` (root), `en`, `en_US`, `en_US_#Latn`, `en_US_POSIX`.
The jlink image ships 24 modules and `jdk.localedata` is not among them, so
`java.base` supplies English and root only.

Consequence for persistence, measured directly
(`probe-locale-converter.groovy`):

| Call | Result |
| --- | --- |
| `LocaleConverter.toString(forLanguageTag("es"))` | `Spanish` |
| `LocaleConverter.toString(forLanguageTag("es-ES"))` | `Spanish (Spain)` |
| `LocaleConverter.fromString("Spanish")` | `null` |
| `LocaleConverter.fromString("Spanish (Spain)")` | `null` |
| `LocaleConverter.fromString("es")` | `null` |
| `LocaleConverter.fromString("es_ES")` | `null` |
| `LocaleConverter.fromString("English (United States)")` | `en_US` |
| round trip `en_US` | `true` |
| round trip `es`, `es_ES`, `es_AR` | **`false`** |

The converter serialises to an English display name and parses by matching that
name against the available locales. With no Spanish locale available, **no
string exists that stores a Spanish display locale in the preferences.** This
was confirmed end to end: setting the property writes `localeDisplay=Spanish`
into `HKCU\Software\JavaSoft\Prefs\io.github.qupath\0.7`, and that value
deserialises to `null` on the next start.

### Blocker B - PathPrefs resets the locale during its own initialisation

The baseline is decisive. The host machine is Spanish:

```
sysprop.user.language=es
sysprop.user.country=AR
```

yet by the time any script can observe it:

```
locale.default=en_US
locale.display=en_US
locale.format=en_US
```

Only the single-argument `Locale.setDefault(Locale)` changes the default *and*
both categories at once. So `PathPrefs`' static initialiser calls
`Locale.setDefault(Locale.US)` - and it does so before any QuPath extension
point exists.

**Anything the JVM was told at launch is discarded at that moment.**

---

## 3. Strategies tested

| # | Strategy | Result | Evidence |
| --- | --- | --- | --- |
| A | JVM system properties `user.language.display` / `user.country.display` | **Fails** | Property arrives (`sysprop.user.language.display=es`) but `locale.display=en_US`: wiped by Blocker B |
| B | `JAVA_TOOL_OPTIONS` scoped to the child process | **Fails** | Same measurement; the delivery mechanism works, the property does not survive |
| C | jpackage launcher options | **Not viable** | The `[JavaOptions]` block of `app/QuPath-0.7.0.cfg` can carry `-D` flags, but they are wiped exactly as in A |
| C' | QuPath's own `-D key=value` CLI option | **Not viable** | Applied with `System.setProperty` inside `main()`, long after `java.util.Locale` has been initialised; nothing re-reads it |
| D | External wrapper launcher | **Pointless** | A wrapper can only deliver A/B/C, all of which are wiped. Building one would imply a fix that does not exist |
| E | Editing `*.cfg` | **Rejected** | Same failure as A, while modifying the installation |
| F | Rebuilding the runtime with `jdk.localedata` | **Out of scope, and the real fix** | See section 6 |
| - | Storing a parseable Spanish preference | **Impossible** | Blocker A: no such string exists |
| - | `java.locale.providers=COMPAT` | **Not available** | The COMPAT provider was removed from the JDK before 25 |
| - | A custom `LocaleServiceProvider` on the classpath | **Not viable here** | Would require compiling Java, and this machine has no JDK: the bundled runtime is a jlink image with no `java.exe` |

Method note: all measurements were taken with the console launcher and the
`script` subcommand, which runs a Groovy script **without building any GUI**,
so the reported state is the state the GUI would be constructed with.

---

## 4. How much does the timing actually cost?

Because the headline hypothesis was wrong, the real size of the timing problem
was measured rather than assumed
(`tools/locale_timing_audit.py`, `reports/locale-timing-audit.json`).

| Key classification | Count |
| --- | --- |
| `DYNAMIC_LOCALE_BOUND` - re-resolves on locale change | 368 |
| `UNKNOWN` - key built at runtime or referenced from FXML | 348 |
| `STATIC_AT_CONSTRUCTION` - resolved once by a static lookup | 123 |
| `MIXED` | 55 |

`STATIC_AT_CONSTRUCTION` over-states the harm: most of those 123 keys belong to
dialogs that are constructed **when opened**, not at startup - `DragDrop.*`,
`Dialogs.*`, the Bio-Formats export dialog - so they pick up the new locale the
next time they are shown. Of the 31 classes that only ever do a static lookup,
the ones actually built during startup are:

- `qupath/lib/gui/ToolBarComponent` - toolbar tooltips
- `qupath/lib/gui/viewer/tools/PathTools` - drawing tool names
- `qupath/lib/gui/viewer/ViewerManager` - viewer placeholder text
- `qupath/lib/gui/QuPathApp` - startup messages

That is the true cost of the late switch on 0.7.0: **a handful of toolbar
tooltips and the viewer placeholder**, not the main interface. Menus, actions,
analysis-pane tabs, preferences, overlay and viewer actions are all
`@ActionConfig`- or `registerProperty`-bound and update correctly, which the
end-to-end proof already showed (40/40 sampled keys in Spanish).

---

## 5. What is in place instead

The startup script remains, rewritten to be **idempotent**:

- `versions/0.7.0/runtime/qupath-es-startup.groovy`
- installed at `<user home>/QuPath/scripts/qupath-es-startup.groovy`
- enabled through *Preferences -> General -> Startup script path*

Behaviour:

```groovy
def displayBefore = Locale.getDefault(Locale.Category.DISPLAY)
def alreadySpanish = displayBefore != null &&
        'es'.equals(displayBefore.getLanguage())
if (!alreadySpanish)
    PathPrefs.defaultLocaleDisplayProperty().set(Locale.forLanguageTag('es'))
```

If a future QuPath (or a runtime with `jdk.localedata`) already provides a
Spanish display locale, the script detects it and changes nothing. It writes
`alreadySpanish=true|false` into the proof file so the state is auditable.

It assigns **only** `Category.DISPLAY`. `localeDefault` and `localeFormat` stay
`en_US`, and the proof file records `formatSample=1234.50`,
`formatUsesDot=true` on every launch.

**Decision on the fallback: option C - keep it installed, made idempotent.**
Option A (remove it) would lose the Spanish interface entirely; option B (plain
fallback) is what it already was, minus the safety check.

---

## 6. The two upstream fixes that would actually close this

1. **Rebuild the Windows runtime with `jdk.localedata`.** A `jlink`
   `--add-modules jdk.localedata` change in QuPath's packaging would make
   Spanish enumerable, which fixes `LocaleConverter` round-tripping, which
   makes the display-locale preference persist - and then
   `-Duser.language.display=es` would also survive, because PathPrefs would be
   restoring a stored Spanish locale rather than falling back to `Locale.US`.
   This single change removes the need for the startup script.

2. **Externalise the remaining hardcoded strings.** The three strings that
   started this investigation are already externalised in the 0.8 line. Moving
   to a QuPath release that contains that work is what translates them; nothing
   in this repository can.

Both belong in QuPath's build, not here.

---

## 7. Rollback

Nothing in the installation was modified. To revert:

- disable the startup script in *Preferences -> General -> Startup script path*,
  or delete `<user home>/QuPath/scripts/qupath-es-startup.groovy`; and/or
- delete `<user home>/QuPath/localization/qupath-gui-strings_es.properties`.

QuPath returns to English. The JAR, the `.cfg` files and the runtime were never
touched, and the only registry value this investigation created
(`locale/Display`, written by a probe) was removed again.

---

## 8. Maintenance

- The probes are reusable: `runtime/diagnose-locale.groovy`,
  `runtime/probe-locale-converter.groovy`, `runtime/probe-prefs-node.groovy`,
  `runtime/probe-display-set.groovy`. Run them against any new QuPath build to
  re-test in minutes.
- `tools/locale_timing_audit.py` re-runs the static/dynamic classification
  against a new installation.
- When a QuPath release ships `jdk.localedata`, re-run
  `probe-locale-converter.groovy`. If the Spanish round trips return `true`,
  the startup script can be retired and Spanish selected from Preferences.
