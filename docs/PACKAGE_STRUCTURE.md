# Python package structure

The engine uses a `src/` layout so that tests import the installed package
rather than accidentally importing repository-root files:

```text
src/job_engine/
├── __init__.py
├── cli.py
├── config.py
├── database.py
├── health.py
├── logging.py
└── modes.py
```

The package uses PyYAML for configuration parsing and otherwise relies on the
Python standard library. The console entry point is:

```bash
job-engine --version
```

Configuration loading, storage validation, scheduling, workers, and the
browser interface are implemented in separate stages.

Operating-mode resolution is provided by `job_engine.modes.resolve_mode`.
It uses `Europe/London` schedule time, supports midnight-spanning windows,
unions actions from overlapping windows, and fails closed for invalid schedule
values.

SQLite initialization is provided by `job_engine.database.migrate`. It creates
the initial jobs, applications, events, and migration-tracking tables and is
safe to call repeatedly.

The dry-run `job-engine health` command is provided by `job_engine.health`. It
loads and validates configuration, checks the SDA-backed data root, resolves
the current operating mode, and records one local health event.

For development without installing the package, run tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```
