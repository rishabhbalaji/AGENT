# Offline fixtures

The `fixtures/` directory contains fictional data for development and tests.
It must never contain the user's real resume, personal details, credentials,
live job postings, or authenticated source data.

- `persona.json` contains a fictional candidate and evidence claims.
- `postings.json` contains synthetic job postings. URLs use
  `example.invalid`, which is reserved for documentation and cannot be a live
  destination.
- `route_decisions.json` records expected shortlist or park outcomes. Fixture
  routes can require human approval, but must never submit an application.

Load and validate the complete set with:

```python
from pathlib import Path
from job_engine.fixtures import load_fixture_set

fixture_set = load_fixture_set(Path("fixtures"))
```
