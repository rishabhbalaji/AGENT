# Tailored document drafts

`job_engine.documents.generate_tailored_documents` creates a local review
packet containing text drafts for:

- a tailored resume;
- a cover letter;
- supplied ATS question answers;
- a LinkedIn message draft.

Every draft carries the evidence chunk IDs from the validated claims used to
create it. Callers must pass claims returned by
`job_engine.claims.validate_claims`; unsupported or unvalidated claims cannot
be used to generate a packet.

The generator is intentionally local and non-submitting. It does not contact
LinkedIn, an ATS, a model, or any other network service. It produces text
only. PDF/DOCX rendering, fact gates, and repair queues are separate later
stages.
