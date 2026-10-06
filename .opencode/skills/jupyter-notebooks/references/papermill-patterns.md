# Papermill Patterns

This guide explains parameterized notebook execution workflows with papermill, including template conventions and batch-run patterns.

## When To Read This

Read this when the same notebook needs to run across many parameter sets (tickers, dates, regions, model configs) while preserving immutable input templates.

## Core Model

Papermill:
- reads input notebook,
- injects parameters,
- executes,
- writes to a separate output notebook.

Input notebook is never mutated by default workflow.

## Parameter Cell Convention

Use one code cell tagged `parameters`:

```python
# in notebook cell tagged with metadata.tags = ["parameters"]
ticker = "AAPL"
lookback = 30
```

Papermill overrides these values at runtime.

## CLI Pattern

```bash
papermill input.ipynb output.ipynb -p ticker MSFT -p lookback 90
```

JSON-style from agent scripts:

```bash
uv run scripts/nb_execute.py \
  --input templates/parameterised.ipynb \
  --output runs/msft.ipynb \
  --papermill \
  --params '{"ticker":"MSFT","lookback":90}'
```

## Template Design Rules

- Keep parameter cell near top.
- Keep defaults runnable.
- Make parameter names stable and explicit.
- Avoid hidden side effects in parameter cell.

## Batch Execution Pattern

```python
import papermill as pm

jobs = [
    {"ticker": "AAPL", "lookback": 30},
    {"ticker": "MSFT", "lookback": 60},
]

for job in jobs:
    out = f"runs/{job['ticker']}-{job['lookback']}.ipynb"
    pm.execute_notebook("template.ipynb", out, parameters=job)
```

## Storage Backends

Papermill can operate on local and cloud paths (e.g., S3/GCS) when environment credentials and filesystem integrations are configured.

## Execution Metadata

Papermill writes metadata about:
- parameters used
- per-cell timing
- execution state

You can inspect this in notebook metadata for auditability and debugging.

## Failure Handling

- Keep one output notebook per run.
- On failure, preserve output notebook for traceback analysis.
- Combine with `allow_errors`-style post-processing only when partial runs are acceptable.
