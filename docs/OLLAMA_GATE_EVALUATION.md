# Model document-gate evaluation

`evaluate_model_draft` runs the fixture-only model drafting path and then the
existing deterministic document gates. It returns a serializable result with
the model name, digest, drafting status, gate status, repair count, and error.

The evaluator does not persist jobs or documents, update the dashboard, or
submit applications. A model draft with unsupported evidence fails before the
document gates run.
