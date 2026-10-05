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

The default address is `http://127.0.0.1:8000`. To make it reachable from
your tailnet, provide the machine's Tailscale IPv4 address:

```bash
job-engine dashboard --host 100.x.y.z --port 8000
```

The CLI accepts only loopback addresses or Tailscale's `100.64.0.0/10`
address range. Wildcard addresses such as `0.0.0.0`, LAN addresses, public
addresses, and hostnames are rejected. Binding to a Tailscale address is the
access restriction for this stage; Tailscale ACLs remain responsible for
tailnet authentication.
