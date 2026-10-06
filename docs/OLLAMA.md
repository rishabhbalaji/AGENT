# Ollama connectivity

The engine can verify and query one explicitly configured Ollama model through a
Tailscale-reachable HTTP endpoint. It never selects a fallback model.

## Engine availability policy

The unattended engine is configured to require the Ollama endpoint and the
selected model. If either is unavailable, the engine must fail closed rather
than continue discovering jobs and create a backlog for later inference.
Existing database records, drafts, and backups remain unchanged.

The current local selection is:

```yaml
ollama:
  required_for_engine: true
  endpoint: http://100.93.206.16:11434
  model: qwen3:14b-16k
```

This is private local configuration and is not committed to Git.

## Health check

```bash
job-engine ollama-health \
  --endpoint http://100.64.0.10:11434 \
  --model qwen2.5:7b
```

The command succeeds only when Ollama responds with a model whose name exactly
matches `--model`. It reports the model digest and modification time so the
selected model can be recorded before inference is enabled.

## Safety boundary

This stage only adds connectivity and non-streaming JSON transport. It does not
replace deterministic matching, clearance exclusions, company exclusions,
document gates, or human approval. Timeouts, unavailable endpoints, unavailable
models, malformed JSON, and empty responses fail closed as errors.
