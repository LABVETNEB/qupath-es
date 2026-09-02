# Cómo contribuir

Gracias por el interés. Este documento explica cómo proponer cambios y qué se
rechaza automáticamente.

Antes de nada, lee [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): describe los
invariantes del proyecto, y casi todo lo que se rechaza es por romper uno.

---

## Modelo de colaboración

Este repositorio sigue un modelo **leer / bifurcar / proponer**:

```
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

Debe pasar entera. La integración continua la ejecutará igualmente en tu pull
request, incluso si viene de un fork.

---

## Reglas que no se negocian

Estas condiciones se comprueban automáticamente y un pull request que las
incumpla se cierra:

| Regla | Por qué |
| --- | --- |
| No modificar `versions/*/base/*` | Es el bundle inglés capturado de una release oficial de QuPath. Es inmutable y su hash está registrado |
| No editar a mano `versions/*/dist/*.properties` | Se genera. Edita `tools/es_translations.py` y regenera |
| No cambiar claves ni su orden | Solo se traducen los valores |
| No alterar marcadores (`{0}`, `%s`, `%n`…) | Un marcador roto puede provocar una excepción en ejecución |
| No poner el locale de formato en español | Cambiaría el separador decimal y afectaría a las mediciones |
| No añadir rutas absolutas de usuario | Rompería la instalación en otros equipos |
| No añadir órdenes que cierren procesos, reinicien o apaguen | Hay pruebas que lo impiden |
| No relajar el validador para que pase algo | Si aparece un formato nuevo, amplía el validador **y añade pruebas** |

---

## Tipos de contribución

### Corregir una traducción

El caso más común. Sigue
[`docs/MAINTAINER_GUIDE.md`](docs/MAINTAINER_GUIDE.md#corregir-una-traducción-existente).

En resumen: edita `tools/es_translations.py`, regenera, valida, audita, ejecuta
las pruebas y actualiza los hashes publicados si el bundle cambió.

Incluye en el pull request la salida del validador y el nuevo SHA-256.

### Añadir soporte para una versión nueva de QuPath

Es un trabajo grande. Lee
[`docs/MAINTAINER_GUIDE.md`](docs/MAINTAINER_GUIDE.md#preparar-una-versión-nueva-de-qupath)
y coméntalo primero en una incidencia: conviene acordar el enfoque antes de
traducir cientos de claves.

Una versión nueva **no se fusiona** hasta cumplir el *release gate*: cero
entradas `PENDING`, `DRAFT` o `BLOCKED`, validador en `PASS` y auditoría
lingüística en `SAFE TO INSTALL`.

### Herramientas y pruebas

Bienvenidas, sobre todo si añaden cobertura. Si corriges un fallo, **añade una
prueba de regresión**: varias de las que hay existen precisamente por eso.

### Documentación

Bienvenida. Verifica que los enlaces internos resuelven antes de enviarla.

---

## Criterios de traducción

- Castellano técnico neutro, comprensible en España y Latinoamérica.
- Tratamiento impersonal o de usted; nunca tuteo.
- Infinitivo en órdenes de menú: «Abrir imagen», no «Abre imagen».
- Mayúscula solo en la inicial.
- Terminología coherente con el resto del bundle; consulta las entradas
  existentes antes de introducir un término nuevo.
- Acrónimos y marcas se conservan: TMA, ROI, DAB, GeoJSON, ImageJ,
  Bio-Formats, QuPath.

---

## Qué NO acepta este proyecto

- Traducciones automáticas sin revisión humana.
- Cambios que modifiquen la instalación de QuPath (JAR, código, ejecutable,
  runtime).
- Funciones que descarguen o instalen QuPath.
- Instaladores desatendidos que escriban sin comprobar que QuPath está cerrado.
- Dependencias de terceros en las herramientas Python, salvo justificación
  sólida: hoy usan solo la biblioteca estándar.

---

## Informar de un problema

Abre una incidencia con:

- la salida completa de `.\runtime\update-qupath-es.ps1` (no contiene datos
  personales: rutas, versiones y hashes);
- la versión de QuPath y de PowerShell;
- qué esperabas y qué ocurrió.

Antes de abrirla, comprueba
[`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md): varios comportamientos que
parecen fallos son limitaciones conocidas de QuPath 0.7.0.

Para vulnerabilidades, no abras una incidencia pública: ver
[`SECURITY.md`](SECURITY.md).

---

## Licencia

Al contribuir aceptas que tu aportación se distribuya bajo
[GPL-3.0](LICENSE), la misma licencia del proyecto.
