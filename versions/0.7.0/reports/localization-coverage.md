# QuPath 0.7.0 - localization coverage

Read-only audit of the installed distribution at
`C:\Users\Nico\AppData\Local\QuPath-0.7.0\app`.

All figures below come from the **installed JARs themselves** (a JAR is a ZIP;
class constant pools were parsed directly), not from the QuPath source tree.
They therefore describe the exact binary that runs on this machine.

- QuPath version: **0.7.0**
- Build: 2026-02-25 16:06
- Upstream commit: `04ccfa4`
- `qupath-gui-fx-0.7.0.jar` SHA-256:
  `4C3DB78B5A3A1F519F3D8CD5BAC4C69E598B1E59D97E666C4BDD23C31164B968`
- JARs scanned: 15 (`qupath*.jar`)
- Classes scanned: 1854

---

## Headline numbers

> **Main GUI bundle coverage: 894 / 894 (100 %).**
>
> **Whole-application localization coverage: an estimated 50-60 % of
> user-visible strings.**

These are two different metrics and must never be conflated. The first is
exact and verified. The second is an estimate, and the method is stated below.

---

## Classification

| Category | What it is | Count | Covered by this project |
| --- | --- | --- | --- |
| `MAIN_BUNDLE` | `qupath/lib/gui/localization/qupath-gui-strings.properties` in `qupath-gui-fx-0.7.0.jar` | **894 keys** | **Yes - 100 %** |
| `OTHER_BUNDLE` | Six further `ResourceBundle`s in other jars | **226 keys** | No |
| `FXML` | 2 FXML views | 65 `%key` refs, 1 literal | Partly (see below) |
| `EXTENSION` | 8 bundled extension jars | - | Only via their own bundles |
| `PARAMETERLIST` | Analysis parameter dialogs | 60 classes, 1071 prose constants | No |
| `HARDCODED` | Prose string constants compiled into classes | 3631 (upper bound) | No |
| `UNSUPPORTED` | JavaFX / ControlsFX / OS dialogs | - | Out of scope |

---

## MAIN_BUNDLE - fully covered

| Metric | Value |
| --- | --- |
| Keys in bundle | 894 |
| Translated (`REVIEWED`) | 884 |
| Deliberately English (`KEEP_EN`) | 10 |
| `BLOCKED` / `PENDING` / `DRAFT` | 0 |
| Validator | PASS, 0 errors, 0 warnings |

This is the bundle that drives the menu bar, the analysis pane, preferences,
tools, overlay and viewer actions, drag & drop, the grid views and the
measurement export dialog. It is served through `QuPathResources`, which is
the only loader in QuPath that searches the external `localization` directory.

---

## OTHER_BUNDLE - not covered

Six additional bundles, **226 keys total**. None of them is reachable from
our external `_es` file, because each is loaded by its own code path.

| Jar | Bundle | Keys |
| --- | --- | --- |
| `qupath-extension-training-0.1.0.jar` | `qupath/ext/training/ui/tour.properties` | 94 |
| `qupath-extension-processing-0.7.0.jar` | `qupath/imagej/gui/scripts/strings.properties` | 68 |
| `qupath-extension-djl-0.4.2.jar` | `qupath/ext/djl/ui/strings.properties` | 46 |
| `qupath-fxtras-0.3.0.jar` | `qupath/fx/localization/strings.properties` | 9 |
| `qupath-extension-openslide-0.7.0.jar` | `qupath/ext/openslide/strings.properties` | 7 |
| `qupath-extension-training-0.1.0.jar` | `qupath/ext/training/ui/strings.properties` | 2 |

`qupath-gui-fx-0.7.0.jar` also ships `qupath-gui-strings_en.properties` (an
intentionally empty English marker) and `log4j.properties` (not user-facing).

---

## FXML

| Jar | View | `%key` refs | Literal texts |
| --- | --- | --- | --- |
| `qupath-extension-processing-0.7.0.jar` | `qupath/imagej/gui/scripts/ij-script-runner.fxml` | 60 | 1 |
| `qupath-gui-fx-0.7.0.jar` | `qupath/lib/gui/update-manager-container.fxml` | 5 | 0 |

Both views externalise their text properly, but neither reaches our bundle:

