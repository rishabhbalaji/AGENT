# Fixture-only model drafting

Model drafting is allowed to propose claims, ATS answers, and message text,
but the model cannot establish its own evidence. Every claim must reference a
known local evidence chunk and pass `validate_claims` before
`generate_tailored_documents` creates any draft.

Unknown evidence IDs, malformed nested fields, unavailable models, and invalid
responses fail closed. This stage creates no external submission and does not
write to the dashboard or application database.
