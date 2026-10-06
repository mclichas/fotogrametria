# Validation And Linting

This guide covers schema validation and notebook-operational lint rules that support CI/CD for `.ipynb` workflows.

## When To Read This

Read this when building quality gates for notebooks in CI, pre-commit, or automated notebook pipelines.

## Schema Basics (nbformat v4)

A valid notebook needs:
- top-level `nbformat`, `nbformat_minor`, `metadata`, `cells`
- valid cell structures by `cell_type`
- valid output payload structure for code cells

Reference schema source: Jupyter `nbformat` and `jupyter/schema` repositories.

## Built-In Validation

`nbformat.validate()` checks structural compliance against schema.

```python
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)
nbformat.validate(nb)
```

What it catches well:
- missing required fields
- malformed output objects
- invalid cell structure

What it does not catch:
- project-specific hygiene rules
- workflow consistency expectations

## Operational Lint Rules (Recommended)

Keep rules focused on notebook integrity and automation safety:
- missing kernelspec metadata
- duplicate cell IDs
- empty source cells
- very long cells (maintainability)
- outputs present (optional pre-commit restriction)
- stale state patterns:
- `execution_count` set but outputs empty
- outputs present but `execution_count` null

Avoid generic Python style policy here; keep that in project lint tooling.

## Example Custom Rule Engine

```python
def lint_notebook(nb, forbid_outputs=False, max_lines=400):
    issues = []
    ids = set()

    if not nb.metadata.get("kernelspec", {}).get("name"):
        issues.append(("error", "Missing kernelspec.name", None))

    for i, cell in enumerate(nb.cells):
        cid = cell.get("id")
        if cid in ids:
            issues.append(("error", f"Duplicate cell id: {cid}", i))
        ids.add(cid)

        src = cell.get("source", "")
        if not src.strip():
            issues.append(("warning", "Empty cell source", i))

        if max_lines and len(src.splitlines()) > max_lines:
            issues.append(("warning", "Cell too long", i))

        if cell.get("cell_type") == "code":
            outs = cell.get("outputs", [])
            count = cell.get("execution_count")
            if count is not None and not outs:
                issues.append(("warning", "execution_count without outputs", i))
            if count is None and outs:
                issues.append(("warning", "outputs without execution_count", i))
            if forbid_outputs and outs:
                issues.append(("error", "Outputs are forbidden", i))

    return issues
```

## CI / Pre-Commit Integration

Typical policy:
- `exit 0`: no issues
- `exit 1`: issues found
- `exit 2`: runtime/tool failure

This distinction helps CI dashboards separate notebook quality failures from infrastructure failures.

## Common Notebook Anti-Patterns

- Hand-edited JSON that breaks schema
- Merge conflicts leaving duplicated IDs
- Large committed outputs bloating history
- Partially executed notebooks committed as final artifacts
