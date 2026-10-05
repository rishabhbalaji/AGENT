# Local review dashboard

`job_engine.dashboard.create_dashboard_app` creates a server-rendered FastAPI
review interface with a responsive dark layout, queue navigation, item counts,
and explicit read-only safety messaging. It currently provides four read-only
queues:

- `applied`
- `apply-yourself`
- `parked`
- `drafts`

The app accepts a queue snapshot, and `queues_from_database` loads that
snapshot read-only from SQLite. Job statuses map to queues as follows:

- `applied` → Applied
- `apply_yourself` and `shortlisted` → Apply yourself
- `parked` and `rejected` → Parked
- `drafted` → Drafts

Application records also contribute to the queues: submitted/applied
applications appear under Applied, `review` routes under Apply yourself,
`park` routes under Parked, and `draft_for_approval` or drafted applications
under Drafts. A job is displayed at most once per queue.

Empty queues are shown explicitly. The dashboard does not submit applications.

Queue cards provide explicit review actions:

- **Drafts** show **Approve**, **Edit**, **Park**, **Reject**, and **Export**.
- **Apply yourself** shows **Mark applied**, **Park**, **Reject**, and
  **Export**.
- **Parked** shows **Approve**, **Edit**, **Reject**, and **Export**.
- **Applied** is read-only and shows **Export** only.

Approve moves a job to `apply_yourself`; it does not submit anything. Park and
Reject move jobs to their corresponding local states. Mark applied records the
local `applied` status after the user applies externally. Export downloads a
plain-text local review bundle. Edit changes only the local title and summary
and records an event.

Mutating actions use POST requests and every status or edit is recorded in the
SQLite `events` table. The dashboard refreshes its queue snapshot after each
successful action.

Run it locally with:

```bash
job-engine dashboard --database /path/to/engine.sqlite3
```

The dashboard does not invent or fetch jobs. For a safe manual walkthrough,
seed the validated fictional fixtures into a separate local database:

```bash
job-engine demo-data --database demo-engine.sqlite3
job-engine dashboard --database demo-engine.sqlite3
```

The command is idempotent and only accepts the repository's
`example.invalid` fixture URLs. It never creates live postings or submits an
application.

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
