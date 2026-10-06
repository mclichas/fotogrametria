# Output Handling

This guide covers output inspection, stripping, sizing, and extraction patterns for notebook outputs.

## When To Read This

Read this when notebooks become large, noisy in git, or when you need to extract artifacts (images, tables, logs) from outputs.

## Output Types

Code-cell outputs include:
- `stream`: text from stdout/stderr
- `execute_result`: expression result with MIME bundle
- `display_data`: rich display bundle (plots, HTML, JSON)
- `error`: exception payload with traceback

## MIME Bundle Basics

Rich outputs use `output.data` maps, e.g.:
- `text/plain`
- `text/html`
- `application/json`
- `image/png`
- `image/svg+xml`

`image/png` is typically base64-encoded.

## Strip Outputs (All Cells)

```python
import nbformat

nb = nbformat.read("notebook.ipynb", as_version=4)
for cell in nb.cells:
    if cell.cell_type == "code":
        cell.outputs = []
        cell.execution_count = None
nbformat.write(nb, "notebook.clean.ipynb")
```

## Strip Outputs (Selected Cells)

```python
indexes = {2, 5, 7}
for i, cell in enumerate(nb.cells):
    if i in indexes and cell.cell_type == "code":
        cell.outputs = []
```

## Estimate Output Size

```python
def output_size_bytes(output):
    if output.get("output_type") == "stream":
        txt = output.get("text", "")
        if isinstance(txt, list):
            txt = "".join(txt)
        return len(str(txt).encode("utf-8"))
    if output.get("output_type") in {"display_data", "execute_result"}:
        total = 0
        for v in output.get("data", {}).values():
            if isinstance(v, list):
                v = "".join(v)
            total += len(str(v).encode("utf-8"))
        return total
    if output.get("output_type") == "error":
        tb = "\n".join(output.get("traceback", []))
        return len(tb.encode("utf-8"))
    return 0
```

## Extract Images From Outputs

```python
import base64
from pathlib import Path

out_dir = Path("images")
out_dir.mkdir(exist_ok=True)

for ci, cell in enumerate(nb.cells):
    if cell.cell_type != "code":
        continue
    for oi, out in enumerate(cell.get("outputs", [])):
        data = out.get("data", {})
        if "image/png" in data:
            raw = data["image/png"]
            if isinstance(raw, list):
                raw = "".join(raw)
            (out_dir / f"cell_{ci}_out_{oi}.png").write_bytes(base64.b64decode(raw))
```

## Outputs In Git: Practical Strategy

- Strip before commit (`nbstripout` / script).
- Keep execution artifacts in generated reports or artifact storage.
- Use nbdime to review source changes when outputs are retained.

## nbstripout Quick Setup

```bash
pip install nbstripout
nbstripout --install
```

Optional per-repo filter config can be committed via `.gitattributes`.
