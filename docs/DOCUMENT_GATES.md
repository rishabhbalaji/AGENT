# Deterministic document gates

`job_engine.document_gates.run_document_gates` checks a generated packet
without changing it. The gates verify:

- every required document type is present exactly once;
- every document has non-empty content;
- every document has evidence references;
- every referenced evidence chunk is known;
- placeholder markers such as `TODO`, `[insert`, and `lorem ipsum` are absent;
- ATS answers are not left at the empty-question default.

Failures produce `RepairQueueItem` records with a document type, gate name,
and explicit reason. A failed gate never becomes a success-shaped fallback and
does not automatically rewrite the draft. Repair or human approval is a
separate action.
