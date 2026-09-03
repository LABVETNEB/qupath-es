# Cómo contribuir

Gracias por el interés. Este documento explica cómo proponer cambios y qué se
rechaza automáticamente.

Antes de nada, lee:

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) para el bundle principal,
  runtime e invariantes de instalación;
- [`docs/COMPONENTS.md`](docs/COMPONENTS.md) para registry, lockfiles,
  provenance y extensiones;
- [`docs/adr/`](docs/adr/) para decisiones arquitectónicas aceptadas.

---

## Modelo de colaboración

Este repositorio sigue un modelo **leer / bifurcar / proponer**:

```text
Lees o clonas el repositorio          →  libre, es público
Haces un fork y lo modificas          →  libre, es tu copia
Abres un pull request                 →  bienvenido
Se fusiona en LABVETNEB/qupath-es     →  solo con aprobación del mantenedor
```

Nadie salvo el mantenedor puede escribir en el repositorio oficial. Los cambios
entran únicamente por pull request revisado. Ver
[`docs/GOVERNANCE.md`](docs/GOVERNANCE.md).

---

## Antes de abrir un pull request

Ejecuta la suite completa:

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

Si modificaste registry o lockfile, ejecuta además los contratos directamente:

```powershell
python tools/schema_validate.py schemas/component-registry.schema.json components/registry.json
python tools/schema_validate.py schemas/components-lock.schema.json versions/0.7.0/components.lock.json
```

Debe pasar todo. CI repite la suite en Ubuntu y Windows y mantiene un check
separado de integridad del bundle canónico.

---

## Reglas que no se negocian

Estas condiciones se comprueban automáticamente o forman parte de decisiones
arquitectónicas aceptadas:

| Regla | Por qué |
| --- | --- |
| No modificar `versions/*/base/*` | Es el bundle inglés capturado de una release oficial de QuPath. Es inmutable y su hash está registrado |
| No editar a mano `versions/*/dist/*.properties` | Es un artefacto generado |
| No cambiar claves ni su orden | Solo se traducen los valores |
| No alterar marcadores (`{0}`, `%s`, `%n`…) | Un marcador roto puede provocar una excepción en ejecución |
| No poner el locale de formato en español | Cambiaría el separador decimal y afectaría a las mediciones |
| No añadir rutas absolutas de usuario | Rompería la instalación en otros equipos |
| No añadir órdenes que cierren procesos, reinicien o apaguen | Hay pruebas que lo impiden |
| No relajar el validador o tests para hacer pasar un estado | La implementación debe ajustarse al contrato, no al revés |
| No crear `components/qupath-core/` | El Core ya tiene su autoridad bajo `versions/<v>/`; ver ADR-0002 |
| No vendorizar árboles upstream bajo `components/` | La provenance debe permanecer separada; ver ADR-0003 |
| No confundir traducción con compatibilidad o distribución | Son estados independientes y requieren evidencia independiente |

---

## Tipos de contribución

### Corregir una traducción del Core

