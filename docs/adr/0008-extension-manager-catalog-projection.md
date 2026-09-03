# ADR-0008 — Proyección al catálogo del Extension Manager

- Estado: Aceptado
- Fecha: 2026-09-03

## Contexto

QuPath 0.7.0 incluye un Extension Manager capaz de consumir catálogos JSON. La
auditoría inicial identificó esta capacidad como la proyección natural para que un
tercero pueda responder «qué extensiones están soportadas» sin leer código.

El esquema consumido por QuPath se mantiene upstream en
`qupath/extension-catalog-model`. Para esta decisión se verificó el modelo en el commit:

```text
89dd551c81db0b16455fc172a05ada694ac013ae
```

Sus modelos son `Catalog`, `Extension`, `Release` y `VersionRange`, serializados con
nombres `lower_case_with_underscores` como `main_url` y `version_range`.

La misma auditoría marcó otra restricción: publicar una URL de catálogo es costoso de
revertir porque los usuarios pueden fijarla. Por tanto, **generar el catálogo** y
**publicar/registrar una URL estable** son decisiones separadas.

## Decisión

Se añade:

```text
catalog/catalog.json
schemas/extension-catalog.schema.json
tools/catalog_projection.py
```

`catalog/catalog.json` es un artefacto generado. No se edita a mano. Su fuente de verdad
son:

```text
components/registry.json
versions/<v>/components.lock.json
versions/<v>/localizations.lock.json
```

La proyección inicial es para:

```text
QuPath 0.7.0
locale es
```

### Gate de publicación de una extensión

Una entrada `QUPATH_EXTENSION` sólo puede aparecer en el catálogo cuando, para el
objetivo y locale seleccionados, se cumplen simultáneamente:

1. `translation_status = TRANSLATED`;
2. `validation_status = VALIDATED`;
3. `distribution_status = DISTRIBUTED`;
4. `runtime_compatibility != NOT_VERIFIED`;
5. existe un tag de release semántico admitido por el modelo del Extension Manager;
6. existe `artifact_name`;
7. existe `artifact_url` HTTPS bajo `github.com/<repository>/releases/download/...`;
8. existe `artifact_sha256` fijado en metadata.

Los estados lingüísticos y de runtime permanecen independientes. En particular,
`DISTRIBUTED` en el eje lingüístico **no** se interpreta como compatibilidad runtime.

### QuPath Core

`qupath-core` nunca se proyecta. El catálogo del Extension Manager describe extensiones,
no la aplicación base. Core continúa gobernado por `versions/<v>/`, release engineering
y sus fingerprints.

### Rango de versión

La primera proyección fija cada release exactamente a:

```json
{
  "min": "v0.7.0",
  "max": "v0.7.0"
}
```

El modelo upstream define `min` y `max` como límites inclusivos. Restringir al target
congelado evita convertir `declared_qupath_api` o una inferencia estática en una promesa
de compatibilidad con otras versiones de QuPath.

### Artefactos upstream frente a forks satélite

Cuando no existe fork, el `main_url` se toma exclusivamente del release asset ya fijado
en `components.lock.json` y se comprueba que pertenezca al repositorio registrado.

Un `fork_repo`/`fork_tag` **no puede reutilizar implícitamente el `artifact_url`
upstream**. El contrato actual de `components.lock.json` conserva provenance del asset
upstream, pero todavía no modela un asset de distribución de un fork satélite. Si una
extensión distribuida requiere fork, la proyección falla cerrada hasta que exista un
contrato explícito de provenance del artefacto del fork.

Esto evita publicar en el catálogo un JAR distinto del que realmente contiene o soporta
la localización.

### `starred`

La proyección usa `starred: false`. La prioridad `P0/P1` del registro expresa prioridad
del proyecto de localización, no una recomendación general del Extension Manager. No se
mezclan ambas semánticas.

## Estado inicial esperado

El catálogo inicial contiene:

```json
"extensions": []
```

Esto es correcto y deliberado.

- Core está `DISTRIBUTED`, pero no es una extensión.
- InstanSeg tiene materialización piloto, pero continúa `IN_PROGRESS`,
  `NOT_VALIDATED`, `UNSUPPORTED` y `runtime_compatibility = NOT_VERIFIED`.
- Las otras extensiones tampoco cumplen el gate completo.

Un catálogo vacío representa fielmente «cero extensiones publicables hoy». Añadir JARs
upstream sólo porque existen releases sería una afirmación falsa de soporte de
`qupath-es`.

## Validación offline

`schemas/extension-catalog.schema.json` replica de forma cerrada los campos estructurales
relevantes del modelo upstream. CI no instala Pydantic ni hace peticiones HTTP: el
repositorio mantiene su política de cero dependencias Python de terceros y tests
reproducibles/offline.

La validación de accesibilidad HTTP que el modelo upstream realiza pertenece a una futura
fase de publicación, no a la proyección determinista.

## Publicación deliberadamente excluida

Este ADR **no**:

- registra el catálogo en QuPath;
- publica una URL como contrato estable;
- crea un repositorio de catálogo separado;
- crea tags o GitHub Releases;
- cambia estados de ninguna extensión;
- crea el fork satélite de InstanSeg;
- modifica el issue upstream #2190.

Publicar una URL sólo debe ocurrir cuando exista al menos una extensión que cumpla el
gate completo y se haya decidido explícitamente la URL estable.

## Invariantes

1. `catalog/catalog.json` es generado, no fuente de verdad.
2. Core nunca aparece en `extensions[]`.
3. `NOT_VERIFIED` nunca se convierte en catálogo publicable.
4. `UNSUPPORTED` o `NOT_VALIDATED` nunca se convierten en catálogo publicable.
5. Una extensión distribuible exige asset GitHub con SHA-256 fijado.
6. El `main_url` debe pertenecer al repositorio registrado.
7. Un fork satélite exige provenance explícito de su propio artefacto antes de
   proyectarse.
8. `P0/P1` no se transforma en `starred`.
9. La primera proyección sólo afirma compatibilidad con QuPath 0.7.0.
10. Un catálogo vacío es válido cuando ninguna extensión cumple el gate.
11. Generar el catálogo no equivale a publicar una URL de catálogo.
12. Este cambio no modifica Core, bundles, TSV, pins, estados ni traducciones.

## Trabajo posterior

Cuando una extensión alcance el gate completo, el mismo generador deberá producir una
entrada real sin edición manual. Antes de exponerla a usuarios habrá que decidir y probar
la URL estable del catálogo y validar su consumo en QuPath.

Si el primer artefacto distribuible es un fork satélite, antes se ampliará el modelo de
provenance para distinguir explícitamente el asset upstream del asset del fork.

## Referencias

- [`0001-two-axis-component-architecture.md`](0001-two-axis-component-architecture.md)
- [`0004-language-axis.md`](0004-language-axis.md)
- [`0007-path-scoped-component-ci.md`](0007-path-scoped-component-ci.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../../catalog/catalog.json`](../../catalog/catalog.json)
- [`../../tools/catalog_projection.py`](../../tools/catalog_projection.py)
