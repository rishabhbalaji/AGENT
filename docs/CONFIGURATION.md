# Configuration contract

This repository contains safe examples only. Real configuration belongs on the
SDA data root and must not be committed.

## Local layout

The current host uses the repository-local `runtime/` directory because the
root filesystem is `/dev/sda2`. It is ignored by Git and contains operational
state, while the private YAML preferences remain under `config/local/`:

```text
/home/rbk/projects/AGENT/
├── config/local/
│   ├── profiles.yaml
│   ├── schedule.yaml
│   ├── sources.yaml
│   ├── repositories.yaml
│   └── policy.yaml
└── runtime/
    ├── engine.sqlite3
    └── backups/
```

The example files under `config/examples/` are templates for that local
configuration. They do not enable live application submission, contain no
personal data, and contain no credentials.

The loader is available as `job_engine.config.load_config(path)`. It requires
all five YAML files, validates their version and required structures, and raises
an explicit configuration error before workers can start.

## Environment values

Copy `.env.example` to a local `.env` only when the application supports
environment loading. The local file must remain untracked. Production systemd
units should prefer systemd credentials or the future Vaultwarden adapter for
secrets.

Required values will eventually include:

- `ENGINE_DATA_ROOT`: the SDA-backed runtime data root
  (`/home/rbk/projects/AGENT/runtime` on this host).
- `ENGINE_BIND_HOST`: the server's Tailscale address.
- `ENGINE_BIND_PORT`: the local dashboard port.
- `OLLAMA_BASE_URL`: the Tailscale endpoint on `rbkmsi`.

The local policy requires the configured Ollama endpoint and model to be
available before unattended engine work runs. This prevents discovery from
outpacing model-assisted processing and creating an unbounded backlog.

The GitHub token, mail credentials, and vault credentials are intentionally
not configured in this stage.

See [SDA_STORAGE.md](./SDA_STORAGE.md) for the host-level storage contract.

## Configuration safety rules

1. Configuration must fail validation before workers start.
2. A missing, read-only, or non-SDA data root must stop startup.
3. LinkedIn and Indeed must remain unauthenticated discovery-only sources.
4. SC Clearance exclusions apply before model scoring.
5. Company exclusions apply before model scoring.
6. Fifteen suitable jobs is a discovery target, never a submission quota.
7. External ATS submission defaults to approval-required mode.
8. CAPTCHA, MFA, changed forms, unexpected pages, ambiguous questions, and
   unsupported account creation must be parked.
9. The dashboard must not bind to `0.0.0.0`.
10. Example configuration must never contain real tokens, passwords, resumes,
    job snapshots, or application history.
