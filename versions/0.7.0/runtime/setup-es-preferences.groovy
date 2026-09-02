/*
 * One-shot setup for the Spanish localization of QuPath 0.7.0.
 *
 * WHY THIS EXISTS
 * ---------------
 * The Spanish interface depends on two ordinary string preferences:
 *
 *   userPath           -> so <user dir>/localization is searched for the
 *                         external qupath-gui-strings_es.properties
 *   startupScriptPath  -> so qupath-es-startup.groovy runs at launch and sets
 *                         the display locale
 *
 * Both are wiped by "Reset preferences" (and by the -r / --reset flag), which
 * silently returns the interface to English.  Re-selecting them by hand
 * through the Preferences dialog is easy to get wrong, so this script sets
 * them programmatically and flushes them to disk.
 *
 * Unlike the locale preferences, these two are plain strings: they do not go
 * through LocaleConverter, so they persist correctly even on a runtime without
 * jdk.localedata.
 *
 * Run it headlessly, with QuPath closed:
 *
 *   "QuPath-0.7.0 (console).exe" script versions/0.7.0/runtime/setup-es-preferences.groovy
 *
 * Then start QuPath normally.
 *
 * It changes only these two user preferences.  It does not touch the QuPath
 * installation, the JAR, the runtime or any machine-wide setting.
 */

import qupath.lib.gui.prefs.PathPrefs
import java.nio.file.Files
import java.nio.file.Paths

def home = System.getProperty('user.home')
def userDir = Paths.get(home, 'QuPath')
def startupScript = userDir.resolve('scripts').resolve('qupath-es-startup.groovy')
def bundle = userDir.resolve('localization').resolve('qupath-gui-strings_es.properties')

def problems = []

if (!Files.isDirectory(userDir))
    problems << ('user directory not found: ' + userDir)
if (!Files.isRegularFile(startupScript))
    problems << ('startup script not found: ' + startupScript)
if (!Files.isRegularFile(bundle))
    problems << ('Spanish bundle not found: ' + bundle)

if (!problems.isEmpty()) {
    println('SETUP FAILED')
    problems.each { println('  - ' + it) }
    println('Install the bundle and the startup script first; nothing was changed.')
    return
}

PathPrefs.userPathProperty().set(userDir.toString())
PathPrefs.startupScriptProperty().set(startupScript.toString())

// Force the values out to the backing store now, rather than waiting for the
// periodic sync, so a hard shutdown cannot lose them.
java.util.prefs.Preferences.userRoot().flush()

println('SETUP OK')
println('  userPath          = ' + PathPrefs.userPathProperty().get())
println('  startupScriptPath = ' + PathPrefs.startupScriptProperty().get())
println('  bundle            = ' + bundle)
println('Start QuPath normally; the interface should come up in Spanish.')
