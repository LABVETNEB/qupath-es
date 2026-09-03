# ADR-0005 — Paquetes de release reproducibles y verificables

- Estado: Aceptado
- Fecha: 2026-09-03

## Contexto

El repositorio ya valida que los bundles canónicos y distribuidos conservan sus bytes,
pero hasta F-012 / E2 no existe un artefacto de release propio. GitHub no tiene releases
publicados para `LABVETNEB/qupath-es` y la instalación documentada depende de clonar el
repositorio o descargar el ZIP genérico de GitHub.

Eso deja una brecha entre «el repositorio está validado» y «un tercero puede descargar
un paquete identificable, verificar exactamente qué contiene y reproducir sus bytes».
El eje de idioma y F-006 ya aportan las precondiciones: cada localización distribuida
tiene estado explícito y `dist_sha256`.

E2 se divide en dos PRs para mantener el cambio auditable:

1. contrato y construcción determinista de artefactos;
2. publicación desde un tag existente y attestation de provenance.

Este ADR cubre la primera parte y fija las invariantes que el workflow posterior deberá
respetar.

## Decisión

Cada combinación soportada de versión de QuPath y locale puede declarar una
especificación versionada:

```text
versions/<qupath-version>/release-<locale>.json
```

La especificación es una allowlist explícita del payload. No se empaqueta el árbol
completo por exclusión ni se descubren archivos por glob durante el release.

Para QuPath 0.7.0 / `es`, el paquete conserva las rutas relativas necesarias por el
actualizador existente (`runtime/`, `tools/`, `versions/`, documentación y metadatos).
El ZIP añade únicamente un prefijo de carpeta igual a `artifact_basename`. No renombra
los archivos internos ni introduce otra lógica de instalación.

`tools/build_release.py` genera cuatro salidas:

```text
<artifact_basename>.zip
<artifact_basename>.manifest.json
<artifact_basename>.spdx.json
<artifact_basename>.SHA256SUMS
```

### Fuente binaria del release

El builder no toma los bytes desde el working tree. Lee cada fichero mediante:

```text
git show <source_commit>:<path>
```

y exige un SHA completo de 40 caracteres que resuelva exactamente al commit solicitado.

Esto evita que `core.autocrlf`, atributos locales, timestamps o metadata del filesystem
cambien el artefacto entre Linux y Windows. El commit deja de ser sólo metadata de
provenance y se convierte en la fuente efectiva de todos los bytes del release.

El release spec, sus JSON Schema y `localizations.lock.json` se leen del mismo commit.

### ZIP reproducible

El ZIP se genera con estas reglas:

- payload ordenado lexicográficamente por ruta de archivo;
- bytes copiados desde los blobs Git, sin normalización de texto;
- `ZIP_STORED`, sin compresión dependiente de una versión de zlib;
- timestamp ZIP fijo `1980-01-01 00:00:00`;
- permisos de fichero fijos `0644`;
- sin entradas de directorio, metadata del host ni timestamps del filesystem.

Por tanto, el mismo commit y la misma especificación producen el mismo ZIP en Linux y
Windows.

### Manifiesto

El manifiesto externo registra:

- tag de release;
- commit fuente exacto;
- epoch del commit fuente;
- versión de QuPath y locale;
- nombre, tamaño y SHA-256 del ZIP;
- nombre, tamaño y SHA-256 del SBOM;
- nombre del fichero `SHA256SUMS`;
- por cada fichero del payload: ruta fuente, ruta dentro del ZIP, rol, componente cuando
  corresponda, tamaño y SHA-256.

El manifiesto es externo al ZIP para evitar autorreferencia: el hash del ZIP puede
registrarse sin alterar el propio ZIP.

### SBOM

El SBOM es JSON SPDX 2.3 a nivel de fichero. Describe exactamente el payload
materializado y enlaza cada fichero con su SHA-256. No infiere licencias de cada fichero:
cuando no existe una conclusión específica usa `NOASSERTION`. El documento sí declara
`CC0-1.0` como `dataLicense`, según el formato SPDX.

La fecha `creationInfo.created` se deriva del timestamp del commit fuente. No se usa la
hora del runner.

### Gate de distribución

Un `LOCALIZATION_BUNDLE` sólo puede entrar al release cuando la entrada
`(component_id, locale)` correspondiente en `localizations.lock.json` cumple:

```text
translation_status  = TRANSLATED
validation_status   = VALIDATED
distribution_status = DISTRIBUTED
```

