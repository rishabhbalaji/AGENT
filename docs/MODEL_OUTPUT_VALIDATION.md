# Model-output validation

`job_engine.model_output` provides a strict boundary for future model-assisted
features. Model responses must be JSON objects with an explicitly declared
closed schema:

- `schema_name` identifies the output contract;
- `schema_version` identifies the contract revision;
- `required_fields` must be present;
- fields outside `allowed_fields` are rejected;
- malformed JSON and non-object JSON are rejected.

Every accepted result carries `ModelProvenance`, including the exact prompt,
model name, model version, revision identifier, and timezone-aware creation
time. The validator does not call a model or silently repair malformed output.
Callers must decide whether to retry, queue a repair, or request human review.

This stage validates structure and records provenance only. It does not claim
that generated text is factually supported; `job_engine.claims` remains the
evidence-reference gate for factual application material.
