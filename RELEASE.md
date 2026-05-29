# Release Checklist

Use this checklist for tagged `cast-a-doc` releases.

## Version Policy

- `VERSION` stores the package version without a leading `v`.
- Git tags use `v<version>`, for example `v0.1.0`.
- Install docs should pin the latest stable tag with `gh skill install --pin v<version>`.
- Use full commit SHAs only for unreleased fixes or temporary verification.
- Runtime renderer scripts must continue to work without installing the package.

## Before Tagging

```bash
python3 scripts/validate_project_profile.py --repo-root .
python3 scripts/validate_schema_contract.py
python3 scripts/validate_package_metadata.py
python3 -m unittest discover -s tests
python3 scripts/check_fixtures.py
python3 scripts/visual_lint.py --input-dir examples --input-dir plan --input-dir spec --input index.html --input install.html --input readme.html --input todo.html --input changelist.html
```

Also verify the README install commands, `INSTALL_AGENT.md`, `site/install.json`, and generated `install.html` all reference the intended release tag.

## Tagging

```bash
version="$(cat VERSION)"
git tag "v${version}"
git push origin "v${version}"
```

## After Publishing

- Confirm GitHub Pages serves `index.html`, `install.html`, `readme.html`, `todo.html`, and `changelist.html`.
- Confirm `gh skill preview CAST-docs/cast-a-doc cast-a-doc --pin "v$(cat VERSION)"` resolves.
- Install into a temporary directory and run `scripts/render_example.sh examples/problem-investigation.json out.html`.
