# Profile matching

`job_engine.matching.match_profile` evaluates a normalized posting against one
profile configuration. It applies:

- included and excluded keyword terms;
- employment-type constraints;
- configured location substrings;
- configured remote modes;
- an optional `salary_gbp` metadata value and minimum salary;
- the profile score threshold.

The result includes a score, threshold, matched/excluded flags, reason codes,
and unknown fields. Missing source data is never silently treated as a match.
Matching is deterministic and does not call Ollama.
