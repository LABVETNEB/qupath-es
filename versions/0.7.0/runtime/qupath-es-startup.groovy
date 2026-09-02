/*
 * QuPath 0.7.0 - Spanish display-locale startup script (idempotent fallback).
 *
 * WHY THIS EXISTS
 * ---------------
 * The Windows runtime bundled with QuPath 0.7.0 (Java 25.0.2, jlink image)
 * omits the jdk.localedata module, so the JVM knows only five locales, all of
 * them English or root.  Two consequences follow:
 *
 *   1. qupath.fx.utils.converters.LocaleConverter serialises a Locale to its
 *      English display name ("Spanish") and parses it back by matching that
 *      name against Locale.getAvailableLocales().  No Spanish locale is
 *      available, so the round trip returns null and the display-locale
 *      preference cannot survive a restart.
 *   2. PathPrefs' static initialiser calls Locale.setDefault(Locale.US),
 *      which resets BOTH the DISPLAY and FORMAT categories.  Any locale set
 *      earlier - including via -Duser.language.display - is discarded.
 *
 * Together these mean the display locale can only be set *after* PathPrefs has
 * initialised, which is what this script does.  See
 * versions/0.7.0/reports/pre-gui-locale-solution.md for the full evidence.
 *
 * IDEMPOTENT
 * ----------
 * If the display locale is already Spanish, the script changes nothing and
 * reports 'alreadySpanish'.  This keeps it safe as a fallback should a future
 * QuPath release set the locale earlier by itself.
 *
 * NEVER TOUCHES FORMATTING
 * ------------------------
 * Only Locale.Category.DISPLAY is assigned.  The default locale and the FORMAT
 * category stay en_US, so the decimal separator, dates and exported
 * measurements are unaffected.
 *
 * Install as: <user home>/QuPath/scripts/qupath-es-startup.groovy
 * Enable via: Preferences -> General -> Startup script path
 */

import qupath.lib.gui.prefs.PathPrefs
import qupath.lib.gui.localization.QuPathResources
import java.util.Locale
import java.nio.file.Files
import java.nio.file.Paths

final String TARGET_LANGUAGE = 'es'

def displayBefore = Locale.getDefault(Locale.Category.DISPLAY)
def alreadySpanish = displayBefore != null &&
        TARGET_LANGUAGE.equals(displayBefore.getLanguage())

if (!alreadySpanish) {
    // Display only.  Never defaultLocaleProperty() and never
    // defaultLocaleFormatProperty() - those would change number formatting.
    PathPrefs.defaultLocaleDisplayProperty().set(
            Locale.forLanguageTag(TARGET_LANGUAGE))
}

// ---------------------------------------------------------------------------
// Evidence file
// ---------------------------------------------------------------------------

def sampleKeys = [
    'Menu.File', 'Menu.Edit', 'Menu.Tools', 'Menu.View', 'Menu.Objects',
    'Menu.Measure', 'Menu.Automate', 'Menu.Analyze', 'Menu.Classify',
    'Menu.Extensions', 'Menu.Window', 'Menu.Help',

    'AnalysisPane.projectTab', 'AnalysisPane.imageTab',
    'AnalysisPane.annotationsTab', 'AnalysisPane.hierarchyTab',
    'AnalysisPane.workflowTab', 'AnalysisPane.measurementsTab',

    'CommonActions.showPrefPane', 'CommonActions.showBrightnessContrast',

    'Action.File.Project.createProject', 'Action.File.Project.openProject',
    'Action.File.Project.addImages',

    'Tools.move', 'Tools.rectangle', 'Tools.ellipse', 'Tools.line',
    'Tools.polygon', 'Tools.polyline', 'Tools.brush', 'Tools.points',

    'OverlayActions.showAnnotations', 'OverlayActions.showDetections',

    'ViewerActions.scalebar', 'ViewerActions.overview',

    'Welcome.title', 'GridView.classification', 'Prefs.Locale',
    'Measurements.Export.title', 'DragDrop.openImage',

    // Toolbar tooltips: resolved with a static lookup while the toolbar is
    // being built, so they show whether this script ran early enough.
    'Toolbar.magnification.description',
]

def sb = new StringBuilder()
def nl = System.lineSeparator()

sb.append('startupScript=PASS').append(nl)
sb.append('alreadySpanish=').append(alreadySpanish).append(nl)
sb.append('displayBefore=').append(displayBefore).append(nl)
sb.append('localeDefault=').append(PathPrefs.defaultLocaleProperty().get()).append(nl)
sb.append('localeFormat=').append(PathPrefs.defaultLocaleFormatProperty().get()).append(nl)
sb.append('localeDisplay=').append(PathPrefs.defaultLocaleDisplayProperty().get()).append(nl)

def sample = String.format(
        Locale.getDefault(Locale.Category.FORMAT), '%.2f', 1234.5d)
sb.append('formatSample=').append(sample).append(nl)
sb.append('formatUsesDot=').append(sample.contains('.')).append(nl)
sb.append('---').append(nl)

def missing = 0

for (key in sampleKeys) {
    def value
    try {
        value = QuPathResources.getString(key)
    } catch (Exception e) {
        value = '<<MISSING:' + e.getClass().getSimpleName() + '>>'
        missing++
    }
    sb.append(key).append('=').append(value).append(nl)
}

sb.append('---').append(nl)
sb.append('sampledKeys=').append(sampleKeys.size()).append(nl)
sb.append('missingKeys=').append(missing).append(nl)

def proof = Paths.get(
    System.getProperty('user.home'), 'QuPath', 'startup-es-proof.txt')

Files.writeString(proof, sb.toString())

println('QuPath Spanish startup localization: alreadySpanish=' + alreadySpanish)
println('localeDisplay=' + PathPrefs.defaultLocaleDisplayProperty().get())
println('Menu.File=' + QuPathResources.getString('Menu.File'))
println('proof written to ' + proof)
