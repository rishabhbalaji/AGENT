# Local review dashboard

`job_engine.dashboard.create_dashboard_app` creates the first server-rendered
FastAPI review interface. It currently provides four read-only queues:

- `applied`
- `apply-yourself`
- `parked`
- `drafts`

The app accepts an in-memory queue snapshot so persistence wiring can be added
without coupling the first browser surface to an unfinished storage query
layer. Empty queues are shown explicitly. The dashboard does not submit
applications.

Run it locally with:

```bash
job-engine dashboard
```

For the integration tests, install the test extra:

```bash
python -m pip install -e ".[test]"
```

The default address is `http://127.0.0.1:8000`. This stage deliberately binds
only to loopback. Tailscale interface binding and access restriction are
implemented in M4P0S1; do not expose this development server publicly.
