# Error Handling

This guide covers execution failure behavior and resilient handling patterns for notebook automation with `nbclient` and related tools.

## When To Read This

Read this when execution failures, timeouts, or kernel crashes need to be handled predictably in CLI or CI workflows.

## Cell Failure Behavior

When a cell raises:
- with `allow_errors=False`, execution stops and raises.
- with `allow_errors=True`, execution continues and failure is captured as an `error` output.

Error output structure includes:
- `ename`
- `evalue`
- `traceback` (list of lines)

## `allow_errors` Pattern

```python
from nbclient import NotebookClient

client = NotebookClient(nb, timeout=300, allow_errors=True)
client.execute()

failed = []
for i, cell in enumerate(nb.cells):
    if cell.cell_type != "code":
        continue
    for out in cell.get("outputs", []):
        if out.get("output_type") == "error":
            failed.append((i, out.get("ename"), out.get("evalue")))
```

## Timeout Behavior

Use per-cell timeout (`timeout`) and startup timeout (`startup_timeout`).

If a timeout occurs:
- execution raises
- notebook may be partially executed
- kernel may require restart on subsequent attempts

## Kernel Crash Cases

Common causes:
- out-of-memory
- native extension crash
- invalid environment/kernel mismatch

Detection signals:
- execution exception from client
- missing expected outputs after partial run

Recovery pattern:
- treat run as failed,
- persist partial notebook for debugging,
- retry in clean kernel/environment.

## Common Execution Errors

- `ModuleNotFoundError`: package missing in kernel env
- `MemoryError`: workload too large
- kernel died: process crash or forced termination

## Graceful Cleanup Pattern

Always ensure kernel shutdown even on exceptions.

```python
from nbclient import NotebookClient

client = NotebookClient(nb, timeout=300)
try:
    client.execute()
finally:
    # NotebookClient handles cleanup internally, but keep this pattern
    # when managing lower-level kernel clients manually.
    pass
```

## Report Failures Deterministically

Recommended result payload for automation:
- run status (`ok`)
- failed cell indexes
- exception summaries
- output notebook path (even on partial execution if available)

This keeps CI and agent retries deterministic and debuggable.
