# Contributing to docassert

Thanks for helping. docassert is the reference implementation of the
[PMO as Code specification](https://github.com/c4g-john/pmo-as-code-spec) —
changes to *behavior specified there* (grammars, blocking semantics) should
start as a spec discussion; tool-level changes start here.

## Development setup

```bash
git clone https://github.com/c4g-john/docassert && cd docassert
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,convert]"
```

## Before you open a PR

All three must pass (CI runs them on Python 3.10–3.13 and Windows):

```bash
ruff check .                     # lint
mypy --config-file pyproject.toml  # types
pytest -q --cov=docassert        # tests, coverage floor 80%
```

House rules:

- **Structural checks stay deterministic**; anything judgment-based is
  semantic and must never block (see the spec, §8).
- New behavior comes with tests. Bug fixes come with a regression test.
- The packaged defaults under `docassert/_data/` must stay identical to the
  repo-root copies (`criteria/`, `schema/`, `profiles/`, `templates/`,
  `skills/`, `consistency.yaml`) — a drift-guard test enforces it, so change
  both.
- Update `CHANGELOG.md` under **Unreleased** for anything user-visible.
- Adding a document kind is a template + schema + criteria trio (in both
  copies) — usually no code.

## Releases (maintainers)

Bump `docassert/__init__.py:__version__`, move the CHANGELOG entries under the
new version, merge, then publish a GitHub Release tagged `vX.Y.Z` — the
`release` workflow builds and uploads to PyPI via Trusted Publishing.

Every release also gets a news entry on the site: add a dated Markdown file
to `src/content/news/` in [c4g-john/pmo-as-code](https://github.com/c4g-john/pmo-as-code)
stating what shipped, with the artifacts linked. The /news/ page and the
RSS feed at pmoascode.com/rss.xml generate from it.

## License

Contributions are accepted under Apache-2.0 (see LICENSE/NOTICE).
