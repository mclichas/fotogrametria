# Versioning Guide

This guide describes practical notebook version-control workflows using `nbdime` for content-aware diff/merge and `nbstripout` for output hygiene.

## When To Read This

Read this when integrating notebooks with git, setting up clean diffs, and reducing merge pain in collaborative notebook workflows.

## Why Plain `git diff` Is Poor For Notebooks

Notebook files are JSON bundles with large transient sections:
- output blobs
- base64 image payloads
- execution counters

Raw text diff is noisy and often hides real source changes.

## nbdime Setup

Install and configure:

```bash
pip install nbdime
nbdime config-git --enable
```

You can then use:

```bash
nbdiff notebook_a.ipynb notebook_b.ipynb
nbmerge base.ipynb local.ipynb remote.ipynb --out merged.ipynb
```

## Git Integration (`.gitattributes`)

Use an attributes file for notebook diff/merge drivers:

```gitattributes
*.ipynb diff=jupyternotebook
*.ipynb merge=jupyternotebook
```

An example is bundled in `assets/.gitattributes.example`.

## nbstripout Setup

`nbstripout` removes outputs on commit or via filters.

```bash
pip install nbstripout
nbstripout --install
```

For repo-local install:

```bash
nbstripout --install --attributes .gitattributes
```

## Recommended Combined Workflow

- Use `nbstripout` to keep committed notebooks lightweight.
- Use `nbdime` for meaningful source-aware diff/merge.
- Keep generated reports (HTML/PDF) outside notebooks when possible.

## Merge Strategy Guidance

If conflicts occur:
- Prefer content-aware merge (`nbmerge`) over manual JSON edits.
- For hard conflicts, resolve at source-cell level then re-run notebook.
- In automation, choose explicit strategy (`inline`, `use-local`, `use-remote`) and surface conflict counts.

## Notebook Naming Convention (CCDS-style)

Use ordered, owner-attributed names to simplify history scanning.

Pattern:
- `<step>-<owner>-<description>.ipynb`

Examples:
- `0.3-mmk-initial-eda.ipynb`
- `1.0-mmk-feature-drift-review.ipynb`

This mirrors cookiecutter-data-science guidance for reproducible notebook organization.
