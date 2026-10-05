# Python package structure

The engine uses a `src/` layout so that tests import the installed package
rather than accidentally importing repository-root files:

```text
src/job_engine/
├── __init__.py
├── cli.py
├── config.py
├── ats.py
├── aggregator.py
├── database.py
├── fixtures.py
├── greenhouse.py
├── matching.py
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

Public job-source adapters implement the contracts in `job_engine.ats`.
`NormalizedPosting` keeps source-specific responses out of the rest of the
engine, while `SourceHealth` and `RateLimit` provide fetch observability and
scheduling metadata.

`job_engine.greenhouse.GreenhouseAdapter` is the first concrete adapter. It
fetches public Greenhouse board listings and reports explicit source health.
`job_engine.public_feed.GovUkFindAJobAdapter` adds the first configurable
public-feed integration without embedding credentials or undocumented URLs.
`job_engine.aggregator.GuestAggregatorAdapter` is a disabled-by-default,
allowlist-gated contract for any future guest/public aggregator.

`job_engine.normalization` canonicalizes source URLs, derives stable posting
identities, preserves raw snapshots, computes expiration state, and marks
duplicate fetches as repost signals before policy filtering.

`job_engine.matching` applies enabled profile rules deterministically and
returns explainable scores, exclusions, and unknown input fields without an
LLM.

Offline fictional development data is loaded and validated by
`job_engine.fixtures.load_fixture_set`. The fixture contract is documented in
`docs/FIXTURES.md`.

For development without installing the package, run tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```
