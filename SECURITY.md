# Política de seguridad

## Alcance

Este repositorio distribuye un **fichero de traducción** y las herramientas para
instalarlo. No distribuye QuPath, no lo modifica y no ejecuta código
descargado de Internet.

Aun así, contiene scripts que escriben en el perfil del usuario, así que las
vulnerabilidades son posibles y se toman en serio.

### Dentro del alcance

- Ejecución de código no intencionada a través de los scripts de `runtime/`.
- Escritura fuera de las rutas previstas (directorio de usuario de QuPath,
  `backups/`, `logs/`).
- Modificación de la instalación de QuPath, que nunca debe ocurrir.
- Un fichero de traducción manipulado que provoque un fallo en QuPath.
- Elevación de privilegios o cambios en configuración global de la máquina.
- Fugas de datos en los registros de `logs/`.

### Fuera del alcance

- Vulnerabilidades de QuPath. Repórtalas a
  [qupath/qupath](https://github.com/qupath/qupath).
- Vulnerabilidades de Java, PowerShell o Windows.
- Que la interfaz no esté traducida al 100 %: es una limitación conocida y
  documentada, no un fallo de seguridad.

## Cómo informar

**No abras una incidencia pública para una vulnerabilidad.**

Usa el aviso privado de GitHub:

*Security → Report a vulnerability* en
<https://github.com/LABVETNEB/qupath-es/security/advisories>

Incluye:

- una descripción del problema y su impacto;
- pasos para reproducirlo;
- versión de QuPath, de Windows y de PowerShell;
- el commit del repositorio.

Este es un proyecto pequeño mantenido por una persona. No hay compromiso de
plazo de respuesta, pero los avisos se leen.

## Cómo verificar lo que instalas

El proyecto está diseñado para que puedas comprobarlo tú mismo.

**Verifica el bundle instalado:**

```powershell
Get-FileHash "$env:USERPROFILE\QuPath\localization\qupath-gui-strings_es.properties" -Algorithm SHA256
```

Para QuPath 0.7.0 debe dar:

```
E4A966C90D1CE1368DE9EA21DECC7D9DBB0180087B60D3724690AAD4C128FC19
```

**Verifica que QuPath no ha sido modificado:**

```powershell
Get-FileHash "$env:LOCALAPPDATA\QuPath-0.7.0\app\qupath-gui-fx-0.7.0.jar" -Algorithm SHA256
```

Debe coincidir con el valor registrado en
`versions/0.7.0/fingerprint.json`.

**Ejecuta un diagnóstico sin escribir nada:**

```powershell
.\runtime\update-qupath-es.ps1
```

El modo por defecto no modifica nada.

## Garantías de diseño

Comprobadas por pruebas automáticas que fallan si se rompen:

| Garantía | Prueba |
| --- | --- |
| Nunca se modifica el JAR de QuPath | `test_runtime_locale.py` |
| No hay órdenes que cierren procesos, reinicien o apaguen | `test_runtime_locale.py`, `test_version_migrator.py` |
| No se escribe configuración global de Windows ni variables de entorno persistentes | `test_runtime_locale.py` |
| No hay rutas absolutas de usuario en los scripts | `test_runtime_locale.py` |
| El bundle canónico inglés es inmutable | `test_repository_integrity.py` |
| Nada se instala sin pasar el validador | `test_version_migrator.py` |

## Integridad del repositorio

La rama `main` está protegida: no admite `force-push` ni borrado, y los cambios
de terceros solo entran por pull request aprobado por el mantenedor. Los tags de
versión están protegidos contra sobrescritura. Ver
[`docs/GOVERNANCE.md`](docs/GOVERNANCE.md).

Si encuentras una release cuyo contenido no coincide con su hash publicado,
trátalo como un incidente de seguridad e infórmalo por el canal privado.

## Qué se registra

Los ficheros de `logs/` guardan fecha, versión de QuPath, rutas, hashes,
acciones y resultado. No contienen credenciales ni datos personales más allá de
las rutas del perfil del usuario. No se suben al repositorio.
