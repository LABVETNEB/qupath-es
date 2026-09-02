/*
 * Locale diagnostic for QuPath 0.7.0.
 *
 * Prints the JVM locale state, the QuPath locale preferences and a few
 * representative resource lookups, as machine-readable key=value lines.
 *
 * Run headless (no GUI is built):
 *   "QuPath-0.7.0 (console).exe" script <path-to-this-file>
 *
 * The point of running it through the `script` subcommand is that PathPrefs
 * and QuPathResources are exercised without QuPathGUI ever constructing a
 * control, so whatever this reports is the state the GUI *would* be built
 * with.
 */

import java.util.Locale

def out = new StringBuilder()

def put = { String k, Object v -> out.append(k).append('=').append(v).append('\n') }

// ---------------------------------------------------------------------------
// 1. JVM system properties that seed java.util.Locale at class-init time
// ---------------------------------------------------------------------------
put('sysprop.user.language', System.getProperty('user.language'))
put('sysprop.user.country', System.getProperty('user.country'))
put('sysprop.user.variant', System.getProperty('user.variant'))
put('sysprop.user.language.display', System.getProperty('user.language.display'))
put('sysprop.user.country.display', System.getProperty('user.country.display'))
put('sysprop.user.variant.display', System.getProperty('user.variant.display'))
put('sysprop.user.language.format', System.getProperty('user.language.format'))
put('sysprop.user.country.format', System.getProperty('user.country.format'))
put('sysprop.user.variant.format', System.getProperty('user.variant.format'))
put('sysprop.JAVA_TOOL_OPTIONS.seen', System.getenv('JAVA_TOOL_OPTIONS'))

// ---------------------------------------------------------------------------
// 2. Effective JVM locale state
// ---------------------------------------------------------------------------
put('locale.default', Locale.getDefault())
put('locale.display', Locale.getDefault(Locale.Category.DISPLAY))
put('locale.format', Locale.getDefault(Locale.Category.FORMAT))

// Is any Spanish locale enumerable? (jdk.localedata presence probe)
def spanish = Locale.getAvailableLocales().findAll { it.getLanguage() == 'es' }
put('availableLocales.total', Locale.getAvailableLocales().length)
put('availableLocales.spanish', spanish.size())

// A Spanish Locale can be *constructed* even when it is not enumerable.
def esTag = Locale.forLanguageTag('es')
put('forLanguageTag.es.language', esTag.getLanguage())
put('forLanguageTag.es.toString', esTag.toString())

// ---------------------------------------------------------------------------
// 3. Number formatting must follow FORMAT, and must keep the decimal point
// ---------------------------------------------------------------------------
def sample = String.format(Locale.getDefault(Locale.Category.FORMAT), '%.2f', 1234.5d)
put('format.sample', sample)
put('format.usesDot', sample.contains('.'))

// ---------------------------------------------------------------------------
// 4. QuPath preference state
// ---------------------------------------------------------------------------
def prefs = Class.forName('qupath.lib.gui.prefs.PathPrefs')
put('prefs.locale', prefs.defaultLocaleProperty().get())
put('prefs.localeDisplay', prefs.defaultLocaleDisplayProperty().get())
put('prefs.localeFormat', prefs.defaultLocaleFormatProperty().get())

// Locale state *after* PathPrefs has certainly been initialised.
put('postPrefs.locale.default', Locale.getDefault())
put('postPrefs.locale.display', Locale.getDefault(Locale.Category.DISPLAY))
put('postPrefs.locale.format', Locale.getDefault(Locale.Category.FORMAT))

// ---------------------------------------------------------------------------
// 5. Resource resolution - the three keys that expose the timing defect
// ---------------------------------------------------------------------------
def res = Class.forName('qupath.lib.gui.localization.QuPathResources')

def lookup = { String key ->
    try {
        return res.getString(key)
    } catch (Exception e) {
        return '<<MISSING:' + e.getClass().getSimpleName() + '>>'
    }
}

put('res.Menu.File', lookup('Menu.File'))
put('res.Panes.ProjectBrowser.imageList', lookup('Panes.ProjectBrowser.imageList'))
put('res.Panes.ProjectBrowser.searchEntry', lookup('Panes.ProjectBrowser.searchEntry'))
put('res.Viewer.ViewerManager.dragAndDropWithoutProject',
        lookup('Viewer.ViewerManager.dragAndDropWithoutProject'))
put('res.AnalysisPane.projectTab', lookup('AnalysisPane.projectTab'))
put('res.CommonActions.showPrefPane', lookup('CommonActions.showPrefPane'))

print '<<<QUPATH-LOCALE-DIAGNOSTIC>>>\n'
print out.toString()
print '<<<END>>>\n'
