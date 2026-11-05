<p align="right"><a href="PRIVACY.en.md">🇺🇸 English</a></p>

# Política de privacidad

Última actualización: 5 de noviembre de 2026.

Grepleo es una aplicación de escritorio de uso personal. No tiene servidor ni cuenta propios y su autor no recibe
ningún dato de quien la usa. Solo se comunica con Apify cuando tú lanzas una búsqueda y, si abres la pestaña **Mapa**, con OpenStreetMap (ver más abajo).

## Qué datos trata

- **Tu perfil:** cargo, años de experiencia, estudios, idiomas, requisitos, salario mínimo, ubicaciones y notas.
- **Las búsquedas:** palabras clave, ubicación, filtros y fuentes elegidas.
- **Las ofertas** que devuelven las búsquedas y la marca que les pones (favorita, postulada o descartada).
- **Tu token de Apify**, que generas tú y que autoriza las búsquedas con tu cuenta.
- **Tus ajustes:** idioma, tema y gasto máximo por búsqueda.

## Dónde se guardan

En tu equipo:

- El token de Apify, en el **llavero del sistema** (libsecret), nunca en un archivo.
- Los perfiles, las búsquedas guardadas, las ofertas, su estado y **tu seguimiento (fase, próximos pasos, histórico), notas y recordatorios** (nunca salen de tu equipo ni van a los informes HTML o CSV), en `~/.local/share/grepleo/grepleo.db`.
- Las ubicaciones ya buscadas para el mapa (el texto de la ubicación y su punto), en la misma base de datos.
- Los ajustes, en `~/.config/grepleo/settings.json`.
- Las carpetas de trabajo del asistente de CV, una por oferta, en `~/.local/share/grepleo/cv/` (la oferta, tu CV construido desde el perfil, una copia del CV que hayas subido y lo que genere la IA).
- Un registro de errores en `~/.local/share/grepleo/grepleo.log` (excepciones y avisos de la propia aplicación; se rota al pasar de 1 MB y nunca se envía a ningún sitio).
- Los informes HTML y CSV, donde tú elijas al exportarlos.

## Con quién se comparte

Solo con los servicios que intervienen cuando lanzas una búsqueda:

- **[Apify](https://apify.com/)** (`api.apify.com`): recibe las **palabras clave, la ubicación, los filtros y el
  número de ofertas** de cada búsqueda, y tu token para autorizarla. Queda sujeto a las condiciones y a la política
  de privacidad de Apify, y el uso se factura o descuenta de tu crédito de Apify.
- **Actors de la comunidad de Apify** (desarrollados por terceros): reciben esos mismos datos de la búsqueda y
  acceden por su cuenta a InfoJobs, Indeed, LinkedIn y Tecnoempleo. Cada Actor tiene su autor y sus condiciones.
- **Michael Page** (`www.michaelpage.es`): si eliges esta fuente, la aplicación se conecta **directamente desde tu
  equipo**, sin pasar por Apify. El sitio recibe tu dirección IP y las **palabras clave** de la búsqueda (no tu
  ubicación, que se filtra en tu equipo), y la aplicación se identifica con su nombre y versión (`Grepleo/x.y.z`).
  Queda sujeto a las condiciones y a la política de privacidad de Michael Page. No hace falta token ni cuesta nada.

- **Pestaña Mapa** (solo si la abres y tienes instalado `gir1.2-shumate-1.0`): las **imágenes del mapa** las sirve **OpenStreetMap** (`tile.openstreetmap.org`), que recibe tu **dirección IP y la zona del mapa que miras** (no tus ofertas, tu perfil ni tus búsquedas). Para colocar las ofertas, el **texto de cada ubicación distinta** («Madrid», «Arlington, VA») se envía una sola vez a **Nominatim** (`nominatim.openstreetmap.org`, el buscador de OpenStreetMap), que recibe también tu IP y el nombre y la versión de la aplicación (`Grepleo/x.y.z`); no recibe la empresa, el puesto ni nada del perfil. Las respuestas, también las de «no encontrado», se guardan en tu base de datos para no repetir la pregunta, y se respeta su límite de una petición por segundo. Ambos servicios son de la Fundación OpenStreetMap, con sus propias condiciones y política de privacidad. Las ofertas remotas o sin ubicación no se envían.
- **Plan de estudio** (solo si pulsas «Estudiar» y un enlace): se abre en tu navegador la página oficial de una certificación o una búsqueda en Udemy o Coursera; la aplicación no se conecta a esos sitios ni les envía nada, solo abre la dirección con el nombre de la habilidad.
- **Tu propia CLI de IA** (Claude Code, OpenCode, Codex…): solo si pulsas **Adaptar CV**. Se abre un terminal con la CLI que tú hayas instalado y configurado, con tu cuenta, y se le da una carpeta con la oferta, tu CV construido desde el perfil (nombre, contacto, experiencia, formación…) y tu CV subido. Lo que llegue a su proveedor queda sujeto a las condiciones y a la política de privacidad de ese servicio. Grepleo no ve tus credenciales ni llama a ninguna API.

**Tu perfil, tus criterios, tus notas y las marcas de las ofertas no se envían a ningún servicio de la aplicación**: la
evaluación se hace en tu equipo. Lo único que puede salir es lo que tú mandes a tu propia IA con **Adaptar CV**. La aplicación no incluye analítica, telemetría ni publicidad.

## Cómo borrar tus datos

Elimina `~/.config/grepleo/` y `~/.local/share/grepleo/`, y borra el token con **Preferencias → Olvidar el token**
(o desde tu gestor de contraseñas, entrada «grepleo»). Desinstalar la aplicación no borra esos datos por sí solo.
Lo que ya hayan procesado Apify o los Actors se gestiona desde tu cuenta de Apify.

## Cambios en esta política

Si cambia, se actualizará este documento y la fecha de arriba; el historial está en el repositorio.

## Contacto

Jose Antonio Seguido Doblado · jose.antonio.seguido@gmail.com
