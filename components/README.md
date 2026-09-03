# Registro y corpus de componentes

`components/` contiene la **identidad estable**, las políticas de auditoría y la evidencia versionada de las extensiones que forman el corpus de `qupath-es`.

La especificación completa del modelo está en [`docs/COMPONENTS.md`](../docs/COMPONENTS.md). Las decisiones estructurales están registradas en [`docs/adr/`](../docs/adr/).

## Modelo de dos ejes

```text
components/registry.json
    identidad estable del componente
            │
            └──────────────┐
                           │
versions/<v>/components.lock.json
    pins, provenance y estados para un objetivo QuPath
```

El registro responde **qué componente es**. El lockfile responde **qué revisión queda fijada y qué estado tiene para una versión concreta de QuPath**.

Esta separación es una decisión arquitectónica aceptada: ver [ADR-0001](../docs/adr/0001-two-axis-component-architecture.md).

## Fuentes de verdad

- `registry.json`: identidad estable de los 13 componentes del corpus.
- `../schemas/component-registry.schema.json`: contrato ejecutable del registro.
- `../versions/<v>/components.lock.json`: pin reproducible por objetivo QuPath.
- `../schemas/components-lock.schema.json`: contrato ejecutable del lockfile.
- `<id>/component.json`: política de auditoría de una extensión.
- `<id>/audits/<evidence_commit>.json`: evidencia observada en un commit concreto.
- `<id>/l10n/<revision>/`: material de localización cuando existe.
- `<id>/patches/`: parches reproducibles sólo cuando sean necesarios.

## Identificadores

Los `id` son estables, únicos y en `kebab-case`:

- `qupath-core`
- `dl-pixel-classifier`
- `tiatoolbox`
- `instanseg`
- `cell-analysis-tools`
- `training`
- `stardist`
- `cellpose`
- `wsinfer`
- `djl`
- `bioimageio`
- `sam`
- `image-export-toolkit`

Cambiar un ID publicado afecta lockfiles, rutas, auditorías, localizaciones, parches y automatización; por tanto requiere una migración explícita.

## Qué pertenece al registro

Cada entrada de `registry.json` conserva únicamente identidad relativamente estable:

- `id`;
- `canonical_name`;
- `repository`;
- `owner`;
- `type`;
- `priority`;
- `role`;
- `license`;
- `build_system`;
- `entry_point`;
- `satellite_fork`;
- `first_registered`.

Tags, commits, hashes, compatibilidad, revisión de localización y estados de validación/distribución **no pertenecen al registro**; van al lockfile del objetivo QuPath.

## Pin y evidencia

El lockfile distingue dos commits con semántica diferente:

- `upstream_commit`: revisión fijada por la política de pin;
- `evidence_commit`: revisión de la que existe un snapshot de auditoría versionado.

No deben suponerse iguales. Una auditoría puede observar una cabeza upstream posterior sin mover silenciosamente el pin de una release.

Para `pin_basis = UPSTREAM_RELEASE`, el lockfile registra además el `artifact_name`, `artifact_url` y `artifact_sha256` del asset fijado. El schema exige esos campos y `tools/verify_artifacts.py` permite verificarlos bajo demanda.

## QuPath Core

QuPath Core figura en registry y lockfile para compartir el mismo modelo de identidad y provenance, pero **no es una extensión** y no tiene `components/qupath-core/`.

Su base versionada permanece bajo `versions/<v>/`. Duplicarla aquí crearía dos fuentes de verdad. Esta invariante está cubierta por tests y formalizada en [ADR-0002](../docs/adr/0002-core-outside-components.md).

## Código de terceros

Registrar o auditar un componente **no significa vendorizarlo**. `qupath-es` conserva metadatos, evidencia, traducciones, hashes y parches reproducibles; no copia el árbol upstream completo.

Si un cambio de código resulta imprescindible para localización, se prioriza upstream y sólo se contempla un fork satélite separado cuando esté justificado. Ver [ADR-0003](../docs/adr/0003-no-vendoring-satellite-forks.md).

## Localización de extensiones

La presencia de `components/<id>/l10n/<revision>/` significa que existe material de localización. No implica automáticamente que esté:

- terminado;
- validado;
- compatible en runtime;
- instalable;
- distribuido.

Esas afirmaciones se registran por separado en `translation_status`, `validation_status`, `runtime_compatibility` y `distribution_status`.

El piloto actual de InstanSeg está representado de forma conservadora como trabajo `IN_PROGRESS`, no como distribución soportada.

## Validación

Antes de fusionar cambios en registry o lockfile:

```powershell
python tools/schema_validate.py schemas/component-registry.schema.json components/registry.json
python tools/schema_validate.py schemas/components-lock.schema.json versions/0.7.0/components.lock.json
python -m unittest discover -s tests -p "test_*.py"
```

CI repite la suite en Ubuntu y Windows y mantiene separado el check de integridad del bundle canónico.