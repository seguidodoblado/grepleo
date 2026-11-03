<p align="right"><a href="PRIVACY.md">🇪🇸 Español</a></p>

# Privacy policy

Last updated: November 3, 2026.

Grepleo is a desktop application for personal use. It has no server or account of its own and its author receives
no data from the people who use it. It only talks to Apify when you run a search.

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
- The profiles, saved searches, offers and their status, in `~/.local/share/grepleo/grepleo.db`.
- The settings, in `~/.config/grepleo/settings.json`.
- The HTML and CSV reports, wherever you choose when exporting them.

## Who it is shared with

Only with the services involved when you run a search:

- **[Apify](https://apify.com/)** (`api.apify.com`): receives the **keywords, location, filters and number of
  offers** of each search, and your token to authorize it. It is subject to Apify's terms and privacy policy, and
  the usage is billed to or deducted from your Apify credit.
- **Apify community Actors** (developed by third parties): receive that same search data and access InfoJobs,
  Indeed and LinkedIn on their own. Each Actor has its own author and terms.

**Your profile, your criteria, your notes and the marks on offers are never sent**: the evaluation runs on your
computer. The application includes no analytics, telemetry or advertising.

## How to delete your data

Remove `~/.config/grepleo/` and `~/.local/share/grepleo/`, and delete the token with **Preferences → Forget the
token** (or from your password manager, entry “grepleo”). Uninstalling the application does not delete that data by
itself. What Apify or the Actors have already processed is managed from your Apify account.

## Changes to this policy

If it changes, this document and the date above will be updated; the history is in the repository.

## Contact

Jose Antonio Seguido Doblado · jose.antonio.seguido@gmail.com
