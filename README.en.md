<p align="right"><a href="README.md">🇪🇸 Español</a></p>

<p align="center">
  <img src="grepleo.svg" alt="Grepleo logo" width="128">
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
  Search for jobs on InfoJobs, Indeed, LinkedIn, Tecnoempleo and Michael Page, and check which criteria you meet in each offer.
</p>

Desktop application (GTK 4 + PyGObject, interface in Spanish and English), for personal use: no server or account
of its own, only your [Apify](https://apify.com/) token to run the searches (Michael Page is read directly from its website and
does not need it).

- **One search, five sources:** the position or keywords, the location and the posting date are sent at once to
  InfoJobs, Indeed, LinkedIn and Tecnoempleo (through Apify Actors) and Michael Page (read directly from its website,
  at no cost), and offers repeated across sources are merged.
- **Which criteria you meet:** each offer is evaluated against your **profile** (technical and soft skills,
  what you master and what you know, with synonyms, experience, education, languages with level, minimum salary, work mode, location
  and what you would rather not find) and shows ✓ met, ✗ not met or ? cannot be known, plus a High, Medium or Low
  fit.
- **Honest about what it does not know:** summary cards (when a source does not bring the full description) do not have it, so
  a requirement that does not appear stays as "cannot tell" and does not count against you.
- **Several profiles** and **saved searches**; offers are stored on your computer and you can mark them as
  favourite, applied or discarded. Each offer has its own **follow-up**: process
  stage (final stage, suspended, rejected…), next steps, a **history** of contacts, interviews and tests, a dated
  **reminder** that warns you when the application opens and your **notes**.
- **Skills radars:** in each offer's panel, a general one and those you define in your profile by topic (Cloud,
  Languages, Methodologies…), whose axes are concrete things that appear in offers, with your level from 0 to 10.
  Your polygon (more intense towards the edges) is overlaid on what the offer asks and each radar gives its **overlap
  percentage**; at the top, the overall overlap: the more they overlap, the better the chances of fit.
- **Estimated ATS compatibility:** a percentage per offer of whether your CV would pass the automatic filter many
  companies use to screen CVs, with its verdict, its reliability, the keywords your CV does not cite and the
  knock-out requirements you do not meet. It is a local, explained estimate, not an official figure: each company
  configures its own ATS. Each radar also has a side legend that explains, axis by axis, what you are seeing.
- **Market:** your radars against what the offers you are looking at ask for on average (or only the high or medium fit ones), to see at a glance on which topics you fall short.
- **Overview:** which requirements repeat across the sample and what can be concluded by counting (most
  requested, the nice-to-haves of your profile that no offer mentions, **what you lack most often** (a red card with what your offers ask for and you do not cover) and **your strengths** (a green card with what you already have and they ask for most), how many offers publish a salary, how many are remote…).
- **Export** what you see to a self-contained HTML report or a CSV table.
- **Spending control:** before searching you see an estimate of the cost on Apify, and every search has a
  spending cap that you configure.
- **Light and dark mode** with system icons, and **Spanish and English** with a language selector.

## Documentation

All the documentation —installation, usage guide, technical specifications, troubleshooting and more— is in the
**[project wiki](https://github.com/seguidodoblado/grepleo/wiki)** (Spanish and English).

## Third-party services

Grepleo uses [Apify](https://apify.com/) to get the offers, specifically **community Actors** on Apify (by their
authors, not by Apify) that access InfoJobs, Indeed, LinkedIn and Tecnoempleo. Those sites offer no public search API and
their terms of use restrict automated access: the use is personal and the responsibility of whoever runs it.
Actors may stop working or change without notice.

**Michael Page** is the exception: the application reads its public website (michaelpage.es) directly from your
computer, only the search and offer routes its `robots.txt` allows, with pauses between requests and a cap on the
number of offers per search. It does not go through Apify and costs nothing, but it depends on that website's
design and may stop working if it changes.

## Privacy

Grepleo has no server or account of its own and collects no data. Only the keywords, location and filters of each
search are sent to Apify, plus your token to authorize it; **your profile and criteria never leave your
computer**. What is stored and where is in the **[privacy policy](PRIVACY.en.md)**.

## License

This project is distributed under the GNU General Public License, version 3 or later (see `COPYING`).
