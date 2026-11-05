<p align="right"><a href="CONTRIBUTING.md">🇪🇸 Español</a></p>

# Contributing

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

This project is distributed under the [PolyForm Noncommercial 1.0.0](COPYING) license: free use, copying and modification for noncommercial purposes. By contributing you agree that your contribution is offered under that same license.
