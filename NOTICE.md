# NOTICE

## What this project is

`qupath-es` is an **unofficial Spanish localization project for QuPath**.

It is not affiliated with, endorsed by, or maintained by the QuPath developers
or the University of Edinburgh. QuPath is an academic project intended for
research use only.

## What it contains

This repository distributes a translated Java `.properties` resource bundle
that QuPath loads at runtime from an external directory. It does **not**
contain, modify or redistribute QuPath itself: no source code, no JAR files
and no executables.

The repository does contain, for traceability and validation purposes:

- an unmodified copy of the canonical English resource bundle
  `qupath-gui-strings.properties`, extracted from the official QuPath 0.7.0
  distribution;
- an unmodified copy of the `META-INF/MANIFEST.MF` of
  `qupath-gui-fx-0.7.0.jar`;
- a Spanish translation derived from that English bundle.

The property **keys** are QuPath's. The Spanish **values** are this project's
translation work.

## Upstream

| Item | Value |
| --- | --- |
| Upstream project | QuPath |
| Upstream repository | https://github.com/qupath/qupath |
| Upstream licence | GNU General Public License, version 3 (GPL-3.0) |
| Version targeted | QuPath 0.7.0 |
| Build | 2026-02-25 16:06 |
| Upstream commit | `04ccfa4` |
| Source JAR | `qupath-gui-fx-0.7.0.jar` |
| Source JAR SHA-256 | `4C3DB78B5A3A1F519F3D8CD5BAC4C69E598B1E59D97E666C4BDD23C31164B968` |
| Canonical bundle SHA-256 | `796EFC44FC23369E4D7BDFDE69C0FA2A702051BF2F9D71399157B505E8D45D2D` |
| Canonical bundle size | 80798 bytes, 894 entries |

## Licence of this repository

Because the translated bundle is derived from a GPL-3.0 licensed resource file,
this repository is distributed under the **GNU General Public License,
version 3**. The full text is in [`LICENSE`](LICENSE).

Copyright of the original QuPath resources remains with the QuPath developers
and the University of Edinburgh.

## Modifications

| Item | Detail |
| --- | --- |
| Nature of modification | Translation of resource bundle values from English to Spanish |
| Keys modified | None - all 894 keys, and their order, are preserved unchanged |
| Values translated | 884 |
| Values deliberately left in English | 10 (acronyms, product names, numeric labels; marked `KEEP_EN`) |
| Translated and maintained by | LABVETNEB |
| Date | 2026-09-02 |

## Relationship to the QuPath runtime

The translation is installed as an external bundle in the QuPath user
directory (`<user home>/QuPath/localization/`), using the external-bundle
mechanism that QuPath provides through
`qupath.lib.gui.localization.QuPathResources`. The QuPath installation itself
is never modified.

## Disclaimer

This NOTICE documents provenance and licensing for transparency. It is not
legal advice and makes no legal warranty. Anyone redistributing this work
should read `LICENSE` and satisfy themselves as to their own obligations.

QuPath, ImageJ, Bio-Formats, OpenSlide, Groovy and other names used in the
translated strings are the trademarks or product names of their respective
owners and are retained untranslated where appropriate.
