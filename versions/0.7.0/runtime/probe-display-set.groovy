/*
 * WARNING - THIS PROBE MUTATES STATE.
 *
 * Assigning defaultLocaleDisplayProperty writes a 'localeDisplay' value into
 * the Windows registry under
 *   HKCU\Software\JavaSoft\Prefs\io.github.qupath\0.7
 * as the key 'locale/Display'.  The value it writes ("Spanish") cannot be
 * parsed back, so it is inert, but remove it after running this probe if you
 * want to leave the machine exactly as you found it.
 *
 * The other probes in this directory are strictly read-only.
 *
 * Probe: set DISPLAY=es inside a headless process (no GUI built) and check
 * that (a) resource resolution switches to Spanish, and (b) the default and
 * FORMAT categories stay en_US.
 *
 * This isolates the *mechanism* from the *timing*: if this works, then any
 * hook that runs before QuPathGUI builds its controls would give a fully
 * Spanish interface.
 */

import java.util.Locale

def out = new StringBuilder()
def put = { String k, Object v -> out.append(k).append('=').append(v).append('\n') }

def prefs = Class.forName('qupath.lib.gui.prefs.PathPrefs')
def res = Class.forName('qupath.lib.gui.localization.QuPathResources')

def lookup = { String key ->
    try { return res.getString(key) }
    catch (Exception e) { return '<<MISSING:' + e.getClass().getSimpleName() + '>>' }
}

// Where does QuPath think the user directory is?  This decides whether the
// external localization directory is searched at all.
put('before.userPath', prefs.userPathProperty().get())
def udm = Class.forName('qupath.lib.gui.UserDirectoryManager').getInstance()
put('before.userDirectory', udm.getUserPath())
put('before.localizationDirectory', udm.getLocalizationDirectoryPath())

put('before.locale.default', Locale.getDefault())
put('before.locale.display', Locale.getDefault(Locale.Category.DISPLAY))
put('before.locale.format', Locale.getDefault(Locale.Category.FORMAT))
put('before.Menu.File', lookup('Menu.File'))

// --- flip DISPLAY only ------------------------------------------------------
prefs.defaultLocaleDisplayProperty().set(Locale.forLanguageTag('es'))

put('after.locale.default', Locale.getDefault())
put('after.locale.display', Locale.getDefault(Locale.Category.DISPLAY))
put('after.locale.format', Locale.getDefault(Locale.Category.FORMAT))

def sample = String.format(Locale.getDefault(Locale.Category.FORMAT), '%.2f', 1234.5d)
put('after.format.sample', sample)
put('after.format.usesDot', sample.contains('.'))

put('after.Menu.File', lookup('Menu.File'))
put('after.Menu.Edit', lookup('Menu.Edit'))
put('after.AnalysisPane.projectTab', lookup('AnalysisPane.projectTab'))
put('after.CommonActions.showPrefPane', lookup('CommonActions.showPrefPane'))
put('after.Tools.brush', lookup('Tools.brush'))
put('after.ViewerActions.scalebar', lookup('ViewerActions.scalebar'))

// Keys that do not exist in the 0.7.0 bundle - proof they are not ours to fix.
put('after.Panes.ProjectBrowser.imageList', lookup('Panes.ProjectBrowser.imageList'))
put('after.Viewer.ViewerManager.dragAndDropWithoutProject',
        lookup('Viewer.ViewerManager.dragAndDropWithoutProject'))

// Does the preference survive a serialise/deserialise round trip?
def node = java.util.prefs.Preferences.userRoot().node('io.github.qupath/0.7')
put('after.storedPref.localeDisplay', node.get('localeDisplay', '<<absent>>'))

print '<<<QUPATH-DISPLAY-SET-PROBE>>>\n'
print out.toString()
print '<<<END>>>\n'
