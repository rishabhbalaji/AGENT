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

## Deep review window

The large-context review workload is separately gated by the schedule's
`deep_review` action. The example schedule permits it only from `00:00` to
`02:00` in `Europe/London`. The worker also requires the actionable queue to be
at or below `deep_review.max_actionable_queue_depth` (currently `0`), so deep
review cannot consume capacity while ordinary review work is waiting.

The deep-review model is configured separately as
`ollama.deep_review_model`. It is health-checked by exact model name before the
review task runs. Outside the window, while paused, with actionable work
present, or when Ollama is unavailable, the worker does not invoke the task.
