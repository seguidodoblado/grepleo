<p align="right"><a href="CONTRIBUTING.en.md">🇺🇸 English</a></p>

# Cómo contribuir

Gracias por tu interés en contribuir a este proyecto.

## Desarrollo

Consulta la sección [Entorno de desarrollo](https://github.com/seguidodoblado/grepleo/wiki/es-01-4-instalacion-configuracion#entorno-de-desarrollo)
de la wiki para preparar el entorno, y
[Comprobaciones (para contribuir)](https://github.com/seguidodoblado/grepleo/wiki/es-01-4-instalacion-configuracion#comprobaciones-para-contribuir)
para saber qué debe pasar antes de abrir una pull request.

## Cambios

Antes de realizar cambios importantes, abre una issue para describir la propuesta y facilitar su discusión.

## Pull Requests

Crea una rama pequeña desde `main`. Si añades o cambias un texto de la interfaz, sigue `po/README.md`. Las
contribuciones deben incluir las pruebas correspondientes cuando sea aplicable, y si cambia el comportamiento
visible, hay que actualizar la wiki.

Una **fuente nueva de ofertas** es un módulo en `src/grepleo/sources/` con su Actor de Apify y sus pruebas con
respuestas de ejemplo; no hagas pruebas contra Apify ni contra los portales.

Los cambios deben mantener la calidad y las convenciones establecidas para el proyecto.

Este proyecto se distribuye bajo la licencia [PolyForm Noncommercial 1.0.0](COPYING): uso, copia y modificación libres para fines no comerciales. Al contribuir aceptas que tu aportación se ofrezca bajo esa misma licencia.
