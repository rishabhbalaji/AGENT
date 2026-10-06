# Read-only MCP context layer

The context layer is a narrow local-provider boundary for model workflows. It
does not implement an MCP server transport or grant model workflows authority
over policy, database writes, ATS actions, browser sessions, or credentials.
A future MCP transport may call this provider, but it must preserve the same
allowlist.

## Allowlisted resources

- `jobs`: bounded job projections, ordered by fit score.
- `drafts`: only drafts that passed deterministic document gates.
- `email_status`: Gmail metadata without message bodies.
- `resume_evidence`: supplied provenance-bearing evidence chunks.
- `repository_evidence`: supplied provenance-bearing repository chunks.

SQLite is opened with `mode=ro`; callers provide a resource name and optional
identifier, never SQL. Limits are restricted to 1–100. Missing databases,
malformed evidence references, and unsupported resources fail closed.

Example:

```bash
job-engine context \
  --database runtime/engine.sqlite3 \
  --resource jobs \
  --limit 15
```

The Python engine remains authoritative. Context retrieval is informational and
cannot approve applications, alter job state, send mail, or bypass evidence
and document gates.
