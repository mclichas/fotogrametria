# Execution Guide

This guide explains which execution tool to use (`nbclient`, `nbconvert`, `papermill`, or direct `jupyter_client`) and how execution behaves in automated workflows.

## When To Read This

Read this before implementing notebook execution automation, especially for timeout, kernel selection, selective cell range runs, or parameterized runs.

## Decision Tree

- Need to run a notebook only:
- Use `nbclient` (`scripts/nb_execute.py` default mode).
- Need run + export in one step:
- Use `nbconvert --execute` path (`scripts/nb_convert.py --execute`).
- Need parameter injection + run:
- Use papermill mode (`scripts/nb_execute.py --papermill`).
- Need low-level interactive kernel messaging:
- Use `jupyter_client` directly (advanced pattern).

## How nbclient Works

`nbclient`:
- starts a kernel,
- sends code cells in order,
- captures outputs/errors back into notebook cells,
- shuts down kernel when done.

```python
import nbformat
from nbclient import NotebookClient

nb = nbformat.read("in.ipynb", as_version=4)
client = NotebookClient(nb, timeout=300, startup_timeout=60, allow_errors=False)
executed = client.execute()
nbformat.write(executed, "out.ipynb")
```

## Selective Cell-Range Execution (Cornerstone Pattern)

For stable automation, execute prefix `0..end` to preserve state, then write back only target range.

```python
import copy
import nbformat
from nbclient import NotebookClient

nb = nbformat.read("in.ipynb", as_version=4)
start, end = 3, 7

prefix = copy.deepcopy(nb)
prefix.cells = copy.deepcopy(nb.cells[: end + 1])
NotebookClient(prefix, timeout=300).execute()

result = copy.deepcopy(nb)
for i in range(start, end + 1):
    result.cells[i] = copy.deepcopy(prefix.cells[i])

nbformat.write(result, "out.ipynb")
```

Why this works:
- Cells `start..end` can depend on variables from earlier cells.
- Only target cells are updated, so unrelated output noise is minimized.

## Timeout Strategy

Use first-class per-cell timeout only:
- `timeout` controls per-cell runtime limit.
- `startup_timeout` controls kernel startup wait.

On timeout, execution raises and notebook may be partially updated.

## Error Handling (`allow_errors`)

- `allow_errors=False` (default): raises on first failure.
- `allow_errors=True`: continues execution; errors are recorded in output cells.

```python
for i, cell in enumerate(nb.cells):
    if cell.cell_type != "code":
        continue
    for out in cell.get("outputs", []):
        if out.get("output_type") == "error":
            print("failed", i, out.get("ename"), out.get("evalue"))
```

## Kernel Selection

- Preferred: kernel name from `jupyter kernelspec list`.
- Notebook metadata `kernelspec.name` can define default kernel.
- CLI kernel argument should override notebook metadata when needed.

## Resource Cleanup

Always rely on the client lifecycle (or context managers) so kernels are shut down on errors. Avoid custom long-lived kernel processes unless you need direct messaging control.

## jupyter_client Advanced Pattern (Direct Control)

Use only when you need cell-by-cell streaming or custom message handling.

```python
from jupyter_client import KernelManager

km = KernelManager(kernel_name="python3")
km.start_kernel()
try:
    kc = km.client()
    kc.start_channels()
    kc.execute("x = 1; print(x)")
finally:
    km.shutdown_kernel(now=True)
```
