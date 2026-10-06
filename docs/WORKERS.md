# Supervised discovery worker

`discover-worker` runs one persistent public discovery pass. It is designed to
be invoked by a systemd timer rather than kept alive as an unbounded process.
Each invocation:

- exits immediately when the pause file exists;
- skips when another invocation holds the lock;
- fetches only explicitly configured public boards;
- persists discovery results but never submits an application;
- returns a compact JSON summary suitable for service logs.

Before fetching a source, the worker checks the exact Ollama endpoint and model
configured in `policy.yaml`. If Ollama is unavailable or the configured model
is missing, the worker exits closed and does not create a discovery backlog.
Backups, recovery checks, and status controls remain available during an
Ollama outage.

Install the unit files from `systemd/` into the user systemd directory, adjust
the working directory, virtual-environment path, and board arguments, then
enable the timer:

```bash
systemctl --user daemon-reload
systemctl --user enable --now job-engine-discovery.timer
```

The CLI provides explicit controls for the pause marker:

```bash
job-engine pause --pause-file /path/to/PAUSED
job-engine worker-status --pause-file /path/to/PAUSED
job-engine resume --pause-file /path/to/PAUSED
```

This stage does not yet enable model drafting or external ATS actions.

The deep-review scheduling helper uses the same lock and pause boundary. It
allows the large-context review task only during the configured
`deep_review` schedule window and only when the actionable queue is at or below
the configured threshold. It does not submit applications or bypass dashboard
approval.

The backup timer uses the same local control boundary and keeps the newest
fourteen verified database backups. Application evidence is not pruned by this
stage. A manual backup can be created with:

```bash
job-engine backup \
  --database /path/to/engine.sqlite3 \
  --backup-root /path/to/backups \
  --keep 14
```

Run the non-destructive recovery check before enabling unattended operation:

```bash
job-engine recovery-check \
  --database /path/to/engine.sqlite3 \
  --backup-root /path/to/backups \
  --pause-file /path/to/PAUSED
```
