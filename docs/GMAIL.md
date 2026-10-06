# Read-only Gmail status ingestion

The engine can poll a dedicated Gmail mailbox for application-status metadata.
This path is intentionally separate from application submission and does not
send, delete, modify, label, archive, or reply to messages.

## OAuth setup

Create a Desktop OAuth client with only this scope:

```text
https://www.googleapis.com/auth/gmail.readonly
```

Keep the downloaded client secret under `config/local/`, which is ignored by
Git and must remain mode `600`. The OAuth token is written to the ignored
runtime path with the same restrictive permissions. Never paste either file
into chat or commit them.

## One bounded poll

Run from the repository root:

```bash
job-engine gmail-status \
  --client-secret config/local/gmail-client-secret.json \
  --token runtime/gmail-token.json \
  --database runtime/engine.sqlite3 \
  --lookback-hours 72 \
  --max-messages 100
```

The first run opens a local browser consent flow. Subsequent runs reuse the
local token and refresh it when possible. If the token is revoked, delete the
local token and run the command again.

Only message metadata is requested. Results are deduplicated by Gmail message
ID in the `email_status_messages` table. Ingestion does not change any job or
application status. Creating `PAUSED` stops the command before OAuth or API
access.
