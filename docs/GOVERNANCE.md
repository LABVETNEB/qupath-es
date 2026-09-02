# Gobernanza y protección del repositorio

Cómo se protege el repositorio canónico, qué está aplicado en el servidor de
GitHub, y qué puede y no puede hacer un tercero.

---

## Qué significa realmente «proteger el repositorio»

Conviene ser preciso, porque hay una expectativa habitual que no se puede
cumplir y no hace falta cumplir.

En un repositorio **público** es imposible —y no es deseable— impedir que
alguien:

- lo lea;
- lo clone;
- haga un *fork*;
- modifique **su propia copia** como quiera.

Eso es lo que hace que el proyecto sea auditable y reutilizable, y la licencia
GPL-3.0 lo garantiza expresamente.

Lo que sí se protege es que esas modificaciones **entren en el repositorio
canónico** `LABVETNEB/qupath-es`. El modelo es:

```
LEER / BIFURCAR / PROPONER
        ↓
NO SE MODIFICA EL REPOSITORIO OFICIAL
        ↓
SOLO EL MANTENEDOR AUTORIZADO PUEDE ACEPTAR
```

---

## Punto de partida: quién podía escribir

Antes de aplicar nada, la situación real era:

| Hecho | Valor |
| --- | --- |
| Visibilidad | Pública |
| Propietario | Cuenta de usuario `LABVETNEB` (no una organización) |
| Colaboradores con permiso de escritura | **Solo `LABVETNEB`** |
| Protección de rama | Ninguna |
| Rulesets | Ninguno |

Es decir: **ningún tercero podía hacer push, force-push, fusionar ni sobrescribir
releases**, porque GitHub deniega la escritura a quien no es colaborador. Esa
puerta nunca estuvo abierta.

Los riesgos reales eran otros:

1. un `force-push` o un borrado accidental de `main` por el propio propietario;
2. un token comprometido con permiso `repo`;
3. añadir un colaborador en el futuro sin protecciones ya puestas;
4. fusionar un pull request sin que pasen las pruebas;
5. mover o reescribir un tag de versión ya publicado.

Las protecciones aplicadas atacan esos cinco puntos.

---

## Qué está aplicado en GitHub

### Protección de la rama `main`

| Ajuste | Valor | Qué impide |
| --- | --- | --- |
| Pull request obligatorio | Sí, 1 aprobación | Que un colaborador fusione sin revisión |
| Revisión de *code owners* | Sí | Que se toque un área crítica sin que la vea el mantenedor |
| Descartar aprobaciones al llegar commits nuevos | Sí | Aprobar una versión y colar otra después |
| Pruebas obligatorias (`tests`, `canonical bundle integrity`) | Sí | Fusionar código que rompe la suite o el bundle canónico |
| Ramas actualizadas antes de fusionar | Sí | Fusionar contra una base obsoleta |
| Resolución de conversaciones | Obligatoria | Cerrar un PR con objeciones abiertas |
| `force-push` | **Bloqueado** | Reescribir la historia publicada |
| Borrado de la rama | **Bloqueado** | Eliminar `main` |
| Aplicar también a administradores | **No** | *(ver más abajo)* |

### Protección de tags

Un *ruleset* sobre los patrones `es-*` y `v*` bloquea:

- el **borrado** de un tag publicado;
- la **actualización no lineal** (mover un tag a otro commit).

Esto es lo que evita que una release publicada cambie de contenido después de
anunciarse. El hash que aparece en la documentación sigue describiendo lo que
alguien descarga meses después.

### Por qué los administradores no están incluidos

`enforce_admins` está en **false** deliberadamente. Consecuencia:

- **cualquier colaborador** que se añada en el futuro queda sujeto a pull
  request, revisión y pruebas en verde;
- **el mantenedor** conserva el push directo a `main` para el mantenimiento
  diario.

Es una decisión consciente de compromiso: protege contra terceros y contra
colaboradores futuros sin convertir cada corrección de una cadena en un pull
request. El `force-push` y el borrado siguen bloqueados para todos, que es la
parte irreversible.

Si en algún momento se quiere máxima integridad —ni siquiera el mantenedor
puede saltarse el proceso—, basta con poner `enforce_admins` en `true`; el
comando está más abajo.

---

## Qué puede hacer un tercero

| Acción | ¿Permitida? |
| --- | --- |
| Leer y clonar | Sí |
| Hacer *fork* y modificarlo | Sí |
| Redistribuir bajo GPL-3.0 | Sí |
| Abrir una incidencia | Sí |
| Abrir un pull request | Sí |
| Ver ejecutarse la CI sobre su pull request | Sí, con token de solo lectura y sin acceso a *secrets* |
| **Hacer push a `main`** | **No** |
| **Fusionar su propio pull request** | **No** |
| **Reescribir la historia** | **No** |
| **Borrar o mover un tag publicado** | **No** |
| **Publicar o alterar una release** | **No** |

---

## Ficheros de gobernanza en el repositorio

| Fichero | Función |
| --- | --- |
| `.github/CODEOWNERS` | Toda ruta requiere revisión del mantenedor |
| `CONTRIBUTING.md` | Modelo de colaboración y reglas que no se negocian |
| `SECURITY.md` | Canal privado para vulnerabilidades y cómo verificar lo que instalas |
| `.github/PULL_REQUEST_TEMPLATE.md` | Lista de comprobación obligatoria |
| `.github/workflows/ci.yml` | Pruebas e integridad del bundle canónico en cada PR |

La CI hace dos cosas que importan para la integridad:

1. ejecuta las 147 pruebas;
2. comprueba que **cada artefacto canónico coincide con su fingerprint** y que
   los bundles publicados validan contra su base. Un pull request que altere el
   bundle inglés capturado falla aquí, aunque el revisor no se dé cuenta.

---

## Reproducir o revisar la configuración

Requiere `gh` autenticado con permiso de administración sobre el repositorio.

**Ver el estado actual:**

```bash
gh api repos/LABVETNEB/qupath-es/branches/main/protection
gh api repos/LABVETNEB/qupath-es/rulesets
gh api repos/LABVETNEB/qupath-es/collaborators --jq '.[].login'
```

**Elevar a máxima integridad** (el mantenedor también pasa por pull request):

```bash
gh api -X POST repos/LABVETNEB/qupath-es/branches/main/protection/enforce_admins
```

**Volver al modo equilibrado:**

```bash
gh api -X DELETE repos/LABVETNEB/qupath-es/branches/main/protection/enforce_admins
```

---

## Higiene recomendada

Cosas que la configuración del repositorio no puede garantizar por sí sola:

- **No añadas colaboradores** salvo que haga falta. Hoy la lista es de una
  persona, y esa es la protección más fuerte que existe.
- **Activa la verificación en dos pasos** en la cuenta de GitHub. Un token
  comprometido con permiso `repo` puede saltarse todo lo anterior si es de un
  administrador.
- **Usa tokens de alcance mínimo** y con caducidad para automatizaciones.
- **Revisa los pull requests de forks con cuidado**, sobre todo si tocan
  `runtime/` o `.github/workflows/`: un flujo de trabajo modificado puede
  ejecutar código.
- **Comprueba el diff de `versions/*/base/`** en cada revisión. Debe estar
  siempre vacío. La CI lo verifica, pero conviene mirarlo.

---

## Si algo se rompe

`main` no se puede borrar ni reescribir, así que la historia publicada es
recuperable. Si un tag pareciese haber cambiado de contenido, o un hash
publicado dejara de coincidir con lo descargado, trátalo como un incidente de
seguridad y sigue [`SECURITY.md`](../SECURITY.md).
