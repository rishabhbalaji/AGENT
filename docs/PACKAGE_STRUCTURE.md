# Python package structure

The engine uses a `src/` layout so that tests import the installed package
rather than accidentally importing repository-root files:

```text
src/job_engine/
├── __init__.py
├── cli.py
└── logging.py
```

The package currently uses only the Python standard library. The console entry
point is:

```bash
job-engine --version
```

Configuration loading, storage initialization, scheduling, workers, and the
browser interface are intentionally deferred to later stages.

For development without installing the package, run tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```
