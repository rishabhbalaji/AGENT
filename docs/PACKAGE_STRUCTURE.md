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
├── resume.py
├── github_index.py
├── evidence.py
├── claims.py
├── triage.py
├── model_output.py
├── documents.py
├── document_gates.py
├── dashboard.py
├── storage_check.py
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

`job_engine.resume.import_pdf` extracts text from a local PDF master resume
and records its source path, page count, and content hash. Resume files remain
ignored by Git and are not copied into the repository.

`job_engine.github_index.GitHubRepositoryIndexer` inventories only explicitly
allowlisted public GitHub repositories using read-only API requests. It stores
file metadata, not repository clones or credentials.

`job_engine.evidence` creates stable, traceable chunks from the local resume
and indexed public repository text files. Each chunk retains source identity,
revision/hash information, and a content hash.

`job_engine.claims.validate_claims` rejects generated claims without evidence
references or with unknown/repeated chunk IDs before application material is
accepted.

`job_engine.triage.triage_posting` extracts structured review fields and maps
existing deterministic match decisions to non-submitting review routes.

`job_engine.model_output` validates closed JSON schemas and preserves model
prompt, version, revision, and timestamp provenance for future model-assisted
features.

`job_engine.documents.generate_tailored_documents` creates local,
evidence-backed text drafts for resumes, cover letters, ATS answers, and
LinkedIn messages without submitting anything.

`job_engine.document_gates.run_document_gates` checks packet structure,
evidence references, and placeholder/ATS safety, returning explicit repair
queue items without mutating the drafts.

`job_engine.dashboard.create_dashboard_app` provides the local, server-rendered
review queue interface. `queues_from_database` reads persisted SQLite jobs
into the queues without mutating or submitting anything.

`job_engine.storage_check` contains the installed-package storage validation
used by the CLI and health checks; the legacy `scripts/storage_check.py` module
remains available for direct script and test compatibility.

Offline fictional development data is loaded and validated by
`job_engine.fixtures.load_fixture_set`. The fixture contract is documented in
`docs/FIXTURES.md`.

For development without installing the package, run tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_*.py'
```
