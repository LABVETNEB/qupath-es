# ADR-0003 — No vendoring y forks satélite sólo cuando sean necesarios

- Estado: Aceptado
- Fecha: 2026-09-03

## Contexto

`qupath-es` necesita auditar y eventualmente localizar extensiones de terceros. Copiar sus árboles de código fuente dentro de este repositorio facilitaría aplicar cambios locales, pero convertiría `qupath-es` en un mirror parcial difícil de mantener, con riesgo de divergencia, licencias mezcladas y actualizaciones opacas.

Algunas extensiones, además, pueden requerir cambios upstream para que sus bundles sean localizables desde fuera del JAR.

## Decisión

No vendorizar código fuente upstream dentro de `qupath-es`.

El repositorio puede conservar:

- identidad y pins;
- snapshots de auditoría;
- traducciones;
- hashes y URLs de artefactos;
- parches reproducibles;
- referencia a un fork satélite cuando sea estrictamente necesario.

Cuando una localización requiera modificar código upstream, el orden de preferencia es:

1. solución aceptada upstream;
2. parche propuesto upstream;
3. fork satélite separado, sólo si la necesidad persiste y está justificada.

El fork no convierte a `qupath-es` en propietario del código upstream: la relación debe quedar registrada mediante `satellite_fork`, `fork_repo`, `fork_tag` y/o `patches` según corresponda.

## Consecuencias

### Positivas

- el repositorio permanece pequeño y auditable;
- la provenance del código sigue siendo inequívoca;
- actualizar upstream no exige reconciliar una copia vendorizada completa;
- las obligaciones de licencia y autoría permanecen separadas con mayor claridad.

### Costes

- probar un parche puede requerir clonar o construir el repositorio upstream/fork;
- una localización que dependa de cambios de código puede quedar temporalmente en `UNSUPPORTED`;
- el pipeline debe distinguir traducción lista de mecanismo de distribución listo.

## Invariantes derivadas

- `components/<id>/` no contiene una copia completa del repositorio upstream;
- `source_code_vendored_here` permanece falso salvo que un ADR posterior sustituya esta decisión;
- no se declara `DISTRIBUTED` sólo porque exista una traducción;
- un fork satélite debe estar trazado explícitamente y no aparecer de forma implícita en scripts o URLs.

## Alternativas descartadas

### Submodules para todas las extensiones

Descartado porque introduce acoplamiento operativo y no aporta valor al objetivo principal de localización/auditoría.

### Copias parciales de archivos Java modificados

Descartado como mecanismo principal porque pierde contexto de build y hace más difícil demostrar contra qué revisión upstream se generó el cambio. Los parches reproducibles son preferibles.

## Referencias

- [`../COMPONENTS.md`](../COMPONENTS.md)
- [`../../components/README.md`](../../components/README.md)