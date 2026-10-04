# Python package structure

The engine uses a `src/` layout so that tests import the installed package
rather than accidentally importing repository-root files:

```text
src/job_engine/
├── __init__.py
├── cli.py
├── config.py
└── logging.py
```

The package currently uses only the Python standard library. The console entry
point is:

```bash
job-engine --version
```

Configuration loading, storage initialization, scheduling, workers, and the
browser interface are intentionally deferred to later stages.

Operating-mode resolution is provided by `job_engine.modes.resolve_mode`.
It uses `Europe/London` schedule time, supports midnight-spanning windows,
unions actions from overlapping windows, and fails closed for invalid schedule
values.

For development without installing the package, run tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```
