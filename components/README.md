# Registro de componentes

`components/registry.json` es la fuente de verdad para la **identidad estable** de los componentes que forman el corpus de `qupath-es`.

Esta capa no fija versiones de extensiones, compatibilidad con una versión concreta de QuPath, artefactos, hashes ni estados de traducción. Esos datos pertenecen al futuro `versions/<qupath-version>/components.lock.json`.

## Modelo de dos ejes

```text
components/registry.json
    identidad estable del componente
            │
            └──────────────┐
                           │
versions/<v>/components.lock.json
    pines reproducibles para una versión de QuPath
```

El registro responde **qué componentes existen y cómo se identifican**. El lockfile responderá **qué versión exacta de cada componente queda certificada para una versión concreta de QuPath**.

## Identificadores

Los `id` son estables, únicos y en `kebab-case`. Cambiarlos después de que existan lockfiles, auditorías, rutas, parches o forks sería una migración costosa.

Los 13 identificadores iniciales son:

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

## Campos de identidad

Cada entrada registra:

- `id`: identificador estable interno de `qupath-es`.
- `canonical_name`: nombre canónico del repositorio upstream.
- `repository`: repositorio upstream en formato `owner/name`.
- `owner`: propietario upstream.
- `type`: `QUPATH_CORE` o `QUPATH_EXTENSION`.
- `priority`: prioridad del corpus (`BASE`, `P0`, `P0/P1`, `P1`).
- `role`: función principal, en una línea.
- `license`: identificador SPDX observado en upstream.
- `build_system`: sistema de construcción observado.
- `entry_point`: mecanismo de carga de la extensión; `null` para QuPath Core.
- `satellite_fork`: repositorio de fork satélite si llega a existir; actualmente `null`.
- `first_registered`: fecha de alta del identificador en el registro.

## Qué no pertenece al registro

El registro deliberadamente no contiene:

- versión o tag seleccionado para una versión de QuPath;
- commit upstream fijado;
- compatibilidad certificada;
- nombre, URL o hash de artefacto;
- revisión de localización;
- estado de auditoría;
- estado de traducción;
- estado de validación;
- estado de distribución;
- parches concretos.

Esos datos cambian con mayor frecuencia y pertenecen a los lockfiles o a las auditorías por componente.

## QuPath Core

QuPath Core aparece en el registro para que su identidad, procedencia y licencia se encuentren en el mismo índice que las extensiones. Sin embargo, **no se trata como una extensión** y no necesita un directorio `components/qupath-core/`: su base versionada permanece bajo `versions/<v>/`.

## Código de terceros

Registrar un componente **no significa vendorizarlo**. `qupath-es` no copia aquí el código fuente upstream. El registro conserva identidad y procedencia; futuras traducciones, auditorías o parches se añadirán sólo cuando un PR específico lo justifique.

## Estado de esta fase

PR1 crea únicamente la capa de identidad:

```text
schemas/component-registry.schema.json
components/registry.json
components/README.md
tests/test_component_registry.py
```

No crea lockfiles, directorios por componente, traducciones, forks, parches ni cambios de CI.
