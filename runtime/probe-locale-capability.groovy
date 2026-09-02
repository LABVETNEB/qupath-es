/*
 * Version-aware locale capability probe.
 *
 * Decides whether a given QuPath installation can hold a Spanish display
 * locale by itself, or whether it still needs the startup-script fallback.
 *
 * Run headlessly - no GUI is built:
 *   "QuPath-x.y.z (console).exe" script runtime/probe-locale-capability.groovy
 *
 * Strictly read-only: it never assigns a preference and never writes to the
 * registry.  Output is key=value lines between markers.
 *
 * The verdict line is:
 *   localeMode=LOCALE_MODE_NATIVE            -> QuPath can persist Spanish
 *   localeMode=LOCALE_MODE_STARTUP_FALLBACK  -> the startup script is required
 */

import java.util.Locale

def out = new StringBuilder()
def put = { String k, Object v -> out.append(k).append('=').append(v).append('\n') }

put('javaVersion', System.getProperty('java.version'))
put('javaVendor', System.getProperty('java.vendor'))

// --- locale data availability ----------------------------------------------
def all = Locale.getAvailableLocales()
def spanish = all.findAll { it.getLanguage() == 'es' }

put('availableLocales.total', all.length)
put('availableLocales.spanish', spanish.size())
put('has.es', spanish.any { it.getCountry().isEmpty() })
put('has.es_ES', spanish.any { it.getCountry() == 'ES' })
put('has.es_AR', spanish.any { it.getCountry() == 'AR' })

// jdk.localedata is not directly queryable from a jlink image at runtime, so
// use the locale count as the observable proxy: without it, java.base offers
// only root and English.
def localeDataPresent = spanish.size() > 0
put('jdk.localedata.presentByProxy', localeDataPresent)

// --- can a Spanish locale even be built? -----------------------------------
def es = Locale.forLanguageTag('es')
put('forLanguageTag.es.works', 'es'.equals(es.getLanguage()))

// --- does QuPath's preference converter round-trip Spanish? -----------------
def roundTrip = false
def serialized = '<n/a>'
def parsedBack = '<n/a>'

try {
    def converterClass = Class.forName('qupath.fx.utils.converters.LocaleConverter')
    def converter = converterClass.getDeclaredConstructor().newInstance()
    serialized = String.valueOf(converter.toString(es))
    def back = converter.fromString(serialized)
    parsedBack = String.valueOf(back)
    roundTrip = back != null && 'es'.equals(back.getLanguage())
} catch (Exception e) {
    serialized = '<<ERR:' + e.getClass().getSimpleName() + '>>'
}

put('localeConverter.serialized', serialized)
put('localeConverter.parsedBack', parsedBack)
put('localeConverter.roundTrip', roundTrip)

// --- current QuPath locale preferences (read-only) -------------------------
try {
    def prefs = Class.forName('qupath.lib.gui.prefs.PathPrefs')
    put('prefs.locale', prefs.defaultLocaleProperty().get())
    put('prefs.localeDisplay', prefs.defaultLocaleDisplayProperty().get())
    put('prefs.localeFormat', prefs.defaultLocaleFormatProperty().get())
    put('prefs.userPath', prefs.userPathProperty().get())
    put('prefs.startupScriptPath', prefs.startupScriptProperty().get())
} catch (Exception e) {
    put('prefs.error', e.getClass().getSimpleName())
}

put('locale.default', Locale.getDefault())
put('locale.display', Locale.getDefault(Locale.Category.DISPLAY))
put('locale.format', Locale.getDefault(Locale.Category.FORMAT))

def sample = String.format(Locale.getDefault(Locale.Category.FORMAT), '%.2f', 1234.5d)
put('format.sample', sample)
put('format.usesDot', sample.contains('.'))

// --- verdict ---------------------------------------------------------------
// Native mode needs BOTH: a Spanish locale the runtime knows about, and a
// converter that can store and restore it.  Either one missing means the
// preference cannot survive a restart.
def native_ok = localeDataPresent && roundTrip
put('localeMode', native_ok ? 'LOCALE_MODE_NATIVE' : 'LOCALE_MODE_STARTUP_FALLBACK')

print '<<<QUPATH-LOCALE-CAPABILITY>>>\n'
print out.toString()
print '<<<END>>>\n'
