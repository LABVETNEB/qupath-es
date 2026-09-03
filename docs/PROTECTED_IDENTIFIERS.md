# Protected Identifier Controls

Este documento define el contrato ejecutable para impedir que la localización altere
identificadores técnicos con semántica de runtime.

## Fuente de política

`components/<id>/component.json` declara las categorías de identificadores protegidos
que pertenecen a la política del componente. Esa declaración no basta por sí sola para
identificar literales concretos.

Cuando existe una revisión de localización materializada, debe existir exactamente un
inventario en:

```text
components/<id>/protected-identifiers/<revision>.json
```

El inventario es posterior a la auditoría inicial y no reescribe retroactivamente
`explicit_protected_identifiers` ni
`explicit_identifier_inventory_status = NOT_ENUMERATED_IN_INITIAL_AUDIT` del manifest.
Esos campos conservan la afirmación histórica de la auditoría inicial. El inventario
nuevo es una capa de enforcement independiente y versionada.

## Contrato del inventario

Cada inventario fija:

- `component_id` y `localization_revision`;
- uno o más commits de evidencia con los blob SHA-1 exactos de los archivos usados;
- `inventory_status`, que sólo puede ser `PARTIAL` o `COMPLETE`;
- reglas con `category`, `value`, `match` y `evidence_paths`.

`PARTIAL` significa que el archivo contiene identificadores confirmados por evidencia,
pero no afirma que el upstream completo haya sido enumerado. La ausencia de una regla
no constituye permiso para traducir un identificador no auditado.

Las categorías de cada regla deben estar declaradas en
`audit_policy.protected_identifier_categories` del componente. Las rutas de evidencia
deben caer dentro de `audit_policy.relevant_paths` y estar respaldadas por un blob
SHA-1 fijado en el propio inventario.

## Modos de coincidencia

- `EXACT`: el valor fuente completo es el identificador y debe permanecer idéntico.
- `PREFIX`: el identificador es un prefijo semántico y debe conservarse al inicio.
- `CONTAINS`: cada aparición literal y sensible a mayúsculas/minúsculas debe conservar
  exactamente el mismo número de ocurrencias.

Una regla sólo se aplica a una cadena cuando el identificador está presente en el valor
fuente. Esto permite registrar identificadores de runtime que todavía no forman parte
de un bundle traducible sin inventar que ya fueron externalizados.

## Fail closed

`tests/test_protected_identifiers.py` exige que:

1. toda revisión `components/<id>/l10n/<revision>/` tenga exactamente un inventario;
2. no existan inventarios huérfanos;
3. los commits de evidencia coincidan con los `evidence_commit` del lockfile;
4. las categorías y rutas de evidencia estén autorizadas por `component.json`;
5. el JSON sea UTF-8 sin BOM, LF y con contrato de campos cerrado;
6. los modos desconocidos, commits inválidos, rutas inseguras, blobs inválidos y reglas
   duplicadas fallen;
7. cualquier identificador protegido presente en `en` se conserve en `es`.

El control es genérico: no contiene bifurcaciones por `component_id`. InstanSeg
`v0.1.7` es la primera instancia real.

## Alcance

Este control no modifica traducciones, no certifica que el inventario `PARTIAL` sea
exhaustivo, no cambia compatibilidad runtime y no convierte una localización en
distribuible. Es una barrera de integridad para impedir que una traducción válida desde
el punto de vista lingüístico rompa nombres de modelos, motores, nodos de I/O, nombres
de medición, archivos u otros identificadores técnicos declarados.
