# Estado PR6 — API upstream para ResourceBundles de extensiones

Este informe registra el estado del **PR6 de la hoja de ruta** definida en `ecosystem-repository-architecture-audit.md`.

PR6 no implementa Java dentro de `qupath-es`. Su destino es **`qupath/qupath`**. Este repositorio sólo conserva el estado, la evidencia y los criterios que deben cumplirse antes de escribir el PR upstream.

## Estado

- Estado: **`UPSTREAM_ISSUE_OPEN`**.
- Implementación upstream: **no iniciada**.
- Repositorio upstream: `qupath/qupath`.
- `main` observado: `67cbf619996582f8737550080cd05c6e52b37b13`.
- `QuPathResources.java` observado: blob `6143911c4eff5eccf72567d1d34858a461644738`.
- Issue upstream: <https://github.com/qupath/qupath/issues/2190>.
- Estado del issue upstream: **OPEN**.
- PR upstream: ninguno todavía.
- Fork de QuPath: ninguno.
- Patch de QuPath: ninguno.

## Por qué todavía no se escribe el PR

`qupath/qupath/CONTRIBUTING.md` pide discutir cambios de API antes de enviar código. La plantilla de feature request recomienda hacerlo en image.sc.

Además, el propio mantenedor Pete Bankhead remitió una consulta de traducción a una discusión ya existente:

- <https://forum.image.sc/t/qupath-internationalize-multi-language-support/77468>
- referencia GitHub: <https://github.com/qupath/qupath/issues/1609#issuecomment-2316693891>

Después de verificar que no existía un issue o PR técnico equivalente, LABVETNEB publicó la propuesta técnica upstream como **qupath/qupath#2190**: <https://github.com/qupath/qupath/issues/2190>. El issue enlaza la discusión internacional previa y solicita dirección del equipo Core antes de preparar el cambio Java.

## Problema reproducido sobre `main`

`QuPathResources` ya hace correctamente una parte crítica: resuelve usando `Locale.getDefault(Locale.Category.DISPLAY)`.

Sin embargo, para bundles de extensiones quedan dos bloqueos independientes:

1. **ClassLoader.** `getBundleOrNull(...)` carga usando `QuPathResources.class.getClassLoader()`. No existe una entrada pública que permita a una extensión proporcionar su propio `ClassLoader` o una clase ancla para resolver recursos empaquetados en su JAR.
2. **Espacio de nombres externo plano.** `getShortPropertyFileName(...)` elimina el paquete del bundle y busca sólo el basename, por ejemplo `strings_es.properties`. Once bundles auditados usan precisamente `strings`, de modo que no pueden coexistir como overrides externos independientes.

A esto se suma que las extensiones auditadas usan `ResourceBundle.getBundle(String)` directamente. Por tanto, no alcanzan el `ResourceBundle.Control` de QuPath ni su directorio externo de localización.

## Contrato que debe discutirse upstream

La propuesta no fija todavía nombres de métodos; fija comportamiento observable:

1. QuPath ofrece una API soportada para resolver un bundle arbitrario proporcionando el `ClassLoader` de la extensión o una clase ancla.
2. La selección de idioma usa exclusivamente `Locale.Category.DISPLAY`.
3. El `ClassLoader` de la extensión puede resolver primero sus recursos; el classloader de la aplicación sólo actúa como fallback controlado cuando corresponda.
4. Los overrides externos preservan el namespace completo del bundle. Ejemplo:
   `qupath/ext/instanseg/ui/strings_es.properties`.
5. El bundle principal de QuPath mantiene compatibilidad con la ruta externa actual para no romper instalaciones existentes.
6. La API no modifica `FORMAT`, `Locale.setDefault(...)`, preferencias globales ni archivos externos.

## Tests mínimos del futuro PR upstream

- selección de `_es` mediante `Locale.Category.DISPLAY`;
- visibilidad de un bundle disponible sólo en un classloader de extensión;
- override externo namespaced;
- dos extensiones con `strings_es.properties` sin colisión entre sí;
- fallback ante recursos ausentes;
- compatibilidad del bundle principal con el esquema externo existente;
- ninguna modificación de la locale `FORMAT` ni de la locale global.

## Fuera de alcance

PR6 no debe:

- vendorizar código upstream en `qupath-es`;
- modificar JAR instalados;
- crear un fork permanente antes de conocer la posición upstream;
- traducir nombres de mediciones, `PathClass`, IDs de modelos, claves de parámetros o identificadores funcionales;
- mezclar la API de localización con el catálogo de extensiones o con PR8/PR9 del roadmap.

## Gate siguiente

**`AWAIT_MAINTAINER_DIRECTION_ON_ISSUE_2190`**.

Sólo después de una respuesta del equipo Core que acepte la dirección general —o indique una API alternativa equivalente— debe empezar el código de `qupath/qupath`.

El dato estructurado de este informe vive en `upstream-extension-bundle-api-status.json`.
