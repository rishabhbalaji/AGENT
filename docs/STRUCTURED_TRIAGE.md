# Structured triage

`job_engine.triage.triage_posting` converts a normalized posting and its
deterministic `MatchDecision` into a review-ready `TriageRecord`.

The record preserves:

- role and source identity;
- salary value and source salary text;
- location, sponsorship, seniority, and work mode;
- the existing fit score, reasons, and unknown fields;
- a safe review route.

Routes are deliberately non-submitting:

- `draft_for_approval` for profile matches;
- `review` for postings below threshold without an exclusion;
- `park` for excluded postings.

Matched and below-threshold postings require human approval. Excluded postings
are parked automatically. Missing salary, sponsorship, seniority, work mode,
or location data is recorded as an explicit unknown rather than treated as a
positive match.

Optional metadata keys are `role`, `location`, `salary_gbp`, `salary_text`,
`salary_range`, `salary`, `sponsorship`, `seniority`, and `work_mode`.
Otherwise the extractor uses the normalized title, description, location, and
remote mode with deterministic text rules.
