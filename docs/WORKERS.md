# Supervised discovery worker

`discover-worker` runs one persistent public discovery pass. It is designed to
be invoked by a systemd timer rather than kept alive as an unbounded process.
Each invocation:

- exits immediately when the pause file exists;
- skips when another invocation holds the lock;
- fetches only explicitly configured public boards;
- persists discovery results but never submits an application;
- returns a compact JSON summary suitable for service logs.

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
