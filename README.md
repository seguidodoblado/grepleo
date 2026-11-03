<p align="right"><a href="README.en.md">🇺🇸 English</a></p>

<p align="center">
  <img src="grepleo.svg" alt="Logotipo de Grepleo" width="128">
</p>

<h1 align="center">Grepleo</h1>

<p align="center">
  <a href="https://github.com/seguidodoblado/grepleo/releases"><img src="https://img.shields.io/github/v/release/seguidodoblado/grepleo" alt="release"></a>
  <a href="https://github.com/seguidodoblado/grepleo/actions/workflows/ci.yml"><img src="https://github.com/seguidodoblado/grepleo/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/seguidodoblado/grepleo/actions/workflows/cd.yml"><img src="https://github.com/seguidodoblado/grepleo/actions/workflows/cd.yml/badge.svg" alt="CD"></a>
  <a href="https://github.com/seguidodoblado/grepleo/blob/main/COPYING"><img src="https://img.shields.io/github/license/seguidodoblado/grepleo" alt="license"></a>
  <a href="https://github.com/seguidodoblado/grepleo/commits/main/"><img src="https://img.shields.io/github/last-commit/seguidodoblado/grepleo" alt="last commit"></a>
  <a href="https://github.com/seguidodoblado/grepleo/commits/main/"><img src="https://img.shields.io/github/commit-activity/t/seguidodoblado/grepleo" alt="total commits"></a>
  <a href="https://github.com/seguidodoblado/grepleo/releases"><img src="https://img.shields.io/github/downloads/seguidodoblado/grepleo/total" alt="downloads"></a>
  <a href="https://github.com/seguidodoblado/grepleo/stargazers"><img src="https://img.shields.io/github/stars/seguidodoblado/grepleo?style=flat" alt="stars"></a>
  <a href="https://github.com/seguidodoblado/grepleo/issues"><img src="https://img.shields.io/github/issues/seguidodoblado/grepleo" alt="issues"></a>
  <a href="https://github.com/seguidodoblado/grepleo"><img src="https://img.shields.io/github/languages/top/seguidodoblado/grepleo" alt="language"></a>
  <a href="https://codetime.dev"><img alt="CodeTime Badge" src="https://shields.jannchie.com/endpoint?style=flat&color=0284c7&url=https%3A%2F%2Fcodetime.dev%2Fv3%2Fusers%2Fshield%3Fuid%3D36830"></a>
  <a href="https://wakatime.com/badge/github/seguidodoblado/grepleo"><img src="https://wakatime.com/badge/github/seguidodoblado/grepleo.svg" alt="wakatime"></a>
</p>

<p align="center">
  Busca empleo en InfoJobs, Indeed y LinkedIn y comprueba qué criterios cumples en cada oferta.
</p>

Aplicación de escritorio (GTK 4 + PyGObject, interfaz en español e inglés), de uso personal: sin servidor ni cuenta
propios, solo tu token de [Apify](https://apify.com/) para lanzar las búsquedas.

- **Una búsqueda, tres fuentes:** el puesto o las palabras clave, la ubicación y la fecha de publicación se
  lanzan a la vez en InfoJobs, Indeed y LinkedIn (a través de Actors de Apify), y las ofertas repetidas entre
  fuentes se unifican.
- **Qué criterios cumples:** cada oferta se evalúa frente a tu **perfil** (requisitos imprescindibles y
  deseables con sinónimos, experiencia, estudios, idiomas con nivel, salario mínimo, modalidad, ubicación y lo que
  prefieres no encontrar) y muestra ✓ cumple, ✗ no cumple o ? no se puede saber, además de un encaje Alto, Medio
  o Bajo.
- **Honesta con lo que no sabe:** las fichas resumidas (como las de InfoJobs) no traen la descripción completa, así
  que un requisito que no aparece queda como «no se sabe» y no cuenta en tu contra.
- **Varios perfiles** y **búsquedas guardadas**; las ofertas se guardan en tu equipo y las marcas como
  favoritas, postuladas o descartadas.
- **Panorama:** qué requisitos se repiten en la muestra y qué se puede concluir contando (lo más pedido, lo que
  nadie pide, cuántas ofertas publican salario, cuántas son remotas…).
- **Exporta** lo que ves a un informe HTML autocontenido o a una tabla CSV.
- **Control del gasto:** antes de buscar ves una estimación del coste en Apify, y cada búsqueda lleva un tope de
  gasto que tú configuras.
- **Modo claro y oscuro** con los iconos del sistema, y **español e inglés** con selector de idioma.

## Documentación

Toda la documentación —instalación, guía de uso, especificaciones técnicas, solución de problemas y más— está en
la **[wiki del proyecto](https://github.com/seguidodoblado/grepleo/wiki)** (español e inglés).

## Servicios de terceros

Grepleo usa [Apify](https://apify.com/) para obtener las ofertas, y en concreto **Actors de la comunidad** de
Apify (de sus autores, no de Apify) que acceden a InfoJobs, Indeed y LinkedIn. Esos sitios no ofrecen una API
pública de búsqueda y sus condiciones de uso restringen el acceso automatizado: el uso es personal y responsabilidad
de quien lo lanza. Los Actors pueden dejar de funcionar o cambiar sin avisar.

## Privacidad

Grepleo no tiene servidor ni cuenta propios y no recoge datos. A Apify solo se envían las palabras clave, la
ubicación y los filtros de cada búsqueda, y tu token para autorizarla; **tu perfil y tus criterios no salen de tu
equipo**. Qué se guarda y dónde está en la **[política de privacidad](PRIVACY.md)**.

## Licencia

Este proyecto se distribuye bajo la GNU General Public License, versión 3 o posterior (ver `COPYING`).
