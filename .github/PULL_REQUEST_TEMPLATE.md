## Qué cambia

<!-- Describe el cambio en una o dos frases. -->

## Tipo de cambio

- [ ] Corrección de una traducción
- [ ] Nueva versión de QuPath (migración)
- [ ] Herramientas o pruebas
- [ ] Documentación
- [ ] Otro:

## Comprobaciones obligatorias

- [ ] `python -m unittest discover -s tests -p "test_*.py"` pasa completo
- [ ] No he editado ningún fichero de `versions/*/base/` (son inmutables)
- [ ] No he editado a mano `versions/*/dist/*.properties` (se genera)
- [ ] Si toqué traducciones: regeneré el bundle y el validador da `PASS`
- [ ] Si toqué traducciones: la auditoría lingüística da `SAFE TO INSTALL`
- [ ] No he introducido rutas absolutas de usuario ni configuración global

## Si cambia el bundle español

Pega la salida del validador y el nuevo SHA-256:

```
```

## Notas para el revisor

<!-- Cualquier cosa que convenga mirar con atención. -->
