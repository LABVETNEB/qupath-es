# ADR-0007 — CI por componente con matriz dinámica basada en rutas

- Estado: Aceptado
- Fecha: 2026-09-03

## Contexto

La arquitectura del repositorio ya tiene un eje explícito de componentes, pins por
versión de QuPath y localizaciones por `(component_id, locale)`. Sin embargo, el CI
principal continúa ejecutando la suite completa de forma monolítica en cada pull request
y en cada push a `main`.

La auditoría de arquitectura del ecosistema había diferido expresamente este paso hasta
que existieran componentes reales materializados. Su diseño recomendado era:

1. checks globales siempre activos;
2. detección de componentes afectados por el diff;
3. matriz dinámica con checks por componente.

Con 12 extensiones esto aún es manejable, pero no escala de forma limpia a 25, 50 o 100
extensiones. Tampoco existe hoy un punto de entrada único para preguntar «¿este
componente sigue siendo coherente con registro, lockfiles y localizaciones?».

Al mismo tiempo, los tres checks actuales (`tests`, `tests (Windows)` y
`canonical bundle integrity`) ya funcionan como protección estable. Reducirlos en el
mismo PR que introduce selección por rutas mezclaría optimización de costes con un
cambio de cobertura y haría más difícil detectar regresiones.

## Decisión

Se adopta una migración **aditiva**.

Los tres jobs protegidos existentes conservan sus nombres y comportamiento. Se añaden:

```text
component detection
component (<component_id>)
```

La primera fase no intenta ahorrar minutos eliminando pruebas globales. Introduce la
arquitectura de selección y el contrato por componente mientras conserva íntegramente la
cobertura ya probada. La reducción futura de trabajo duplicado requiere evidencia y un
PR separado.

## QuPath Core queda fuera de la matriz

`qupath-core` no es una extensión y, por ADR-0002, no puede tener
`components/qupath-core/`.

Por tanto:

- la matriz sólo contiene entradas `QUPATH_EXTENSION` del registro;
- un cambio bajo `components/qupath-core/**` es un error de arquitectura y falla CI;
- los cambios propios de Core continúan protegidos por los jobs globales, fingerprints,
  tests de versión y release engineering.

La ausencia de Core en la matriz no significa menor cobertura; significa respetar la
frontera entre el eje de componentes de extensión y el sustrato versionado de QuPath.

## Detección de componentes afectados

`tools/ci_component_matrix.py` opera sólo con Git y biblioteca estándar.

### Cambios directos

Una ruta:

```text
components/<id>/**
```

selecciona `<id>` cuando el id existe en `components/registry.json` y su tipo es
`QUPATH_EXTENSION`.

Una ruta de componente desconocido falla cerrada. No se interpreta como «ningún
componente afectado».

### Registro

Cuando cambia:

```text
components/registry.json
```

el detector compara estructuralmente las entradas del registro en base y head, usando
`id` como identidad. Sólo las extensiones cuya entrada cambió entran en la matriz.

La eliminación de un id de extensión falla cerrada porque los ids son identidades
estables referenciadas por lockfiles, auditorías y rutas.

### Lock de componentes

Para:

```text
versions/<v>/components.lock.json
```

se comparan las entradas por `component_id`. Un cambio en la entrada de Cellpose sólo
selecciona Cellpose; un cambio en la entrada de Core no crea un falso componente de
matriz.

### Lock de localizaciones

Para:

```text
versions/<v>/localizations.lock.json
```

se compara por `(component_id, locale)`. Cambiar `instanseg/es` selecciona InstanSeg sin
necesidad de ejecutar una matriz de todas las extensiones.

### Contratos compartidos

Cambios en infraestructura que puede alterar la interpretación de **todos** los
componentes seleccionan las 12 extensiones. Entre ellos:

- schemas de registro/components lock/localizations lock;
- `tools/component_audit.py`;
- `tools/protected_identifiers.py`;
- el propio detector y el checker por componente;
- tests que definen esos contratos;
- `.github/workflows/ci.yml`.

Esto es deliberadamente conservador: una modificación en una regla compartida se prueba
contra todo el corpus.

### Rutas no relacionadas

Un cambio documental sin relación con componentes puede producir una matriz vacía.
Eso no omite los checks protegidos globales: continúan ejecutándose siempre.

## Semántica del diff

Los refs de entrada se resuelven primero a commits completos de 40 caracteres.

La lista de rutas se obtiene mediante Git con separación NUL:

