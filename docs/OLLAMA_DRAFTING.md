# Model-assisted drafting

Model drafting is allowed to propose claims, ATS answers, and message text,
but the model cannot establish its own evidence. Every claim must reference a
known local evidence chunk and pass `validate_claims` before
`generate_tailored_documents` creates any draft.

Unknown evidence IDs, malformed nested fields, unavailable models, and invalid
responses fail closed. This stage creates no external submission and does not
write an external application action.

`job_engine.drafting_worker` selects the highest-scoring suitable jobs with a
stable tie-breaker and caps each pass at 15 jobs. Technical postings are
routed to the configured technical workload when available; other postings use
the routine workload. The worker checks model availability before processing
the selected batch, so an Ollama outage stops the batch instead of creating a
backlog.

Successful local drafts and deterministic gate failures are persisted in the
SQLite `drafts` and `repair_queue` tables. Persisting a draft does not change
the approval-required application route or submit anything externally.
