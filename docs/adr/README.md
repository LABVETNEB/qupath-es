# Architecture Decision Records

Los ADRs registran decisiones estructurales que no deben cambiar de forma implícita.

| ADR | Estado | Decisión |
| --- | --- | --- |
| [ADR-0001](0001-two-axis-component-architecture.md) | Aceptado | Separar identidad estable y pins por versión de QuPath |
| [ADR-0002](0002-core-outside-components.md) | Aceptado | Mantener QuPath Core fuera de `components/` |
| [ADR-0003](0003-no-vendoring-satellite-forks.md) | Aceptado | No vendorizar código upstream; forks satélite sólo si son necesarios |

## Regla de mantenimiento

Si un cambio contradice un ADR aceptado, debe añadirse un nuevo ADR que lo sustituya o lo modifique explícitamente. No se reescribe el historial para hacer parecer que la decisión anterior nunca existió.

Los ADRs describen decisiones, no resultados de pruebas ni estados temporales. La evidencia mutable pertenece a auditorías, lockfiles e informes versionados.