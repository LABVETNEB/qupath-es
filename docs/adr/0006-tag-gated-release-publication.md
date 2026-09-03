# ADR-0006 — Publicación desde tag existente con provenance attestation

- Estado: Aceptado
- Fecha: 2026-09-03

## Contexto

ADR-0005 introdujo un builder reproducible, un manifest, un SBOM SPDX 2.3 y
`SHA256SUMS`, pero deliberadamente dejó fuera tags, GitHub Releases y attestations.

La segunda mitad de F-012 / E2 debe conectar esos artefactos con una publicación pública
sin reintroducir ambigüedad entre «lo que está en `main`», «lo que señala el tag» y «lo
que descarga un tercero».

El riesgo principal no es sólo un hash incorrecto. También hay que impedir:

- publicar desde una rama no fusionada;
- crear un tag implícitamente desde el workflow;
- construir desde bytes diferentes al commit etiquetado;
- incorporar un bundle no `DISTRIBUTED`;
- publicar antes de verificar provenance;
- depender de una action flotante;
- reemplazar silenciosamente un release o sus assets;
- borrar automáticamente evidencia cuando una publicación parcial falla.

## Decisión

Añadir `.github/workflows/release.yml` como único camino automatizado de publicación.

El workflow es exclusivamente `workflow_dispatch`. No escucha `push.tags`; crear o
subir un tag no publica por sí solo.

La ejecución debe ser solicitada explícitamente con el tag existente como `ref`.

## Preflight del ref

Antes del build, `tools/release_guard.py preflight` exige simultáneamente:

1. `GITHUB_REF` pertenece a `refs/tags/`.
2. El nombre del tag cumple el contrato de seguridad de nombres.
3. `HEAD`, el tag y `GITHUB_SHA` resuelven al mismo commit completo de 40 caracteres.
4. El commit etiquetado es ancestro de `refs/remotes/origin/main`.
5. La release spec puede leerse y validarse desde ese mismo commit.
6. Los canonical fingerprints siguen coincidiendo byte a byte.
7. La versión objetivo figura como `stable`.
8. La identidad del bundle Core no diverge entre metadata histórica y el language axis.

Un tag que apunte a una rama no fusionada no es suficiente autoridad para publicar.

## Suite previa

El workflow vuelve a ejecutar:

```text
python -m compileall -q tools
python -m unittest discover -s tests -p "test_*.py" -v
```

La publicación no depende exclusivamente del CI que pudo haber corrido antes de crear
el tag.

## Build

El workflow llama al builder de ADR-0005 con:

```text
source_commit = GITHUB_SHA
release_tag   = GITHUB_REF_NAME
```

No reimplementa el empaquetado en YAML.

Después, `release_guard.py verify-outputs` verifica de forma independiente que sólo
existan las cuatro salidas esperadas y que ZIP, manifest, SBOM y `SHA256SUMS` sean
coherentes.

## Attestation

La provenance se genera con la action oficial `actions/attest`, fijada a un SHA completo
correspondiente a una release inmutable de la action.

Los cuatro outputs son sujetos de la misma attestation mediante `subject-path`. Se evita
`subject-checksums` como dependencia del contrato: `SHA256SUMS` es un artefacto publicado
y también debe ser sujeto firmado.

Antes de publicar, cada fichero local se verifica con GitHub CLI exigiendo:

- repositorio exacto;
- `.github/workflows/release.yml` como signer workflow;
- ref fuente exacto;
- commit fuente exacto;
- runner no self-hosted.

La attestation se genera antes de `gh release create`. Si no puede firmarse o
verificarse, no hay publicación.

## Permisos

El workflow declara únicamente los permisos necesarios para su función:

```text
contents: write
id-token: write
attestations: write
artifact-metadata: write
```

`actions/checkout` usa `persist-credentials: false`, de modo que el token de escritura no
queda almacenado en la configuración Git del checkout.

## Publicación

El release se crea con GitHub CLI y `--verify-tag`.

Esto tiene dos propiedades obligatorias:

1. el workflow no puede crear un tag implícito;
2. la lista de assets proviene exclusivamente del directorio de outputs ya verificado.

No se usa `--clobber`.

El workflow no elimina automáticamente tags, releases ni assets ante un error. Un fallo
parcial requiere inspección manual.

## Verificación posterior

Después de publicar deben pasar:

```text
gh release verify <tag>
gh release verify-asset <tag> <cada-output>
```

La primera prueba comprueba que el release esté acompañado por una attestation válida;
la segunda comprueba cada asset descargable contra su provenance.

## Trigger y control humano

El tag se crea fuera del workflow. La ejecución del workflow es una segunda acción
deliberada.

Por tanto:

```text
push tag != publish release
```

El operador puede auditar el tag antes de iniciar la publicación.

## Consecuencias

### Positivas

- un release público sólo puede derivar de un commit ya contenido en `main`;
- el tag, el checkout, el manifest y la provenance quedan anclados al mismo SHA;
- el workflow no puede inventar tags;
- el release conserva los cuatro artefactos definidos en ADR-0005;
- provenance se firma con OIDC/Sigstore mediante GitHub artifact attestations;
- los usuarios pueden verificar el release con GitHub CLI;
- las actions críticas quedan fijadas a SHAs completos;
- un fallo previo a publicación no crea un release público;
- la ausencia de cleanup automático conserva evidencia ante fallos parciales.

### Costes

- publicar requiere dos acciones explícitas: crear tag y disparar el workflow;
- el runner necesita una versión de GitHub CLI que soporte `release verify`,
  `release verify-asset` y `attestation verify`;
- el workflow requiere permisos de escritura que el CI ordinario no necesita;
- una verificación posterior puede dejar un release visible pero un run rojo, lo que exige
  investigación manual.

## Invariantes derivadas

1. El workflow de release no tiene trigger `push`.
2. El workflow nunca ejecuta `git tag` ni crea refs.
3. Todo release parte de `refs/tags/...`.
4. El commit etiquetado debe estar contenido en `origin/main`.
5. `persist-credentials` permanece deshabilitado en checkout.
6. Se ejecuta la suite completa antes del build.
7. El builder de ADR-0005 es la única implementación del empaquetado.
8. Los cuatro outputs pasan `verify-outputs` antes de la attestation.
9. La attestation precede a `gh release create`.
10. La action de attestation está fijada a SHA completo.
11. `gh release create` usa `--verify-tag`.
12. No se usa `--clobber`.
13. Los cuatro assets deben pasar verificación posterior.
14. El workflow no borra automáticamente releases, tags ni assets.

## No decisión

Este ADR no crea el primer tag ni el primer GitHub Release. Implementa el mecanismo. La
primera publicación real es una operación posterior y explícita del mantenedor, una vez
que el workflow esté fusionado, sincronizado y verificado.

## Referencias

- [`0005-reproducible-release-artifacts.md`](0005-reproducible-release-artifacts.md)
- [`../RELEASING.md`](../RELEASING.md)
- [`../../tools/release_guard.py`](../../tools/release_guard.py)
- [`../../.github/workflows/release.yml`](../../.github/workflows/release.yml)