- the ImageJ script runner resolves its 60 keys against its **own** bundle;
- the update manager container resolves its 5 keys against the main bundle
  **name**, but loads it with a plain `ResourceBundle.getBundle(...)` call -
  no custom `Control`, so the external file is never searched, and no explicit
  locale, so it follows the **FORMAT** locale (which we deliberately keep at
  `en_US`).

The update manager will therefore stay in English under our configuration.
That is a QuPath consistency defect, not a defect of this translation.

---

## PARAMETERLIST and HARDCODED

| Metric | Value |
| --- | --- |
| Prose string constants across the 6 UI/processing jars | 4563 |
| ... SLF4J log messages (contain `{}`) | 795 (17.4 %) |
| ... exception-style messages | 137 (3.0 %) |
| ... remaining prose | 3631 (79.6 %) |
| Classes that build a `ParameterList` | 60 |
| Prose constants inside those classes | 1071 |

Per jar:

| Jar | Classes | Prose | ParameterList classes | Prose in them |
| --- | --- | --- | --- | --- |
| `qupath-gui-fx-0.7.0.jar` | 618 | 2033 | 14 | 476 |
| `qupath-core-processing-0.7.0.jar` | 389 | 965 | 35 | 414 |
| `qupath-extension-processing-0.7.0.jar` | 107 | 687 | 7 | 207 |
| `qupath-core-0.7.0.jar` | 459 | 601 | 1 | 7 |
| `qupath-extension-bioformats-0.7.0.jar` | 43 | 253 | 2 | 18 |
| `qupath-extension-svg-0.7.0.jar` | 7 | 24 | 1 | 12 |

**The 3631 figure is an upper bound, not a count of visible text.** Constant
pool analysis cannot tell a button label from a workflow script fragment, a
CSS rule or a JSON key. What it does establish reliably is the *shape* of the
problem: the analysis parameter dialogs are a large, clearly identifiable
cluster of untranslatable visible text concentrated in
`qupath-core-processing` and `qupath-extension-processing`.

---

## How the whole-application estimate was derived

Countable, user-visible strings that our bundle does **not** reach:

| Cluster | Count | Confidence |
| --- | --- | --- |
| Other resource bundles | 226 | Exact |
| ImageJ script runner FXML | 60 (subset of the above bundle) | Exact |
| `ParameterList` labels and tooltips | ~535 (≈ 50 % of 1071 prose constants in those 60 classes; the rest are parameter keys, units and internal text) | Estimated |
| Plugin names / descriptions, enum display labels | not separately countable at binary level | Unknown |

Localized: 894.
Countable untranslated: 226 + ~535 ≈ **761**, plus an unknown residue.

    894 / (894 + 761) ≈ 54 %

Rounding for the unknown residue in both directions gives the stated band of
**50-60 %**.

For comparison, a source-level audit with hand review of every candidate
literal (performed against the newer 0.8 development sources, where the
i18n coverage is somewhat better) put the *main GUI window* at ~97 % and the
whole application at ~80 %. The binary audit here is coarser - it cannot
separate visible from non-visible strings - so it produces a more pessimistic
band. Both agree on the structural conclusion:

- the QuPath main window is essentially fully translatable through this bundle;
- the analysis parameter dialogs are not, and no external-bundle strategy can
  reach them.

---

## What remains in English

Confirmed by the E2E run and by this audit:

1. **Analysis parameter dialogs** - cell detection, positive cell detection,
   tissue detection, tile/superpixel creation, TMA dearrayer, intensity and
   shape features. Largest single gap.
2. **Plugin names and descriptions** used as menu text and dialog titles.
3. **Enum display labels** in some drop-downs.
4. **Update manager** window (loads the bundle without the custom `Control`).
5. **ImageJ script runner** (its own bundle, own loader).
6. **OpenSlide, Deep Java Library and Training extensions** (own bundles).
7. **JavaFX / ControlsFX standard controls** - `OK`, `Cancel`, `Yes`, `No`,
   text-field context menu, colour picker. These follow the **FORMAT** locale,
   which we deliberately keep at `en_US`; translating them would require
   moving the format locale and would change decimal separators.
8. **Operating-system dialogs** - native file and directory choosers.

None of these can be fixed by an external `.properties` file. Items 1-3 need
changes upstream in QuPath; items 4-6 need either upstream changes or separate
`_es` bundles that their own loaders can find; items 7-8 are outside QuPath.
