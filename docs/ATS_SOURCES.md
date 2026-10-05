# ATS source contract

Public source adapters implement `job_engine.ats.SourceAdapter`. The contract
is intentionally limited to unauthenticated fetching and normalization:

- `NormalizedPosting` contains stable source identity, public URL, job content,
  optional dates, requirements, clearance requirements, and source metadata.
- `SourceFetchResult` returns postings together with the time of the fetch.
- `SourceHealth` records whether the source was healthy, degraded, unavailable,
  or disabled.
- `RateLimit` lets the scheduler enforce the source's request budget.

Adapters must not require cookies, browser sessions, login credentials, or
account creation. They must return timezone-aware timestamps and preserve the
original public source URL.

The first adapter is `job_engine.greenhouse.GreenhouseAdapter`. It reads the
public Greenhouse boards endpoint for a configured board slug and converts each
job into `NormalizedPosting`. Transport failures produce an explicit
`UNAVAILABLE` health result; they are never reported as a successful empty
fetch. Tests use `fixtures/greenhouse_jobs.json` and do not contact the live
network.

`job_engine.public_feed.GovUkFindAJobAdapter` provides the first public-feed
adapter. Its endpoint is explicitly injected because the engine must not guess
at an undocumented or changing endpoint. It accepts a normalized JSON feed
shape, preserves the source URL, and uses the same explicit health behavior.
Reed and Adzuna remain configuration- and credential-gated until their API
credentials and terms are deliberately enabled.
