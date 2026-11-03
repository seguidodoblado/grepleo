<p align="right"><a href="PRIVACY.en.md">🇺🇸 English</a></p>

# Política de privacidad

Última actualización: 3 de noviembre de 2026.

Grepleo es una aplicación de escritorio de uso personal. No tiene servidor ni cuenta propios y su autor no recibe
ningún dato de quien la usa. Solo se comunica con Apify cuando tú lanzas una búsqueda.

## Qué datos trata

- **Tu perfil:** cargo, años de experiencia, estudios, idiomas, requisitos, salario mínimo, ubicaciones y notas.
- **Las búsquedas:** palabras clave, ubicación, filtros y fuentes elegidas.
- **Las ofertas** que devuelven las búsquedas y la marca que les pones (favorita, postulada o descartada).
- **Tu token de Apify**, que generas tú y que autoriza las búsquedas con tu cuenta.
- **Tus ajustes:** idioma, tema y gasto máximo por búsqueda.

## Dónde se guardan

En tu equipo:

- El token de Apify, en el **llavero del sistema** (libsecret), nunca en un archivo.
- Los perfiles, las búsquedas guardadas, las ofertas y su estado, en `~/.local/share/grepleo/grepleo.db`.
- Los ajustes, en `~/.config/grepleo/settings.json`.
- Los informes HTML y CSV, donde tú elijas al exportarlos.

## Con quién se comparte

Solo con los servicios que intervienen cuando lanzas una búsqueda:

- **[Apify](https://apify.com/)** (`api.apify.com`): recibe las **palabras clave, la ubicación, los filtros y el
  número de ofertas** de cada búsqueda, y tu token para autorizarla. Queda sujeto a las condiciones y a la política
  de privacidad de Apify, y el uso se factura o descuenta de tu crédito de Apify.
- **Actors de la comunidad de Apify** (desarrollados por terceros): reciben esos mismos datos de la búsqueda y
  acceden por su cuenta a InfoJobs, Indeed y LinkedIn. Cada Actor tiene su autor y sus condiciones.

**Tu perfil, tus criterios, tus notas y las marcas de las ofertas nunca se envían**: la evaluación se hace en tu
equipo. La aplicación no incluye analítica, telemetría ni publicidad.

## Cómo borrar tus datos

Elimina `~/.config/grepleo/` y `~/.local/share/grepleo/`, y borra el token con **Preferencias → Olvidar el token**
(o desde tu gestor de contraseñas, entrada «grepleo»). Desinstalar la aplicación no borra esos datos por sí solo.
Lo que ya hayan procesado Apify o los Actors se gestiona desde tu cuenta de Apify.

## Cambios en esta política

Si cambia, se actualizará este documento y la fecha de arriba; el historial está en el repositorio.

## Contacto

Jose Antonio Seguido Doblado · jose.antonio.seguido@gmail.com