Su ruta debe coincidir con `dist_bundle` y sus bytes con `dist_sha256`.

Además, el payload debe cubrir **exactamente todas** las localizaciones `DISTRIBUTED`
del locale objetivo. Una localización `UNSUPPORTED` o `EXPERIMENTAL` no puede filtrarse
accidentalmente al release, y una nueva localización promovida a `DISTRIBUTED` obliga a
actualizar la especificación antes de que CI vuelva a quedar verde.

## Consecuencias

### Positivas

- el release deja de depender del ZIP genérico del repositorio;
- el payload es una allowlist revisable y machine-readable;
- el paquete puede reproducirse byte a byte entre runners;
- los bytes no dependen de la política de checkout del sistema operativo;
- hashes, manifiesto y SBOM describen el mismo conjunto de bytes;
- el bundle Core conserva su fingerprint F-006 como autoridad de distribución;
- InstanSeg sigue fuera del release mientras su estado sea `UNSUPPORTED`;
- no se necesita ninguna dependencia Python de terceros.

### Costes

- cada fichero nuevo necesario en el paquete debe añadirse explícitamente al spec;
- una localización promovida a `DISTRIBUTED` obliga a actualizar el release spec;
- el ZIP usa `ZIP_STORED`, priorizando reproducibilidad sobre compresión;
- el builder requiere Git y que el commit fuente exista en el repositorio local;
- esta fase todavía no publica un GitHub Release ni crea/valida tags.

## Invariantes derivadas

1. La especificación de release es un contrato cerrado validado por JSON Schema.
2. Ninguna ruta absoluta, `..` o barra invertida puede entrar al payload.
3. Las rutas del payload son únicas y deben existir en el commit fuente.
4. Sólo `LOCALIZATION_BUNDLE` puede declarar `component_id`.
5. El conjunto de bundles del spec coincide exactamente con las localizaciones
   `DISTRIBUTED` del locale.
6. Cada bundle distribuido debe seguir siendo `TRANSLATED` + `VALIDATED` y conservar su
   `dist_sha256`.
7. Spec, schemas, lock y payload proceden del mismo commit de 40 caracteres.
8. Dos builds con los mismos inputs deben producir cuatro salidas byte-idénticas.
9. El ZIP preserva exactamente los bytes de cada blob Git.
10. El SBOM y el manifiesto deben concordar con los bytes realmente producidos.
11. Este PR no crea tags, releases, firmas ni attestations.

## Fase posterior

El workflow de publicación E2 deberá:

1. operar únicamente sobre un tag que ya exista y apunte al commit que se publica;
2. ejecutar la suite protegida antes de construir;
3. invocar este builder con el commit etiquetado, no reimplementar el empaquetado en YAML;
4. publicar ZIP + manifiesto + SBOM + `SHA256SUMS`;
5. generar provenance attestation sobre los artefactos publicados;
6. fallar cerrado ante cualquier divergencia de tag, commit, hash o estado.

## Alternativas descartadas

### Publicar el ZIP automático de GitHub

Descartado como artefacto principal porque no expresa nuestro payload de distribución,
no incorpora el gate de `localizations.lock.json` y su contenido incluye material de
desarrollo que el usuario final no necesita.

### Empaquetar todo el repositorio y excluir ficheros

Descartado porque una denylist deriva silenciosamente cuando aparecen archivos nuevos.
La allowlist hace que la ampliación del release sea una decisión explícita.

### Leer el payload desde el working tree

Descartado porque un checkout Windows puede materializar bytes distintos de los blobs
Git por normalización de finales de línea. Release engineering debe operar sobre la
identidad versionada, no sobre efectos secundarios del checkout.

### Comprimir con DEFLATE

Descartado para el contrato base porque la reproducibilidad binaria puede depender de la
implementación y versión de zlib. El tamaño actual del paquete no justifica ese riesgo.

### Incluir el manifiesto dentro del ZIP

Descartado porque un manifiesto que registra el hash del propio ZIP introduciría una
autorreferencia imposible de cerrar de forma simple.

## Referencias

- [`0004-language-axis.md`](0004-language-axis.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../../versions/0.7.0/localizations.lock.json`](../../versions/0.7.0/localizations.lock.json)
- [`../../schemas/release-spec.schema.json`](../../schemas/release-spec.schema.json)
- [`../../schemas/release-manifest.schema.json`](../../schemas/release-manifest.schema.json)
