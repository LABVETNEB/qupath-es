# ADR-0002 — QuPath Core fuera de `components/`

- Estado: Aceptado
- Fecha: 2026-09-03

## Contexto

QuPath Core forma parte del corpus y debe aparecer en el registro y en cada lockfile para que identidad, provenance y versión objetivo sean explícitas. Sin embargo, el Core ya tiene una autoridad versionada propia bajo `versions/<v>/`: bundle canónico, TSV, distribución, fingerprints e informes.

Crear además `components/qupath-core/` duplicaría esa autoridad y abriría dos rutas posibles para representar la misma base.

## Decisión

`qupath-core` permanece como entrada única en:

- `components/registry.json`;
- `versions/<v>/components.lock.json`.

No se crea `components/qupath-core/`.

Los artefactos de localización y evidencia específicos del Core continúan bajo `versions/<v>/`.

## Consecuencias

### Positivas

- existe una sola autoridad para la base canónica de una versión de QuPath;
- se evita duplicar bundles, fingerprints, traducciones o informes;
- el Core puede participar en el mismo modelo de identidad/pin sin fingir que es una extensión.

### Costes

- el árbol de componentes no es perfectamente uniforme;
- las herramientas genéricas deben reconocer explícitamente el tipo `QUPATH_CORE`.

Ese coste es deliberado: una abstracción uniforme no justifica duplicar una fuente de verdad.

## Invariantes derivadas

- debe existir exactamente un componente `QUPATH_CORE` y su ID es `qupath-core`;
- su `entry_point` es `null`;
- `components/qupath-core/` no debe existir;
- las bases de Core permanecen bajo `versions/<v>/`.

Estas reglas están cubiertas por tests y no deben relajarse para acomodar tooling de extensiones.

## Alternativas descartadas

### Crear un directorio Core vacío

Descartado porque sugiere una autoridad que no existe y facilita que en el futuro se añadan datos duplicados.

### Mover toda la versión Core a `components/qupath-core/`

Descartado porque rompería la arquitectura versionada del bundle principal y mezclaría el objetivo QuPath con la identidad estable del componente.

## Referencias

- [`../COMPONENTS.md`](../COMPONENTS.md)
- [`../../components/registry.json`](../../components/registry.json)
- [`../../versions/0.7.0/`](../../versions/0.7.0/)