```text
git diff --name-only -z --no-renames <base> <head>
```

`--no-renames` es intencional: una renombrada se trata como eliminación + adición y no
puede ocultar el componente de destino.

Cualquier ref no resoluble, JSON inválido, id desconocido o estado ambiguo provoca error.
**Error de detección ≠ matriz vacía.**

## Eventos de GitHub Actions

### Pull request

Se comparan los SHAs exactos:

```text
github.event.pull_request.base.sha
github.event.pull_request.head.sha
```

No se usa el commit sintético de merge como identidad del cambio.

### Push a `main`

Se compara `github.event.before` con `github.sha`. Si el evento no ofrece un `before`
utilizable, se seleccionan todas las extensiones en vez de adivinar.

### workflow_dispatch

Una ejecución manual selecciona todas las extensiones. Es una forma explícita de hacer
un barrido completo del eje de componentes.

## Checker por componente

`tools/component_ci.py` es el punto de entrada offline para una extensión. Verifica:

1. id válido y exactamente una entrada `QUPATH_EXTENSION` en el registro;
2. existencia de `components/<id>/`;
3. `tools/component_audit.py --check --component <id>`;
4. exactamente una entrada del componente en cada `versions/*/components.lock.json`;
5. proyecciones del componente en `localizations.lock.json`;
6. existencia de `source_of_truth` cuando está materializada;
7. existencia y SHA-256 exacto de cada `dist_bundle` materializado;
8. coherencia básica de inventarios de identificadores protegidos.

No descarga upstream, no compila extensiones, no modifica ficheros y no convierte
`NOT_VERIFIED` en `VALIDATED`.

## Seguridad de Actions

Los jobs nuevos mantienen `permissions: contents: read` heredado del workflow.

Los checkouts de los jobs nuevos usan:

```text
persist-credentials: false
```

Las acciones de checkout/setup-python siguen fijadas por SHA completo. Los ids de
componente llegan al shell mediante variables de entorno y además han sido validados
contra el registro y el patrón kebab-case.

No se incorpora ninguna action externa de path filtering.

## Consecuencias

### Positivas

- existe por primera vez una vista CI dirigida por componente;
- un cambio futuro de una única extensión puede aislar su trabajo específico;
- los lockfiles se comparan semánticamente y no por «cualquier cambio en el fichero»;
- el mecanismo escala con el número de componentes afectados, no necesariamente con el
  tamaño total del corpus;
- los checks protegidos ya existentes no cambian de identidad;
- una ejecución manual puede forzar una matriz completa;
- Core conserva su modelo separado;
- cero dependencias Python de terceros.

### Coste inmediato

Este PR **añade** trabajo a CI. Cuando un contrato compartido cambia, ejecuta además una
matriz de las 12 extensiones. Es intencional durante la fase de adopción: primero se
prueba que la selección y los checks dirigidos son correctos; sólo después puede
eliminarse duplicación con evidencia.

## Invariantes

1. `tests`, `tests (Windows)` y `canonical bundle integrity` mantienen sus nombres.
2. Los tres jobs globales siguen ejecutándose en todo PR/push.
3. La matriz sólo contiene extensiones registradas.
4. `qupath-core` nunca es un objetivo de la matriz.
5. `components/qupath-core/` sigue prohibido.
6. Un componente desconocido falla CI.
7. Un fallo de Git/JSON/detección nunca se transforma en matriz vacía.
8. Los lockfiles se comparan por identidad estructural, no sólo por nombre de fichero.
9. Los contratos compartidos seleccionan todas las extensiones.
10. El checker por componente es offline y de solo lectura.
11. Este PR no modifica bundles, TSV, traducciones, pins, estados ni fingerprints.

## Trabajo posterior

Una vez acumulada evidencia de CI puede proponerse un PR independiente para trasladar
checks costosos desde la suite global al checker por componente, sin cambiar la semántica
de protección.

El siguiente bloque de la auditoría histórica es la proyección al catálogo del Extension
Manager. Sigue separado: detectar qué componente cambió y decidir qué artefacto es
publicable son responsabilidades distintas.

## Referencias

- [`0001-two-axis-component-architecture.md`](0001-two-axis-component-architecture.md)
- [`0002-core-outside-components.md`](0002-core-outside-components.md)
- [`0004-language-axis.md`](0004-language-axis.md)
- [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
- [`../../versions/0.7.0/reports/ecosystem-repository-architecture-audit.md`](../../versions/0.7.0/reports/ecosystem-repository-architecture-audit.md)
