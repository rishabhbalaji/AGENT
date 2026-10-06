# Agent Corner isolation

Agent Corner is a separate, non-production workspace for creative or
experimental local work. It does not share production job records, browser
sessions, credentials, or outbound application actions.

## Filesystem boundary

The production runtime is `runtime/`. Agent Corner uses the sibling
`agent-corner-runtime/` directory, which is ignored by Git. Its subdirectories
are created independently:

```text
agent-corner-runtime/
├── data/
├── credentials/
├── browser/
└── jobs/
```

The `credentials/` directory is reserved for future isolated credentials and
must never contain production secrets. The current check does not grant access
to any credential provider, browser automation, job database, or outbound
action API.

Validate and prepare the boundary with:

```bash
job-engine agent-corner-check \
  --root agent-corner-runtime \
  --production-root runtime
```

The command refuses an Agent Corner root inside the production runtime and
rejects artifact paths that attempt directory traversal. The systemd template
uses `ProtectSystem=strict`, `ProtectHome=read-only`, `PrivateTmp`, and
`PrivateDevices`, with write access limited to the isolated sibling root.
