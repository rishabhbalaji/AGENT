"""Read-only Gmail status ingestion with bounded, idempotent polling."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .database import DatabaseError, migrate

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
DEFAULT_STATUS_TERMS = ("application", "interview", "assessment", "rejected", "next steps")


class GmailIngestionError(RuntimeError):
    """Raised when Gmail setup or a read-only ingestion operation fails."""


@dataclass(frozen=True)
class GmailMessage:
    message_id: str
    thread_id: str
    received_at: str
    sender: str
    subject: str
    category: str


def _require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise GmailIngestionError(f"{label} does not exist: {path}")
    if os.name != "nt" and path.stat().st_mode & 0o077:
        raise GmailIngestionError(f"{label} must not be accessible by group or others: {path}")


def authorize_gmail(client_secret_path: Path, token_path: Path, *, port: int = 0) -> Any:
    """Run a local OAuth consent flow and return Gmail API credentials."""
    _require_file(client_secret_path, "Gmail client secret")
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:
        raise GmailIngestionError("Google OAuth dependencies are not installed") from exc

    credentials = None
    if token_path.exists():
        _require_file(token_path, "Gmail token")
        try:
            credentials = Credentials.from_authorized_user_file(
                str(token_path), [GMAIL_READONLY_SCOPE]
            )
        except (ValueError, OSError) as exc:
            raise GmailIngestionError(f"invalid Gmail token file: {token_path}") from exc
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception as exc:
            raise GmailIngestionError("Gmail token refresh failed; consent may be revoked") from exc
    if not credentials or not credentials.valid:
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path), [GMAIL_READONLY_SCOPE]
            )
            credentials = flow.run_local_server(port=port, access_type="offline", prompt="consent")
        except Exception as exc:
            raise GmailIngestionError("Gmail OAuth consent flow failed") from exc
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    if os.name != "nt":
        token_path.chmod(0o600)
    return credentials


def build_gmail_service(credentials: Any) -> Any:
    """Build the Gmail API client; only read-only methods are used by this module."""
    try:
        from googleapiclient.discovery import build
        return build("gmail", "v1", credentials=credentials, cache_discovery=False)
    except Exception as exc:
        raise GmailIngestionError("cannot initialize Gmail API client") from exc


def _header(headers: list[dict[str, str]], name: str) -> str:
    wanted = name.lower()
    for header in headers:
        if header.get("name", "").lower() == wanted:
            return header.get("value", "").strip()
    return ""


def _category(sender: str, subject: str, terms: tuple[str, ...]) -> str:
    value = f"{sender} {subject}".lower()
    for term in terms:
        if term.lower() in value:
            return term.lower().replace(" ", "_")
    return "status"


def list_status_messages(
    service: Any,
    *,
    lookback: timedelta,
    max_messages: int = 100,
    query: str = "in:anywhere",
    status_terms: tuple[str, ...] = DEFAULT_STATUS_TERMS,
) -> list[GmailMessage]:
    """List recent message metadata only; message bodies are never requested."""
    if max_messages < 1:
        raise ValueError("max_messages must be positive")
    after = int((datetime.now(timezone.utc) - lookback).timestamp())
    bounded_query = f"{query} after:{after}"
    messages: list[GmailMessage] = []
    request = service.users().messages().list(
        userId="me", q=bounded_query, maxResults=min(max_messages, 100)
    )
    while request and len(messages) < max_messages:
        response = request.execute()
        for item in response.get("messages", []):
            if len(messages) >= max_messages:
                break
            detail = (
                service.users()
                .messages()
                .get(userId="me", id=item["id"], format="metadata", metadataHeaders=["From", "Subject"])
                .execute()
            )
            payload = detail.get("payload", {})
            headers = payload.get("headers", [])
            internal_date = int(detail.get("internalDate", "0")) / 1000
            received_at = datetime.fromtimestamp(internal_date, timezone.utc).isoformat()
            sender = _header(headers, "From")
            subject = _header(headers, "Subject")
            messages.append(
                GmailMessage(
                    message_id=detail["id"],
                    thread_id=detail.get("threadId", ""),
                    received_at=received_at,
                    sender=sender,
                    subject=subject,
                    category=_category(sender, subject, status_terms),
                )
            )
        token = response.get("nextPageToken")
        request = (
            service.users()
            .messages()
            .list(userId="me", q=bounded_query, pageToken=token, maxResults=100)
            if token and len(messages) < max_messages
            else None
        )
    return messages


def persist_status_messages(database_path: Path, messages: list[GmailMessage]) -> int:
    """Persist message metadata idempotently without changing application state."""
    migrate(database_path)
    try:
        with __import__("sqlite3").connect(database_path) as connection:
            inserted = 0
            for message in messages:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO email_status_messages(
                        message_id, thread_id, received_at, sender, subject,
                        category, payload_json, ingested_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (
                        message.message_id,
                        message.thread_id,
                        message.received_at,
                        message.sender,
                        message.subject,
                        message.category,
                        json.dumps({"source": "gmail"}, sort_keys=True),
                    ),
                )
                inserted += cursor.rowcount
            connection.commit()
            return inserted
    except __import__("sqlite3").Error as exc:
        raise DatabaseError(f"cannot persist Gmail status messages: {exc}") from exc
