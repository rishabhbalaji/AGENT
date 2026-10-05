# Ollama model benchmark

The benchmark sends two fictional postings to each explicitly selected model:

- a junior Python role that should be reviewable or draftable;
- a Python role requiring SC Clearance that must be parked.

Each response must be closed JSON with exactly the fields `role`, `seniority`,
`sponsorship`, `clearance_required`, and `route`. The benchmark records model
digest, status, schema validity, route, and latency. A failed health check or
malformed response produces a failed result; it never falls back to another
model.

Run it locally:

```bash
job-engine ollama-benchmark \
  --endpoint http://100.93.206.16:11434 \
  --model qwen3:14b-16k \
  --model qwen3-coder:30b-16k \
  --model gemma4:31b \
  --model qwen3-coder-64k:latest \
  --output ollama-benchmark.json
```

This is an evaluation command only. It does not write jobs, update SQLite,
change deterministic matching, create application drafts, or submit anything.
