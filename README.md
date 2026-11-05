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
  Busca empleo en InfoJobs, Indeed, LinkedIn, Tecnoempleo y Michael Page, y comprueba qué criterios cumples en cada oferta.
</p>

Aplicación de escritorio (GTK 4 + PyGObject, interfaz en español e inglés), de uso personal: sin servidor ni cuenta
propios, solo tu token de [Apify](https://apify.com/) para lanzar las búsquedas (Michael Page se lee directamente de
su web y no lo necesita).

- **Una búsqueda, cinco fuentes:** el puesto o las palabras clave, la ubicación y la fecha de publicación se
  lanzan a la vez en InfoJobs, Indeed, LinkedIn y Tecnoempleo (a través de Actors de Apify) y en Michael Page (leída
  directamente de su web, sin coste), y las ofertas repetidas entre fuentes se unifican.
- **Qué criterios cumples:** cada oferta se evalúa frente a tu **perfil** (habilidades técnicas y blandas,
  tus habilidades con un nivel de 0 a 10 cada una (en una ventana con la escala de niveles a la vista) y sinónimos, experiencia, estudios, idiomas con nivel, salario mínimo, modalidad, ubicación y lo que
  prefieres no encontrar) y muestra ✓ cumple, ✗ no cumple o ? no se puede saber, además de un encaje Alto, Medio
  o Bajo.
- **Honesta con lo que no sabe:** las fichas resumidas (cuando una fuente no trae la descripción completa) no la tienen, así
  que un requisito que no aparece queda como «no se sabe» y no cuenta en tu contra.
- **Varios perfiles** y **búsquedas guardadas**; las ofertas se guardan en tu equipo y las marcas como
  favoritas, postuladas o descartadas. Cada oferta tiene su **seguimiento**: fase del
  proceso (fase final, suspendido, rechazado…), próximos pasos, un **histórico** de contactos, entrevistas y pruebas,
  un **recordatorio** con fecha que te avisa al abrir la aplicación y tus **notas**.
- **Radares de competencias:** en el panel de cada oferta, uno general y los que definas en tu perfil por temas (Cloud,
  Lenguajes, Metodologías…), cuyos ejes son cosas concretas que aparecen en las ofertas con tu nivel de 0 a 10. Tu
  polígono (más intenso hacia los extremos) se superpone a lo que pide la oferta y cada radar da su **porcentaje de
  solape**; arriba, el solape global: cuanto más superpuestos, más posibilidades de encaje.
- **Compatibilidad ATS estimada:** un porcentaje por oferta de si tu CV pasaría el filtro automático con el que muchas
  empresas criban los currículums, con su veredicto, su fiabilidad, las palabras clave que tu CV no cita y los
  requisitos eliminatorios que no cumples. Es una estimación local y explicada, no un dato oficial: cada empresa
  configura su ATS. Cada radar lleva además una leyenda lateral que explica eje por eje lo que se ve.
- **Mapa:** las ofertas que ves como puntos sobre un mapa claro u oscuro, con el color de su encaje (necesita `gir1.2-shumate-1.0`; las imágenes son de CARTO y las ubicaciones se buscan en Nominatim, ver la política de privacidad).
- **Mercado:** tus radares frente a lo que piden, de media, las ofertas que estás viendo (con las de encaje alto o medio, si quieres), para ver de un vistazo en qué temas te quedas corto.
- **Panorama:** qué requisitos se repiten en la muestra y qué se puede concluir contando (lo más pedido, lo que conoces y ninguna oferta cita, lo que dominas y pocas ofertas piden, **qué te falta más veces** (cuadro rojo con lo que piden tus ofertas y no cubres) y **tus puntos fuertes** (cuadro verde con lo que ya tienes y más piden), cuántas ofertas publican salario, cuántas son remotas…).
- **Exporta** lo que ves a un informe HTML autocontenido o a una tabla CSV.
- **Control del gasto:** antes de buscar ves una estimación del coste en Apify, y cada búsqueda lleva un tope de
  gasto que tú configuras.
- **Modo claro y oscuro** con los iconos del sistema, y **español e inglés** con selector de idioma.

## Documentación

Toda la documentación —instalación, guía de uso, especificaciones técnicas, solución de problemas y más— está en
la **[wiki del proyecto](https://github.com/seguidodoblado/grepleo/wiki)** (español e inglés).

## Servicios de terceros

Grepleo usa [Apify](https://apify.com/) para obtener las ofertas, y en concreto **Actors de la comunidad** de
Apify (de sus autores, no de Apify) que acceden a InfoJobs, Indeed, LinkedIn y Tecnoempleo. Esos sitios no ofrecen una API
pública de búsqueda y sus condiciones de uso restringen el acceso automatizado: el uso es personal y responsabilidad
de quien lo lanza. Los Actors pueden dejar de funcionar o cambiar sin avisar.

**Michael Page** es la excepción: la aplicación lee directamente su web pública (michaelpage.es) desde tu equipo, solo
las rutas de búsqueda y de ficha que su `robots.txt` permite, con pausas entre peticiones y un máximo de ofertas por
búsqueda. No pasa por Apify ni cuesta nada, pero depende del diseño de esa web y puede dejar de funcionar si cambia.

## Privacidad

Grepleo no tiene servidor ni cuenta propios y no recoge datos. A Apify solo se envían las palabras clave, la
ubicación y los filtros de cada búsqueda, y tu token para autorizarla; **tu perfil y tus criterios no salen de tu
equipo**. Qué se guarda y dónde está en la **[política de privacidad](PRIVACY.md)**.

## Licencia

Este proyecto se distribuye bajo la GNU General Public License, versión 3 o posterior (ver `COPYING`).
