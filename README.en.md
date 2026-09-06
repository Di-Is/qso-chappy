# chappy — Code for Handling Absorption Profiles with PYthon

[日本語](README.md) | **English**

[![CI](https://github.com/Di-Is/qso-chappy/actions/workflows/ci.yml/badge.svg)](https://github.com/Di-Is/qso-chappy/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22162939.svg)](https://doi.org/10.5281/zenodo.22162939)

Light from a distant quasar passes through countless clouds of gas on its way to Earth.
Along the way, specific wavelengths are absorbed, leaving dark features — absorption lines — in the spectrum.

chappy is a desktop application that measures the shape of those lines to estimate how much gas
blocked the light, and how fast and how hot that gas was.
It is built for everyone from high-school students and citizen scientists to graduate students and
researchers who use it daily.

## What you can do

- **View spectra** — Load spectroscopic data in FITS format and pan and zoom across wavelength
- **Fit the continuum** — Interactively set the continuum level that absorption measurements are made against
- **Model absorption lines** — Overlay Voigt profiles to estimate column density, Doppler parameter, and radial velocity
- **Optimize automatically** — Refine your hand-placed initial guesses into a best-fit solution
- **Identify absorbers** — Work out which element or ion produced a feature from the pattern of wavelengths
- **Keep your results** — Save an analysis as a project to resume, share, or export later

The interface is available in Japanese and English.

## Getting started

1. Download the latest zip file from [Releases](https://github.com/Di-Is/qso-chappy/releases) and extract it anywhere you like
2. Follow the steps in [INSTALL.en.md](INSTALL.en.md)

You do not need to install Python yourself — the required Python version and dependencies are
downloaded automatically on first launch.

**A tutorial starts automatically the first time you launch the app.**
A sample quasar spectrum is bundled, so you can try it right away without preparing your own data.

## Learning the interface

Open **Help > User Guide** in the app for screen-by-screen instructions.
The manual ships with the release package and opens in whichever language the interface is set to.

## Requirements

- Windows / macOS / Linux
- Python 3.12 or later

## Getting help

If something does not work, or you are unsure how to proceed, write to our mailing list at
[chappy-ml@shinshu-u.ac.jp](mailto:chappy-ml@shinshu-u.ac.jp).
No astronomy or programming background is required — just tell us what you were trying to do and
what happened instead.

If you are comfortable with GitHub, you are also welcome to file bug reports and feature requests
on [Issues](https://github.com/Di-Is/qso-chappy/issues).

## Contributing

Bug reports, feature suggestions, and pull requests are welcome.
See [CONTRIBUTING.en.md](CONTRIBUTING.en.md) for development setup and coding conventions.

## License

MIT License — free to use, modify, and redistribute for research, education, or any other purpose.
See [LICENSE](LICENSE) for details.

## Citing chappy

If you use chappy in your research, please cite it via the DOI below.
The link always resolves to the latest version.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22162939.svg)](https://doi.org/10.5281/zenodo.22162939)

Bibliographic metadata lives in [CITATION.cff](CITATION.cff), and GitHub's
"Cite this repository" panel can export it in the format you need.

## About this project

Provenance and observing details for the bundled sample data are documented in
[sample_data/README.md](sample_data/README.md).
