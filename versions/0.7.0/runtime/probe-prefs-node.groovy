/*
 * Probe: enumerate the locales this runtime actually has, and the contents of
 * QuPath's preference node.  Read-only.
 */

import java.util.Locale

def out = new StringBuilder()
def put = { String k, Object v -> out.append(k).append('=').append(v).append('\n') }

Locale.getAvailableLocales().eachWithIndex { loc, i ->
    put('availableLocale[' + i + ']', "'" + loc.toString() + "' tag=" + loc.toLanguageTag() +
            " display='" + loc.getDisplayName(Locale.ENGLISH) + "'")
}

put('localeProviders', System.getProperty('java.locale.providers'))

def root = java.util.prefs.Preferences.userRoot()

// Walk the QuPath preference tree and dump every key we can see.
def dump
dump = { java.util.prefs.Preferences node, String path ->
    node.keys().sort().each { k ->
        put('pref[' + path + '/' + k + ']', node.get(k, ''))
    }
    node.childrenNames().sort().each { c ->
        dump(node.node(c), path + '/' + c)
    }
}

if (root.nodeExists('io.github.qupath')) {
    dump(root.node('io.github.qupath'), 'io.github.qupath')
} else {
    put('prefsNode', '<<io.github.qupath does not exist>>')
}

print '<<<QUPATH-PREFS-PROBE>>>\n'
print out.toString()
print '<<<END>>>\n'
