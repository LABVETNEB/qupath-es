/*
 * Probe: what strings can qupath.fx.utils.converters.LocaleConverter parse
 * back into a Locale on this runtime?
 *
 * PathPrefs stores its locale preferences through this converter.  If a
 * Spanish locale cannot be round-tripped, the display-locale preference can
 * never survive a restart, no matter what the JVM is told at launch.
 *
 * Read-only: this probe does not write any preference.
 */

import java.util.Locale

def out = new StringBuilder()
def put = { String k, Object v -> out.append(k).append('=').append(v).append('\n') }

def converterClass = Class.forName('qupath.fx.utils.converters.LocaleConverter')
def converter = converterClass.getDeclaredConstructor().newInstance()

// --- what does it produce for locales we care about? ------------------------
def candidates = [
    'Locale.US'          : Locale.US,
    'Locale.ENGLISH'     : Locale.ENGLISH,
    'forLanguageTag es'  : Locale.forLanguageTag('es'),
    'forLanguageTag es-ES': Locale.forLanguageTag('es-ES'),
    'forLanguageTag es-AR': Locale.forLanguageTag('es-AR'),
]

candidates.each { name, loc ->
    def s
    try { s = converter.toString(loc) } catch (Exception e) { s = '<<ERR:' + e.getClass().getSimpleName() + '>>' }
    put('toString[' + name + ']', s)
}

// --- what can it parse back? ------------------------------------------------
def strings = [
    'en_US', 'English (United States)', 'English',
    'es', 'es_ES', 'es_AR', 'es-ES',
    'Spanish', 'Spanish (Spain)', 'Spanish (Argentina)',
    'espanol', 'ES', '', 'not-a-locale',
]

strings.each { s ->
    def parsed
    try {
        def r = converter.fromString(s)
        parsed = (r == null) ? 'null' : (r.toString() + ' [lang=' + r.getLanguage() + ']')
    } catch (Exception e) {
        parsed = '<<ERR:' + e.getClass().getSimpleName() + '>>'
    }
    put('fromString[' + s + ']', parsed)
}

// --- round-trip check -------------------------------------------------------
candidates.each { name, loc ->
    def ok
    try {
        def s = converter.toString(loc)
        def back = converter.fromString(s)
        ok = (back != null && back.getLanguage() == loc.getLanguage())
    } catch (Exception e) {
        ok = '<<ERR>>'
    }
    put('roundTrip[' + name + ']', ok)
}

// --- what is actually stored right now? -------------------------------------
def node = java.util.prefs.Preferences.userRoot().node('io.github.qupath/0.7')
['locale', 'localeDisplay', 'localeFormat'].each { key ->
    put('storedPref[' + key + ']', node.get(key, '<<absent>>'))
}

print '<<<QUPATH-LOCALE-CONVERTER-PROBE>>>\n'
print out.toString()
print '<<<END>>>\n'
