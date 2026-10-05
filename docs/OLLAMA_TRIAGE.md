# Fixture-only model triage

`job_engine.model_triage.triage_with_model` adds validated model observations
to an existing deterministic `TriageRecord`. It records the model digest and
prompt through `ModelProvenance`, but the deterministic route remains the
authoritative route.

The model cannot override clearance exclusions, company exclusions, profile
filters, approval requirements, or document gates. Invalid JSON, unsupported
fields, invalid types, unavailable models, and unsafe clearance routes fail
closed.

This stage is fixture-only. It does not write jobs, update applications, or
submit anything externally.
