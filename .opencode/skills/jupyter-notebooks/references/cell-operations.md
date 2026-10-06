# Cell Operations

This guide explains how notebook cells are represented in `nbformat` and how to perform reliable CRUD operations directly on `.ipynb` files.

## When To Read This

Read this when building or modifying cell-level automation: add/update/delete/reorder cells, manipulate cell metadata, manage tags, and inspect outputs.

## Cell Data Model (nbformat v4)

Each cell has:
- `cell_type`: `"code"`, `"markdown"`, or `"raw"`
- `source`: string content
- `metadata`: free-form JSON object
- Code-cell only:
- `execution_count`: `null` or integer
- `outputs`: list of output objects

```python
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)
nbformat.validate(nb)

for i, cell in enumerate(nb.cells):
    print(i, cell.cell_type, cell.get("id"), len(cell.source))
```

## Create And Insert Cells

```python
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)

new_code = nbformat.v4.new_code_cell("import pandas as pd")
new_markdown = nbformat.v4.new_markdown_cell("## Notes")

nb.cells.insert(0, new_markdown)
nb.cells.append(new_code)

nbformat.write(nb, "notebook.ipynb")
```

## Replace A Cell

```python
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)
idx = 3
old = nb.cells[idx]

replacement = nbformat.v4.new_code_cell("print('updated')")
replacement.metadata = old.metadata

nb.cells[idx] = replacement
nbformat.write(nb, "notebook.ipynb")
```

## Delete And Move Cells

```python
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)

del nb.cells[2]                 # delete
cell = nb.cells.pop(4)          # remove from old index
nb.cells.insert(1, cell)        # move to new index

nbformat.write(nb, "notebook.ipynb")
```

## Bulk Insert / Delete Range

```python
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)

batch = [
    nbformat.v4.new_markdown_cell("## Step A"),
    nbformat.v4.new_code_cell("x = 1"),
]
nb.cells[5:5] = batch  # insert at position 5

del nb.cells[8:11]     # delete range [8, 10]

nbformat.write(nb, "notebook.ipynb")
```

## Search Cell Source (Regex)

```python
import re
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)
pattern = re.compile(r"read_csv\(")

hits = [i for i, c in enumerate(nb.cells) if pattern.search(c.source)]
print(hits)
```

## Cell Metadata Patterns

Common metadata keys you may encounter:
- `tags`: list of strings
- `collapsed`: bool (legacy UI hint)
- `scrolled`: bool/"auto" for output area
- `slideshow`: `{ "slide_type": "slide|subslide|fragment|skip|notes" }`

```python
cell = nb.cells[2]
cell.metadata.setdefault("tags", [])
if "parameters" not in cell.metadata["tags"]:
    cell.metadata["tags"].append("parameters")
```

Papermill convention:
- A code cell tagged `parameters` is used as the parameter definition anchor.

## Output Structure (Code Cells)

Output objects in `cell.outputs` use `output_type`:
- `stream`: stdout/stderr text
- `execute_result`: execution result + MIME bundle
- `display_data`: rich display output + MIME bundle
- `error`: traceback info (`ename`, `evalue`, `traceback`)

```python
for out in nb.cells[4].get("outputs", []):
    ot = out.get("output_type")
    if ot in {"display_data", "execute_result"}:
        print(out.get("data", {}).keys())
    elif ot == "stream":
        print(out.get("name"), out.get("text"))
    elif ot == "error":
        print(out.get("ename"), out.get("evalue"))
```

## Recommended Safety Checks

- Validate after load: `nbformat.validate(nb)`
- Enforce index bounds before write
- Keep operations deterministic (avoid implicit reorder)
- Preserve metadata unless replacing by design
