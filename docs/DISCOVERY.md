# Public discovery runner

`job_engine.discovery.discover` fetches one configured public source, normalizes
the postings, evaluates all enabled profiles, and assigns a deterministic
status:

- `drafted` for a profile match;
- `parked` for a hard exclusion such as SC clearance or a company exclusion;
- `discovered` for a valid posting that does not yet meet a profile threshold.

The default is a dry run. Persistence requires an explicit database path and
`dry_run=False`. No model call or external application action occurs during
discovery.

The CLI exposes the same guarded flow for Greenhouse boards:

```bash
job-engine discover \
  --config-dir config/local \
  --database engine.sqlite3 \
  --board example-company
```

Add `--persist` only after reviewing the dry-run JSON. Repeat `--board` for
additional explicitly allowlisted public boards. Board slugs are not guessed
by the engine.

The orchestration layer also supports multiple source adapters in one pass.
Sources are evaluated sequentially, a failed source does not stop the others,
and stable duplicate postings are retained once. Source health remains
available per adapter for later scheduling and monitoring.
