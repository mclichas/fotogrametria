# Metadata Reference

This guide summarizes notebook-level and cell-level metadata used in programmatic notebook workflows.

## When To Read This

Read this when setting kernel metadata, managing tags, preparing papermill parameter cells, or configuring slide exports.

## Notebook-Level Metadata

Common keys:
- `kernelspec`
- `language_info`
- optional custom keys (`title`, `authors`, project-specific metadata)

Typical structure:

```json
{
  "kernelspec": {
    "name": "python3",
    "display_name": "Python 3",
    "language": "python"
  },
  "language_info": {
    "name": "python",
    "version": "3.11"
  },
  "title": "Quarterly Analysis"
}
```

## Cell-Level Metadata

Common keys:
- `tags`: `[]`
- `collapsed`: output collapsed hint
- `scrolled`: output scroll hint
- `slideshow`: reveal.js mapping
- `name`: optional human label
- custom workflow keys

Example:

```json
{
  "tags": ["parameters", "etl"],
  "slideshow": {"slide_type": "slide"}
}
```

## Execution Count Semantics

For code cells:
- `execution_count: null` means never executed (or cleared)
- `execution_count: <int>` means execution order in a prior run

Execution count alone does not guarantee outputs are consistent.

## Papermill Tag Usage

Papermill convention:
- tag parameter definition cell with `parameters`

```python
cell = nb.cells[1]
cell.metadata.setdefault("tags", [])
if "parameters" not in cell.metadata["tags"]:
    cell.metadata["tags"].append("parameters")
```

## nbconvert Slide Metadata

For reveal.js slides, use `slideshow.slide_type`:
- `slide`
- `subslide`
- `fragment`
- `skip`
- `notes`

```python
cell.metadata["slideshow"] = {"slide_type": "subslide"}
```

## API Examples

```python
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)

# notebook metadata
nb.metadata["title"] = "EDA v2"
nb.metadata.setdefault("kernelspec", {})["name"] = "python3"

# cell metadata
nb.cells[0].metadata.setdefault("tags", []).append("intro")

nbformat.write(nb, "notebook.ipynb")
```
