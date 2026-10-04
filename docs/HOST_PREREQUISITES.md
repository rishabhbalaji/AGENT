# Host prerequisite verification

The engine expects the following capabilities on `rbkasus`:

- Python 3.12 or newer
- `systemctl` for production supervision
- `findmnt` for SDA mount validation
- Tailscale for access to the dashboard and remote Ollama
- `tectonic` or `pdflatex` for local PDF rendering
- Reachability to the configured Ollama endpoint on `rbkmsi`

Run the non-mutating checker with:

```bash
python3 scripts/host_prerequisites.py
```

To test Ollama reachability explicitly:

```bash
python3 scripts/host_prerequisites.py \
  --ollama-url http://<rbkmsi-tailscale-ip>:11434
```

The checker reports every prerequisite and returns exit code `1` if any
required check fails. It does not install packages, start or stop services,
change mounts, or download models. Ollama is not contacted unless
`--ollama-url` is supplied.

This stage reports the current host state only. Remediation commands and
service installation belong in host-specific operational documentation and
must be reviewed before execution.
