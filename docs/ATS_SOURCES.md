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
The CLI includes it in a discovery pass with
`--govuk-endpoint <https-url>` alongside repeated `--board` arguments. The
endpoint must be operator-supplied and return the fixture-compatible
`{"jobs": [...]}` shape; no login, cookies, or API secret is used. The same
option is available to `discover-worker`.
Reed and Adzuna remain configuration- and credential-gated until their API
credentials and terms are deliberately enabled.

`job_engine.aggregator.GuestAggregatorAdapter` is disabled by default. To
enable a guest feed, an operator must explicitly provide its host in an
allowlist and inject a public transport. The adapter sends no credentials,
cookies, or browser state. It reports `DISABLED` when policy prevents access
and `UNAVAILABLE` when an approved transport fails. No real aggregator is
selected by this stage; the fixture uses `example.invalid`.
## Offline application-form fixtures

Before using any live ATS page, form behavior is tested against local fixtures.
The first fixture is
`fixtures/greenhouse_application_form.json`, which models a small Greenhouse
form using only an `example.invalid` URL.

`job_engine.ats_fixtures.load_form_fixture` validates supported field types,
required fields, select options, unique field names, and fixture-only URLs.
`ATSFormFixture.validate_answers` validates a prepared answer set locally.
Fixtures explicitly default to `supports_submission: false`; this stage does
not open a browser, authenticate, upload a resume, or submit an application.
