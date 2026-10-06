# n8n evaluation

M5P1S2 evaluates n8n as an optional control-plane component. The evaluation
does not install or start n8n because the repository currently has no measured
operational friction that justifies another long-running service.

## Decision

n8n remains disabled by default:

```yaml
n8n:
  enabled: false
  dashboard_only: true
  owns_business_logic: false
  owns_irreplaceable_state: false
  owns_credentials: false
  owns_outbound_actions: false
```

The Python engine remains authoritative for scheduling, policy, matching,
evidence, drafts, SQLite state, and all safety gates. If n8n is introduced
later, it may trigger existing commands or render dashboard-oriented digests,
but it must not duplicate business logic or hold the only copy of any state.
Notifications remain dashboard-only until a separate approval decision.

## Re-evaluation criteria

Reconsider deployment only when all of the following are demonstrated:

1. A recurring dashboard/orchestration task is documented and is materially
   simpler with n8n than with the existing CLI and systemd units.
2. The workflow calls an idempotent Python command and receives an explicit
   success/failure result.
3. SQLite and the Python engine remain the source of truth.
4. n8n has no production Gmail, ATS, browser, or outbound-action credentials.
5. The service has an isolated state directory, backup procedure, and pause
   behavior.
6. A local fixture proves that a failed or repeated workflow cannot create
   duplicate applications or bypass approval gates.

Until then, adding n8n would increase operational surface without reducing
risk or maintenance.
