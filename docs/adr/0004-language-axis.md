# ADR-0004 — Eje explícito de idioma para localizaciones

- Estado: Aceptado
- Fecha: 2026-09-03

## Contexto

La arquitectura de componentes separa identidad estable y objetivo QuPath, pero el
estado lingüístico seguía siendo implícitamente español. En
`versions/<v>/components.lock.json` cada componente tenía una única
`localization_revision`, un único `translation_status`, un único
`validation_status` y un único `distribution_status`.

Ese modelo es suficiente mientras sólo exista `es`, pero deja de ser determinista en
cuanto una misma revisión de componente pueda tener material para dos idiomas. Codificar
el idioma dentro del nombre de una revisión o inferirlo del nombre de un `.properties`
mezclaría dimensiones con ciclos de vida distintos.

Al mismo tiempo, el corpus español existente ya tiene rutas, hashes y pruebas estables.
Mover `versions/0.7.0/work/translation.tsv` o
`components/instanseg/l10n/v0.1.7/` sólo para introducir otra dimensión produciría una
migración innecesaria y arriesgaría artefactos que hoy están verificados.

## Decisión

Introducir una tercera proyección explícita y versionada:

```text
components/registry.json
        identidad del componente

versions/<v>/components.lock.json
        pin, provenance y compatibilidad del componente para QuPath <v>

versions/<v>/localizations.lock.json
        estado lingüístico por (component_id, locale) para QuPath <v>
```

`localizations.lock.json` registra por cada par `(component_id, locale)`:

- `revision`: revisión lingüística cuando exista;
- `source_of_truth`: ruta exacta del material editable;
- `dist_bundle`: ruta exacta del bundle generado;
- `dist_sha256`: SHA-256 exacto de los bytes del bundle generado cuando existe;
- `translation_status`;
- `validation_status`;
- `distribution_status`.

Las rutas son explícitas para no obligar a cambiar el árbol español actual. Una futura
localización puede usar otra estructura física sin codificar esa decisión dentro del ID
del componente ni de la revisión.

El fingerprint pertenece a la proyección lingüística porque identifica el artefacto
generado de un locale concreto. No se coloca en `components.lock.json`, donde los hashes
describen artefactos upstream del componente y no bundles de traducción.

`dist_sha256` no sustituye la validación semántica ni el estado de distribución. Su
función es más estrecha: convertir la identidad byte a byte del artefacto materializado
en un contrato verificable. Si `dist_bundle` es `null`, el fingerprint también lo es; si
hay bundle, ambos son obligatorios y el hash debe coincidir con `Path.read_bytes()`.

El locale se expresa como etiqueta de idioma con guiones, compatible con el modelo de
`Locale.forLanguageTag` usado por el runtime. El contrato no está limitado a `es`.

## Transición

En E1 no se eliminan todavía los cuatro campos lingüísticos históricos de
`components.lock.json`. Para preservar compatibilidad con las herramientas actuales, el
estado `es` de `localizations.lock.json` debe ser un espejo exacto de:

- `localization_revision`;
- `translation_status`;
- `validation_status`;
- `distribution_status`.

La suite verifica esa igualdad. Por tanto, durante la transición no puede existir una
divergencia silenciosa entre ambas representaciones.

La eliminación de esos campos históricos pertenece a una fase posterior de release
engineering. E1 sólo introduce el eje de idioma y su contrato ejecutable. F-006 añade
el fingerprint de distribución sin cambiar esa transición ni promover estados.

## Consecuencias

### Positivas

- el idioma deja de estar implícito en nombres de columnas, revisiones o bundles;
- una misma versión de QuPath y un mismo componente pueden representar varios locales
  sin duplicar identidad ni pins upstream;
- los estados de traducción, validación y distribución quedan correctamente asociados
  al idioma al que pertenecen;
- cada bundle materializado queda identificado por SHA-256 en la misma entrada que
  declara su ruta;
- el corpus español conserva exactamente sus rutas y bytes actuales;
- runtime compatibility continúa siendo una propiedad del componente fijado, no del
  idioma;
- añadir otro locale no exige modificar el schema ni los tests de identidad del corpus.

### Costes

- durante la transición existe un espejo español en dos ficheros, aunque CI exige
  igualdad exacta;
- un cambio legítimo de bytes en un bundle exige actualizar explícitamente su
  `dist_sha256` en el mismo PR;
- las herramientas que hoy consumen directamente los campos lingüísticos del component
  lock deberán migrarse antes de poder retirar el espejo;
- el instalador y la auditoría lingüística siguen siendo españoles en E1 y no se
  generalizan en este cambio.

## Invariantes derivadas

1. `(component_id, locale)` es único dentro de un localization lock.
2. `component_id` debe pertenecer al registry.
3. El `qupath_version` del localization lock debe coincidir con el component lock del
   mismo directorio de versión.
4. Un estado `NOT_STARTED` no puede declarar revisión, fuente, bundle ni fingerprint y
   debe ser `NOT_APPLICABLE` / `UNSUPPORTED` para validación y distribución.
5. Una localización iniciada debe apuntar a una fuente y un bundle existentes dentro del
   repositorio.
6. Todo `dist_bundle` materializado debe declarar un `dist_sha256` SHA-256 en mayúsculas
   que coincida exactamente con los bytes versionados.
7. El localization lock no duplica commits, artefactos, compatibilidad runtime, forks ni
   otros pins del component lock.
8. Mientras exista el espejo legado, los cuatro campos españoles deben coincidir byte a
   byte en significado con la entrada `locale = es`.
9. E1/F-006 no mueven ni reescriben los TSV o `.properties` existentes.

## Alternativas descartadas

### Añadir `locale` a `components/registry.json`

Descartado porque el idioma no forma parte de la identidad de un componente upstream.

### Codificar el idioma dentro de `localization_revision`

Descartado porque mezcla revisión lingüística e identidad de idioma y vuelve difícil
comparar la misma revisión entre locales.

### Mover ahora todo a `l10n/<locale>/<revision>/`

Descartado en E1 porque obligaría a mover el piloto InstanSeg y a cambiar rutas ya
probadas sin necesidad funcional inmediata. Las rutas explícitas permiten una migración
posterior, si llega a justificarse.

### Mantener fingerprints en un fichero paralelo

Descartado en F-006 porque duplicaría la clave `(component_id, locale)` y permitiría
divergencia entre la ruta declarada y el hash que pretende identificarla. El fingerprint
de distribución pertenece a la misma entrada que el bundle.

### Convertir inmediatamente `components.lock.json` a un mapa de locales

Descartado para E1 porque mezclaría una migración de contrato grande con la introducción
del eje. La proyección separada mantiene el cambio pequeño, reversible y verificable.

## Referencias

- [`0001-two-axis-component-architecture.md`](0001-two-axis-component-architecture.md)
- [`../COMPONENTS.md`](../COMPONENTS.md)
- [`../../versions/0.7.0/components.lock.json`](../../versions/0.7.0/components.lock.json)
- [`../../versions/0.7.0/localizations.lock.json`](../../versions/0.7.0/localizations.lock.json)
- [`../../schemas/localizations-lock.schema.json`](../../schemas/localizations-lock.schema.json)
