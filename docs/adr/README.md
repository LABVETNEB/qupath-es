# Architecture Decision Records

Los ADRs registran decisiones estructurales que no deben cambiar de forma implícita.

| ADR | Estado | Decisión |
| --- | --- | --- |
| [ADR-0001](0001-two-axis-component-architecture.md) | Aceptado | Separar identidad estable y pins por versión de QuPath |
| [ADR-0002](0002-core-outside-components.md) | Aceptado | Mantener QuPath Core fuera de `components/` |
| [ADR-0003](0003-no-vendoring-satellite-forks.md) | Aceptado | No vendorizar código upstream; forks satélite sólo si son necesarios |
| [ADR-0004](0004-language-axis.md) | Aceptado | Separar el estado lingüístico por `(component_id, locale)` |
| [ADR-0005](0005-reproducible-release-artifacts.md) | Aceptado | Construir paquetes de release reproducibles y verificables desde blobs Git |
| [ADR-0006](0006-tag-gated-release-publication.md) | Aceptado | Publicar sólo desde tags contenidos en `main`, con provenance attestation verificable |
| [ADR-0007](0007-path-scoped-component-ci.md) | Aceptado | Detectar extensiones afectadas por diff y validarlas mediante matriz dinámica |

## Regla de mantenimiento

Si un cambio contradice un ADR aceptado, debe añadirse un nuevo ADR que lo sustituya o lo modifique explícitamente. No se reescribe el historial para hacer parecer que la decisión anterior nunca existió.

Los ADRs describen decisiones, no resultados de pruebas ni estados temporales. La evidencia mutable pertenece a auditorías, lockfiles e informes versionados.
