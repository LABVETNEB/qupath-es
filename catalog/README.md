# Catálogo del Extension Manager

`catalog.json` es una **proyección generada** del estado soportado de las extensiones para QuPath 0.7.0 / locale `es`. No es una fuente de verdad y no debe editarse manualmente.

Verificación:

```bash
python tools/catalog_projection.py --check
```

Regeneración deliberada:

```bash
python tools/catalog_projection.py --write
```

Una extensión sólo aparece cuando su localización está `TRANSLATED`, `VALIDATED` y `DISTRIBUTED`, su compatibilidad runtime ya no es `NOT_VERIFIED` y existe un release asset de GitHub con provenance fijada.

El catálogo está vacío actualmente porque ninguna de las 12 extensiones cumple simultáneamente esos requisitos. QuPath Core no pertenece al catálogo de extensiones.

**Este directorio no establece todavía una URL pública de catálogo.** Registrar o anunciar una URL estable es una decisión posterior y explícita.
