# Arquitectura del corpus de componentes

Este documento define el contrato arquitectónico del eje `components/` de `qupath-es`.
No describe una implementación futura: documenta las fuentes de verdad que ya existen
y las invariantes que deben conservarse al incorporar nuevas extensiones, auditorías,
localizaciones, artefactos o parches.

Para la arquitectura del bundle principal de QuPath, el runtime y la instalación, ver
[`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 1. Fuentes de verdad

El modelo separa identidad estable, selección por versión de QuPath, evidencia de
auditoría y material de localización.

| Capa | Fuente de verdad | Responde |
| --- | --- | --- |
| Identidad | `components/registry.json` | ¿Qué componente es? |
| Pin por QuPath | `versions/<v>/components.lock.json` | ¿Qué revisión queda fijada para este objetivo? |
| Política del componente | `components/<id>/component.json` | ¿Qué rutas y categorías se auditan? |
| Evidencia | `components/<id>/audits/<commit>.json` | ¿Qué se observó en un commit concreto? |
| Localización | `components/<id>/l10n/<revision>/` | ¿Qué material lingüístico existe? |
| Parche | `components/<id>/patches/` | ¿Qué cambio local reproducible es necesario, si alguno? |

Ninguna de estas capas sustituye a otra. En particular, registrar una extensión no
certifica compatibilidad, y auditar un commit no cambia automáticamente el pin de una
release.

---

## 2. Arquitectura de dos ejes

`qupath-es` separa deliberadamente dos dimensiones:

```text
Eje A — identidad estable
components/registry.json
        │
        ├── qupath-core
        ├── instanseg
        ├── stardist
        └── ...

Eje B — objetivo QuPath
versions/0.7.0/components.lock.json
        │
        ├── pin exacto de cada componente
        ├── provenance
        ├── compatibilidad declarada/observada
        └── estado de localización y distribución
```

El identificador de componente no cambia cuando cambia la versión upstream. El
lockfile sí puede cambiar entre objetivos de QuPath.

Esta decisión está formalizada en
[`ADR-0001`](adr/0001-two-axis-component-architecture.md).

---

## 3. Registro estable

`components/registry.json` contiene únicamente identidad relativamente estable:

- `id` interno en `kebab-case`;
- nombre y repositorio upstream;
- propietario;
- tipo (`QUPATH_CORE` o `QUPATH_EXTENSION`);
- prioridad del corpus;
- función;
- licencia;
- sistema de build;
- entry point;
- eventual fork satélite;
- fecha de alta.

No pertenecen al registro los tags, commits, hashes, compatibilidad, estados de
traducción o estados de distribución. Esos datos dependen del objetivo QuPath y van al
lockfile.

Cambiar un `id` ya publicado es una migración de datos: afecta rutas, lockfiles,
auditorías, parches y cualquier automatización que use ese identificador.

---

## 4. Lockfile por versión de QuPath

Cada `versions/<v>/components.lock.json` fija el estado reproducible del corpus para un
objetivo concreto.

Campos especialmente importantes:

- `upstream_commit`: commit seleccionado por la política de pin;
- `evidence_commit`: commit del que existe evidencia versionada de auditoría;
- `pin_basis`: razón del pin (`FROZEN_TARGET_COMMIT`, `QUPATH_BUNDLED`,
  `UPSTREAM_RELEASE` o `AUDITED_COMMIT`);
- `artifact_name`, `artifact_url`, `artifact_sha256`: bytes de release cuando el pin se
  basa en una release independiente;
- `declared_qupath_api`: versión/API declarada por upstream;
- `runtime_compatibility`: compatibilidad realmente certificada por este repositorio;
- `localization_revision`: revisión local existente, si la hay;
- `translation_status`, `validation_status`, `distribution_status`: estados distintos,
  que no deben colapsarse en un único “hecho/no hecho”.

### Pin y evidencia no son sinónimos

Un tag de release puede fijar un commit, mientras que la auditoría del mecanismo de
localización puede haberse realizado sobre una cabeza upstream posterior. Por eso
`upstream_commit` y `evidence_commit` son campos separados.

La existencia de evidencia más nueva **no autoriza** a mover el pin silenciosamente.

### Provenance de assets

Para `pin_basis = UPSTREAM_RELEASE`, el schema exige nombre, URL HTTPS y SHA-256 del
asset fijado. Los hashes se registran sobre los bytes publicados, no sobre nombres ni
sobre una reconstrucción local.

`tools/verify_artifacts.py` permite verificar esos assets de forma opt-in. CI no depende
de la disponibilidad de servidores upstream para conservar determinismo.

---

## 5. Directorio de una extensión

Una extensión puede materializar el siguiente árbol, pero sólo se crean las ramas que
realmente sean necesarias:

```text
components/<id>/
├── component.json
├── audits/
│   └── <evidence_commit>.json
├── l10n/
│   └── <revision>/
│       ├── strings.tsv
│       └── dist/
│           └── <bundle_localizado>.properties
└── patches/
    └── ...
```

`component.json` describe la política de auditoría: rutas relevantes, bundles y
categorías de identificadores que no deben confundirse con texto de presentación.

Un `l10n/` presente significa que existe trabajo de localización; **no** implica por sí
solo que esté revisado, validado, instalable o distribuible. Esas afirmaciones deben
coincidir con el lockfile y con las pruebas.

---

## 6. QuPath Core es un caso intencionalmente distinto

`qupath-core` aparece en el registro y en el lockfile porque su identidad y provenance
forman parte del mismo corpus. Sin embargo, no existe `components/qupath-core/`.

La base del Core es el propio objetivo versionado bajo `versions/<v>/`, donde viven el
bundle canónico, el TSV, el `dist`, fingerprints e informes.

Duplicarlo bajo `components/` crearía dos autoridades para la misma base. La ausencia
de ese directorio es una invariante probada automáticamente.

Decisión formal: [`ADR-0002`](adr/0002-core-outside-components.md).

---

## 7. No vendoring

Registrar o auditar una extensión no copia su árbol de fuentes dentro de `qupath-es`.
Este repositorio conserva metadatos, evidencia, traducciones, hashes y —si llega a ser
necesario— parches reproducibles.

Si una localización no puede cargarse sin modificar una extensión, la política es:

1. preferir una solución upstream;
2. si no es viable y existe justificación, usar un fork satélite separado;
3. mantener aquí la trazabilidad del fork y los parches, no una copia completa del
   repositorio upstream.

Decisión formal: [`ADR-0003`](adr/0003-no-vendoring-satellite-forks.md).

---

## 8. Estados: evitar afirmaciones implícitas

Los estados se interpretan literalmente:

- `NOT_STARTED`: no hay trabajo de traducción registrado;
- `IN_PROGRESS`: existe material, pero no cumple todavía el gate final;
- `TRANSLATED`: la traducción está completada según su contrato;
- `NOT_APPLICABLE`: la validación no aplica porque no existe material a validar;
- `NOT_VALIDATED`: existe material pero aún no se certificó;
- `VALIDATED`: pasó el contrato de validación aplicable;
- `UNSUPPORTED`: `qupath-es` no declara un mecanismo de distribución soportado;
- `EXPERIMENTAL`: existe un mecanismo, pero no tiene todavía garantía estable;
- `DISTRIBUTED`: existe una vía de distribución soportada y versionada.

`runtime_compatibility = NOT_VERIFIED` debe permanecer así hasta que haya evidencia de
ejecución suficiente. Un `declared_qupath_api` compatible no equivale a compatibilidad
runtime verificada.

---

## 9. Contratos ejecutables

Los metadatos no dependen únicamente de revisión humana:

```powershell
python tools/schema_validate.py schemas/component-registry.schema.json components/registry.json
python tools/schema_validate.py schemas/components-lock.schema.json versions/0.7.0/components.lock.json
python -m unittest discover -s tests -p "test_*.py"
```

El validador de schema es fail-closed para el subconjunto de JSON Schema usado en este
repositorio. Si se introduce una keyword semántica nueva, debe implementarse y probarse
o el cambio debe rechazarse; no se ignora silenciosamente.

CI ejecuta la suite en Linux y Windows, además del check separado de integridad del
bundle canónico.

---

## 10. Cómo introducir cambios

### Añadir un componente

1. Añadir su identidad al registry.
2. Actualizar el schema sólo si el contrato realmente cambia.
3. Añadir el pin correspondiente al lockfile del objetivo QuPath.
4. Materializar `components/<id>/component.json` y un snapshot de auditoría si se ha
   auditado.
5. No crear `l10n/`, `patches/` o forks vacíos “por adelantado”.
6. Ejecutar schemas y suite completa.

### Cambiar una release fijada

1. Actualizar `upstream_commit` según la política de pin.
2. Registrar el asset exacto y su SHA-256 cuando corresponda.
3. Mantener o actualizar `evidence_commit` según la evidencia auditada real.
4. Reauditar si el cambio puede alterar bundles, classloaders, API o distribución.
5. No promover estados de compatibilidad/localización sin evidencia independiente.

### Añadir localización

1. Crear una revisión bajo `components/<id>/l10n/<revision>/`.
2. Mantener el bundle generado separado de la fuente editable.
3. Actualizar `localization_revision` y estados de forma conservadora.
4. Añadir pruebas de conformidad para claves, estructura, placeholders y bytes.
5. No declarar distribución hasta que exista un mecanismo soportado.

---

## 11. Invariantes del eje de componentes

Romper cualquiera de estas reglas requiere una decisión arquitectónica explícita:

1. El registry contiene identidad, no estado dinámico por versión.
2. El lockfile contiene pins y estados de un objetivo QuPath concreto.
3. `qupath-core` es único y no tiene `components/qupath-core/`.
4. Una extensión auditada conserva un snapshot trazable por `evidence_commit`.
5. Un pin `UPSTREAM_RELEASE` con asset independiente tiene URL y SHA-256.
6. Registrar un componente no implica vendorizar código upstream.
7. Localización, validación, compatibilidad y distribución son afirmaciones separadas.
8. Los `.properties` distribuidos bajo `components/**/l10n/**/dist/` se conservan byte a
   byte mediante `.gitattributes`.
9. Los schemas y sus instancias deben validar en CI.
10. No se relajan tests o invariantes para hacer pasar un estado que la evidencia no
    sustenta.

---

## 12. ADRs

Las decisiones estructurales aceptadas se registran en [`docs/adr/`](adr/):

- ADR-0001 — arquitectura de dos ejes;
- ADR-0002 — QuPath Core fuera de `components/`;
- ADR-0003 — no vendoring y forks satélite sólo cuando sean necesarios.

Un cambio que contradiga una decisión aceptada debe añadir un ADR que la sustituya o
la modifique; no basta con cambiar silenciosamente código o documentación.