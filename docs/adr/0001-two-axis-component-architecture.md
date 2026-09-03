# ADR-0001 — Arquitectura de dos ejes para componentes

- Estado: Aceptado
- Fecha: 2026-09-03

## Contexto

El proyecto necesita representar un corpus de QuPath Core y extensiones sin mezclar dos conceptos con ciclos de vida distintos:

1. la identidad estable de un componente;
2. la revisión exacta de ese componente seleccionada para una versión concreta de QuPath.

Si ambos conceptos se guardan en un único documento, cada cambio de tag, compatibilidad, artefacto o estado de localización obliga a mutar la capa de identidad. Eso dificulta comparar objetivos QuPath, vuelve ambiguos los historiales y favorece datos duplicados.

## Decisión

Adoptar una arquitectura de dos ejes:

- `components/registry.json` contiene identidad estable;
- `versions/<qupath-version>/components.lock.json` contiene pins reproducibles, provenance y estados dependientes del objetivo QuPath.

Los directorios `components/<id>/` conservan políticas, evidencia, localizaciones y parches asociados a la identidad estable, mientras que el lockfile selecciona qué revisión y qué evidencia aplica a cada objetivo.

## Consecuencias

### Positivas

- un `id` mantiene significado a través de distintas versiones de QuPath;
- diferentes objetivos QuPath pueden fijar revisiones distintas sin duplicar identidad;
- provenance, compatibilidad y distribución quedan versionadas junto al objetivo que las consume;
- los cambios de release son revisables como cambios de lockfile, no como redefiniciones del componente.

### Costes

- registry y lockfile deben mantenerse coherentes mediante pruebas;
- algunas consultas requieren combinar ambas fuentes;
- introducir un nuevo campo exige decidir explícitamente si pertenece a identidad estable o a estado por versión.

## Invariantes derivadas

- el registry no contiene tags, commits, hashes ni estados de traducción;
- el lockfile referencia únicamente `component_id` existentes en el registry;
- los IDs son estables y cambiarlos requiere una migración explícita;
- el schema de cada capa se valida automáticamente.

## Alternativas descartadas

### Un único manifiesto global

Descartado porque mezcla identidad con estado mutable y dificulta representar más de un objetivo QuPath.

### Copiar el registro dentro de cada versión

Descartado porque duplica datos estables y crea riesgo de divergencia entre copias.

## Referencias

- [`../COMPONENTS.md`](../COMPONENTS.md)
- [`../../components/registry.json`](../../components/registry.json)
- [`../../versions/0.7.0/components.lock.json`](../../versions/0.7.0/components.lock.json)