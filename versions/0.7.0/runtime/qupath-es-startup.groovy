/*
 * QuPath 0.7.0 - Spanish display-locale startup script.
 *
 * WHY THIS EXISTS
 * ---------------
 * The Windows runtime bundled with QuPath 0.7.0 (Java 25 / Eclipse Adoptium)
 * reports zero available locales with language "es".  As a result the normal
 * preference round-trip cannot restore a Spanish Locale between processes:
 * localeDisplay deserialises back to null.  See
 * versions/0.7.0/reports/spanish-locale-runtime.md
 *
 * Locale.forLanguageTag("es") does produce a working Locale inside a running
 * process, so this script sets the DISPLAY locale at startup.
 *
 * It deliberately does NOT touch the default locale or the FORMAT locale:
 * those must stay en_US so that decimal separators, dates and exported
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

def spanish = Locale.forLanguageTag('es')

// Display only.  Never PathPrefs.defaultLocaleProperty() and never
// defaultLocaleFormatProperty() - those would change number formatting.
PathPrefs.defaultLocaleDisplayProperty().set(spanish)

// ---------------------------------------------------------------------------
// End-to-end proof: sample a representative set of resource keys and record
// what the running application actually resolves them to.
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
]

// Keys deliberately identical to English (KEEP_EN) - listed so the report can
// distinguish "not translated" from "intentionally English".
def keepEn = ['Menu.TMA'] as Set

def sb = new StringBuilder()

sb.append('startupScript=PASS').append(System.lineSeparator())
sb.append('localeDefault=').append(PathPrefs.defaultLocaleProperty().get())
  .append(System.lineSeparator())
sb.append('localeFormat=').append(PathPrefs.defaultLocaleFormatProperty().get())
  .append(System.lineSeparator())
sb.append('localeDisplay=').append(PathPrefs.defaultLocaleDisplayProperty().get())
  .append(System.lineSeparator())

// Number formatting must remain en_US: a decimal point, not a comma.
def sampleNumber = String.format(
        Locale.getDefault(Locale.Category.FORMAT), '%.2f', 1234.5d)
sb.append('formatSample=').append(sampleNumber).append(System.lineSeparator())
sb.append('formatUsesDot=').append(sampleNumber.contains('.'))
  .append(System.lineSeparator())

sb.append('---').append(System.lineSeparator())

def missing = 0

for (key in sampleKeys) {
    def value
    try {
        value = QuPathResources.getString(key)
    } catch (Exception e) {
        value = '<<MISSING: ' + e.getClass().getSimpleName() + '>>'
        missing++
    }
    sb.append(key).append('=').append(value).append(System.lineSeparator())
}

sb.append('---').append(System.lineSeparator())
sb.append('sampledKeys=').append(sampleKeys.size()).append(System.lineSeparator())
sb.append('missingKeys=').append(missing).append(System.lineSeparator())
sb.append('keepEnSampled=').append(keepEn.size()).append(System.lineSeparator())

def proof = Paths.get(
    System.getProperty('user.home'), 'QuPath', 'startup-es-proof.txt')

Files.writeString(proof, sb.toString())

println('QuPath Spanish startup localization applied')
println('localeDisplay=' + PathPrefs.defaultLocaleDisplayProperty().get())
println('Menu.File=' + QuPathResources.getString('Menu.File'))
println('proof written to ' + proof)