Sigue
[`docs/MAINTAINER_GUIDE.md`](docs/MAINTAINER_GUIDE.md#corregir-una-traducción-existente).

Edita la fuente canónica de trabajo, regenera el bundle, valida, audita, ejecuta
las pruebas y actualiza los hashes publicados si el artefacto cambió.

Incluye en el pull request la salida del validador y el nuevo SHA-256 cuando
corresponda.

### Cambiar el corpus de componentes

Antes de editar, decide en qué capa vive el dato:

- identidad estable → `components/registry.json`;
- pin/provenance/estado por objetivo QuPath → `versions/<v>/components.lock.json`;
- política de auditoría → `components/<id>/component.json`;
- evidencia observada → `components/<id>/audits/<evidence_commit>.json`;
- material lingüístico → `components/<id>/l10n/<revision>/`.

No dupliques el mismo hecho en varias capas sin una razón explícita.

#### Añadir un componente

- añade un ID estable al registry;
- añade su pin al lockfile del objetivo QuPath;
- crea `component.json` y snapshot sólo si existe auditoría real;
- no crees carpetas `l10n/`, `patches/` o forks vacíos por anticipado;
- valida ambos schemas y ejecuta toda la suite.

#### Cambiar una release fijada

- conserva el commit exacto de pin;
- para `UPSTREAM_RELEASE`, registra `artifact_name`, URL de release y SHA-256;
- distingue `upstream_commit` de `evidence_commit`;
- reaudita si cambian bundles, classloaders, API o mecanismo de distribución;
- no promociones `runtime_compatibility` sin prueba runtime.

`tools/verify_artifacts.py` permite comprobar manualmente los bytes de los assets
registrados sin convertir la red upstream en una dependencia de CI.

### Añadir localización de una extensión

Una traducción de extensión debe vivir bajo una revisión explícita en
`components/<id>/l10n/<revision>/` y tener pruebas que preserven claves,
estructura, placeholders y bytes.

La presencia de traducción no autoriza por sí sola a declarar:

- `VALIDATED`;
- compatibilidad runtime;
- instalabilidad;
- `DISTRIBUTED`.

Los estados deben promoverse sólo cuando la evidencia correspondiente exista.

### Añadir soporte para una versión nueva de QuPath

Es un trabajo grande. Lee
[`docs/MAINTAINER_GUIDE.md`](docs/MAINTAINER_GUIDE.md#preparar-una-versión-nueva-de-qupath)
y coméntalo primero en una incidencia: conviene acordar el enfoque antes de
traducir cientos de claves.

Una versión nueva **no se fusiona** hasta cumplir el *release gate*: cero
entradas `PENDING`, `DRAFT` o `BLOCKED` del bundle que se pretende publicar,
validador en `PASS` y auditoría lingüística en `SAFE TO INSTALL`.

### Herramientas y pruebas

Bienvenidas, sobre todo si añaden cobertura. Si corriges un fallo, **añade una
prueba de regresión**.

Si amplías el subconjunto de JSON Schema utilizado por el repositorio, amplía
también `tools/schema_validate.py` y añade pruebas negativas. Las keywords
semánticas no deben ignorarse silenciosamente.

### Documentación y ADRs

La documentación es parte del contrato. Verifica que los enlaces internos
resuelven antes de enviarla.

Si un cambio contradice un ADR aceptado, añade un nuevo ADR que lo sustituya o
lo modifique. No reescribas silenciosamente una decisión arquitectónica previa.

---

## Criterios de traducción

- Castellano técnico neutro, comprensible en España y Latinoamérica.
- Tratamiento impersonal o de usted; nunca tuteo.
- Infinitivo en órdenes de menú: «Abrir imagen», no «Abre imagen».
- Mayúscula solo en la inicial.
- Terminología coherente con el resto del bundle.
- Acrónimos y marcas se conservan: TMA, ROI, DAB, GeoJSON, ImageJ,
  Bio-Formats, QuPath.
- Identificadores funcionales, claves serializadas, nombres de modelo, rutas,
  argumentos CLI y equivalentes no deben traducirse como si fueran texto de
  presentación.

---

## Qué NO acepta este proyecto

- Traducciones automáticas sin revisión humana.
- Cambios que modifiquen la instalación de QuPath (JAR, código, ejecutable,
  runtime) dentro de este repositorio.
- Funciones que descarguen o instalen QuPath.
- Instaladores desatendidos que escriban sin comprobar que QuPath está cerrado.
- Dependencias de terceros en las herramientas Python sin justificación sólida.
- Copias completas de repositorios upstream bajo `components/`.
- Cambios de metadatos que hagan afirmaciones de compatibilidad o distribución
  no respaldadas por evidencia.

---

## Informar de un problema

Abre una incidencia con:

- la salida completa de `.\runtime\update-qupath-es.ps1`;
- la versión de QuPath y de PowerShell;
- qué esperabas y qué ocurrió.

Antes de abrirla, comprueba
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

Para vulnerabilidades, no abras una incidencia pública: ver
[`SECURITY.md`](SECURITY.md).

---

## Licencia

Al contribuir aceptas que tu aportación se distribuya bajo
[GPL-3.0](LICENSE), la misma licencia del proyecto.