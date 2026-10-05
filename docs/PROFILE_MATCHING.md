# Profile matching

`job_engine.matching.match_profile` evaluates a normalized posting against one
profile configuration. It applies:

- a fail-closed clearance exclusion gate before scoring;
- a company exclusion gate matching exact names, aliases, or source domains;
- included and excluded keyword terms;
- employment-type constraints;
- configured location substrings;
- configured remote modes;
- an optional `salary_gbp` metadata value and minimum salary;
- the profile score threshold.

The result includes a score, threshold, matched/excluded flags, reason codes,
and unknown fields. Missing source data is never silently treated as a match.
Matching is deterministic and does not call Ollama.

The default clearance exclusions are `SC`, `SC Clearance`, and `Security
Check`. They are searched as whole-word terms across the title, company,
description, requirements, and structured clearance requirements. Callers can
provide a different `clearance_exclusions` tuple when a future policy enables
additional clearance profiles.

Company exclusions are supplied as mappings with a canonical `name`, optional
`aliases`, optional `domains`, and a required explanatory `reason`. A matching
company is excluded before scoring and the reason is retained in the decision.
