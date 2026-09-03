# Publicación de releases

Este documento describe el procedimiento de mantenimiento para publicar un release de
`qupath-es`. La publicación está separada de la construcción: el repositorio puede
construir y probar artefactos sin crear tags ni GitHub Releases.

## Principio

El workflow `.github/workflows/release.yml` **nunca crea un tag**. Sólo puede ejecutarse
manualmente sobre un tag que ya exista y cuyo commit esté contenido en `main`.

La secuencia es:

```text
main verde
  -> tag creado por el mantenedor
  -> workflow_dispatch sobre ese tag
  -> preflight fail-closed
  -> suite completa
  -> build reproducible
  -> verificación de ZIP/manifest/SBOM/checksums
  -> provenance attestation
  -> verificación local de la attestation
  -> GitHub Release
  -> verificación del release y de cada asset
```

No hay trigger `push.tags`: subir un tag no publica nada por sí solo.

## Qué se publica

La especificación `versions/<qupath-version>/release-<locale>.json` decide el payload.
Para QuPath 0.7.0 / `es`, el builder produce exactamente:

```text
qupath-es-0.7.0-es.zip
qupath-es-0.7.0-es.manifest.json
qupath-es-0.7.0-es.spdx.json
qupath-es-0.7.0-es.SHA256SUMS
```

Los cuatro ficheros se incluyen como sujetos de una provenance attestation.

## Precondiciones

Antes de crear el tag:

1. `main` debe estar sincronizado y limpio.
2. El CI del commit que se quiere publicar debe estar verde.
3. La release spec debe estar validada por la suite.
4. Toda localización que entre al paquete debe ser `TRANSLATED`, `VALIDATED` y
   `DISTRIBUTED`.
5. Debe conocerse el SHA exacto que se quiere etiquetar.

El workflow vuelve a comprobar estas condiciones; no confía en que se hayan hecho a
mano.

## Crear el tag

La creación del tag es una acción deliberada del mantenedor y se hace fuera del
workflow. Ejemplo:

```powershell
Set-Location C:\qupath-es

git switch main
git fetch origin --prune --tags
git pull --ff-only origin main
git status
git rev-parse HEAD

git tag -a <release-tag> -m "qupath-es release"
git push origin <release-tag>
```

No use un tag que apunte a una rama no fusionada. Aunque se intentara, el preflight lo
rechazaría porque el commit etiquetado debe ser ancestro de `origin/main`.

Crear el tag **no publica** el release.

## Ejecutar el workflow

La forma determinista es GitHub CLI:

```powershell
gh workflow run release.yml `
  --ref <release-tag> `
  -f spec=versions/0.7.0/release-es.json
```

El parámetro `--ref` debe ser el tag existente. Ejecutar el workflow sobre `main` o una
rama falla inmediatamente.

El workflow usa únicamente la release spec indicada como input. El input se pasa por una
variable de entorno y no se interpola directamente dentro de un comando shell.

## Gates previos a publicación

`tools/release_guard.py preflight` prueba:

- el evento usa `refs/tags/...`;
- el tag y `HEAD` resuelven al mismo commit de 40 caracteres;
- el commit está contenido en `origin/main`;
- la release spec se puede validar desde ese mismo commit;
- los bundles del spec coinciden exactamente con las localizaciones `DISTRIBUTED`;
- los fingerprints canónicos conservan SHA-256 y tamaño;
- la versión objetivo está declarada `stable`;
- los hashes Core publicados no divergen entre fingerprint, localization lock y
  `supported-versions.json`.

Luego se ejecuta toda la suite protegida antes del build.

## Construcción y verificación

`tools/build_release.py` lee los bytes desde los blobs Git del commit etiquetado, no
desde el working tree. Después, `tools/release_guard.py verify-outputs` vuelve a verificar
de forma independiente:

- que existen exactamente cuatro outputs;
- SHA-256 y tamaño del ZIP;
- SHA-256 y tamaño del SBOM;
- hash externo del manifest mediante `SHA256SUMS`;
- estructura y contenido de `SHA256SUMS`;
- coherencia entre manifest y SPDX 2.3.

## Provenance attestation

El workflow usa `actions/attest` fijado a un SHA completo. Los permisos se limitan a:

```text
contents: write
id-token: write
attestations: write
artifact-metadata: write
```

Antes de publicar, cada fichero local debe pasar `gh attestation verify` exigiendo:

- este repositorio;
- `.github/workflows/release.yml` como signer workflow;
- el mismo `refs/tags/<tag>`;
- el mismo commit fuente;
- runner no self-hosted.

Si alguna prueba falla, no se ejecuta `gh release create`.

## Publicación

La publicación usa:

```text
gh release create <tag> ... --verify-tag
```

`--verify-tag` impide que GitHub CLI cree un tag implícitamente. Los cuatro outputs
verificados son los únicos assets suministrados al comando.

No se usa `--clobber`, no se reemplazan assets existentes y el workflow no borra
automáticamente releases o tags ante un fallo.

## Verificación posterior

Después de publicar, el workflow exige:

```powershell
gh release verify <release-tag> -R LABVETNEB/qupath-es
```

y ejecuta `gh release verify-asset` para los cuatro ficheros.

Un usuario puede repetir la comprobación descargando un asset y usando:

```powershell
gh release verify-asset <release-tag> <ruta-al-archivo> `
  -R LABVETNEB/qupath-es
```

La attestation prueba provenance e integridad; no sustituye la revisión del código ni
garantiza que el software sea seguro por sí mismo.

## Fallos

El workflow es fail-closed. No intenta «arreglar» tags, estados o hashes.

Si falla antes de `gh release create`, no existe release público.

Si GitHub CLI falla durante la creación con assets, puede quedar un draft según el punto
exacto del fallo. No hay limpieza automática: el mantenedor debe inspeccionar el estado
antes de reintentar. Esto evita eliminar evidencia o reemplazar assets de forma
silenciosa.

Si la verificación posterior a publicación falla, el run queda rojo y requiere
investigación manual; no se oculta el fallo mediante borrado automático.

## Regla operativa

No publique manualmente con `gh release create` fuera de este workflow. El punto de
control de E2 es que **tag, commit, artefactos, hashes, SBOM y provenance pasen por una
misma cadena verificable**.
