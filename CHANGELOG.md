# Changelog

## 0.1.2 — 2026-11-02

- `tps init` creates one game per subfolder of `./photos`, taking the date and title from
  folder names like `2026-09-12 vs North`
- The face models are downloaded once before scanning starts (previously every worker
  downloaded them at the same time)
- Quieter output: no per-worker model messages or dependency deprecation warnings, and
  workers shut down cleanly
- The progress rate counts scanning time only, not model start-up
- Clearer error when an event's photo folder is missing
- Python 3.10–3.14 (ONNX Runtime has no 3.15 builds yet); Mac install steps in the README

## 0.1.1 — 2026-11-02

- Published on PyPI: `pip install team-photo-sorter`
- Live demo site with illustrated players, built by `examples/demo/make_demo.py`
- Fix: face crops were misplaced for photos smaller than 1800 px on the long side
- Require InsightFace 1.x (tested with 1.0.1; 2.x changed its API). No C compiler needed.
- Continuous integration: tests on Python 3.10, 3.12 and 3.13

## 0.1.0 — 2026-11-02

First public release, extracted from a tool built for one high school team's
season (17 games, about 53,000 photos).

- `tps scan`, `cluster`, `images`, `build`, `all`, `labels`, `export`
- Encrypted static site: game picker, player tiles, contact sheets, in-site
  viewer, "Could these also be …?" and cross-game suggestions, shareable labels
- Reference-photo seeding for pre-naming a player across games
- Deterministic encryption, so redeploys upload only changed files
