# Contributing

Thanks for helping! This project is small, so the process is simple.

## Setup

```bash
git clone https://github.com/andyknosp1/team-photo-sorter.git
cd team-photo-sorter
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The tests don't need the face model or any real photos. They write synthetic
face embeddings straight into the database, so they run anywhere in a few
seconds.

## Ground rules

- **Never commit real photos, face data or names.** Not in tests, issues,
  screenshots or examples. Use synthetic data, as `tests/conftest.py` does, and
  fictional names.
- **Keep it local-first.** Pull requests that send photos or faces to a remote
  service won't be accepted.
- **Keep the site static.** No server component; it has to run on free static
  hosting.
- **Measure before tuning.** When you change clustering settings or thresholds,
  include before/after numbers on a real (private) data set in the PR
  description, without the data itself.

## Pull requests

- One change per PR, with a test when it's testable.
- Run `pytest` before opening it.
- By contributing you agree your contribution is licensed under the Apache
  License 2.0 (see LICENSE, section 5).
