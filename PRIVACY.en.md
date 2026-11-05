<p align="right"><a href="PRIVACY.md">🇪🇸 Español</a></p>

# Privacy policy

Last updated: November 5, 2026.

Grepleo is a desktop application for personal use. It has no server or account of its own and its author receives
no data from the people who use it. It only talks to Apify when you run a search and, if you open the **Map** tab, to CARTO and Nominatim (see below).

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

- **Map tab** (only if you open it and have `gir1.2-shumate-1.0` installed): the **map images** are served by **CARTO** (`basemaps.cartocdn.com`, on OpenStreetMap data), which receives your **IP address and the area of the map you look at** (not your offers, profile or searches). To place the offers, the **text of each distinct location** (“Madrid”, “Arlington, VA”) is sent once to **Nominatim** (`nominatim.openstreetmap.org`, OpenStreetMap's search engine), which also receives your IP and the application's name and version (`Grepleo/x.y.z`); it does not receive the company, the position or anything from the profile. The answers, including “not found” ones, are stored in your database so the question is not repeated, and its limit of one request per second is respected. Both services have their own terms and privacy policies. Remote or location-less offers are not sent.
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
