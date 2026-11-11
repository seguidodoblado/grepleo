# Cómo contribuir / Contributing

## 🇪🇸 Español

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

Este proyecto se distribuye bajo la licencia [PolyForm Noncommercial 1.0.0](COPYING): uso, copia y modificación libres para fines no comerciales. Al contribuir aceptas que tu aportación se ofrezca bajo esa misma licencia y, además, concedes al autor del proyecto una licencia perpetua, mundial e irrevocable para usar, modificar y distribuir tu aportación, también con fines comerciales y bajo otras licencias (por ejemplo, si algún día se ofrece una versión comercial). Conservas la autoría de lo que escribas. Si no estás de acuerdo, abre una issue en lugar de una pull request.

---

## 🇺🇸 English

Thank you for your interest in contributing to this project.

## Development

See the [Development environment](https://github.com/seguidodoblado/grepleo/wiki/en-01-4-installation-and-setup#development-environment)
section of the wiki to set up your environment, and
[Checks (for contributing)](https://github.com/seguidodoblado/grepleo/wiki/en-01-4-installation-and-setup#checks-for-contributing)
to know what must pass before opening a pull request.

## Changes

Before making major changes, open an issue to describe the proposal and make it easier to discuss.

## Pull Requests

Create a small branch from `main`. If you add or change a text of the interface, follow `po/README.md`.
Contributions should include the corresponding tests where applicable, and if the visible behaviour changes, the
wiki must be updated.

A **new job source** is a module in `src/grepleo/sources/` with its Apify Actor and its tests using sample
responses; do not test against Apify or the job sites.

Changes must keep the quality and conventions established for the project.

This project is distributed under the [PolyForm Noncommercial 1.0.0](COPYING) license: free use, copying and modification for noncommercial purposes. By contributing you agree that your contribution is offered under that same license and, in addition, you grant the project author a perpetual, worldwide, irrevocable license to use, modify and distribute your contribution, including for commercial purposes and under other licenses (for example, if a commercial version is ever offered). You keep the authorship of what you write. If you do not agree, open an issue instead of a pull request.
