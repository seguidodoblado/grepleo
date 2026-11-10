# Política de privacidad / Privacy policy

## 🇪🇸 Español

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

---

## 🇺🇸 English

Last updated: November 5, 2026.

Grepleo is a desktop application for personal use. It has no server or account of its own and its author receives
no data from the people who use it. It only talks to Apify when you run a search and, if you open the **Map** tab, to OpenStreetMap (see below).

## What data it handles

- **Your profile:** role, years of experience, education, languages, requirements, minimum salary, locations and
  notes.
- **The searches:** keywords, location, filters and chosen sources.
- **The offers** returned by the searches and the mark you give them (favourite, applied or discarded).
- **Your Apify token**, which you generate yourself and which authorizes the searches with your account.
- **Your settings:** language, theme and maximum spend per search.

## Where it is stored

On your computer:

- The Apify token, in the **system keyring** (libsecret), never in a file.
- The profiles, saved searches, offers, their status and **your follow-up (stage, next steps, history), notes and reminders** (they never leave your computer and are not included in the HTML or CSV reports), in `~/.local/share/grepleo/grepleo.db`.
- The locations already looked up for the map (the location text and its point), in the same database.
- The settings, in `~/.config/grepleo/settings.json`.
- The CV assistant's working folders, one per offer, in `~/.local/share/grepleo/cv/` (the offer, your CV built from the profile, a copy of the CV you uploaded and whatever the AI generates).
- An error log in `~/.local/share/grepleo/grepleo.log` (exceptions and warnings from the application itself; it is rotated above 1 MB and never sent anywhere).
- The HTML and CSV reports, wherever you choose when exporting them.

## Who it is shared with

Only with the services involved when you run a search:

- **[Apify](https://apify.com/)** (`api.apify.com`): receives the **keywords, location, filters and number of
  offers** of each search, and your token to authorize it. It is subject to Apify's terms and privacy policy, and
  the usage is billed to or deducted from your Apify credit.
- **Apify community Actors** (developed by third parties): receive that same search data and access InfoJobs,
  Indeed, LinkedIn and Tecnoempleo on their own. Each Actor has its own author and terms.
- **Michael Page** (`www.michaelpage.es`): if you choose this source, the application connects **directly from your
  computer**, without going through Apify. The site receives your IP address and the search **keywords** (not your
  location, which is filtered on your computer), and the application identifies itself by name and version
  (`Grepleo/x.y.z`). It is subject to Michael Page's terms and privacy policy. No token is needed and it costs
  nothing.

- **Map tab** (only if you open it and have `gir1.2-shumate-1.0` installed): the **map images** are served by **OpenStreetMap** (`tile.openstreetmap.org`), which receives your **IP address and the area of the map you look at** (not your offers, profile or searches). To place the offers, the **text of each distinct location** (“Madrid”, “Arlington, VA”) is sent once to **Nominatim** (`nominatim.openstreetmap.org`, OpenStreetMap's search engine), which also receives your IP and the application's name and version (`Grepleo/x.y.z`); it does not receive the company, the position or anything from the profile. The answers, including “not found” ones, are stored in your database so the question is not repeated, and its limit of one request per second is respected. Both services belong to the OpenStreetMap Foundation, with their own terms and privacy policy. Remote or location-less offers are not sent.
- **Study plan** (only if you press “Study” and a link): a certification's official page or a search on Udemy or Coursera opens in your browser; the application does not connect to those sites or send them anything, it only opens the address with the skill's name.
- **Your own AI CLI** (Claude Code, OpenCode, Codex…): only if you press **Tailor CV**. A terminal opens with the CLI you installed and configured, using your account, and it is given a folder with the offer, your CV built from the profile (name, contact, experience, education…) and your uploaded CV. What reaches its provider is subject to that service's terms and privacy policy. Grepleo does not see your credentials and calls no API.

**Your profile, your criteria, your notes and the marks on offers are not sent to any service of the application**: the
evaluation runs on your computer. The only thing that can leave is what you send to your own AI with **Tailor CV**. The application includes no analytics, telemetry or advertising.

## How to delete your data

Remove `~/.config/grepleo/` and `~/.local/share/grepleo/`, and delete the token with **Preferences → Forget the
token** (or from your password manager, entry “grepleo”). Uninstalling the application does not delete that data by
itself. What Apify or the Actors have already processed is managed from your Apify account.

## Changes to this policy

If it changes, this document and the date above will be updated; the history is in the repository.

## Contact

Jose Antonio Seguido Doblado · jose.antonio.seguido@gmail.com
