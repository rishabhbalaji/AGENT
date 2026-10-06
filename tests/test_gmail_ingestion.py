import sqlite3
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

from job_engine.gmail_ingestion import (
    GmailIngestionError,
    GmailMessage,
    list_status_messages,
    persist_status_messages,
)


class GmailIngestionTests(unittest.TestCase):
    def test_lists_metadata_without_requesting_message_body(self):
        service = Mock()
        service.users().messages().list().execute.return_value = {
            "messages": [{"id": "m1"}]
        }
        service.users().messages().get().execute.return_value = {
            "id": "m1",
            "threadId": "t1",
            "internalDate": "1730000000000",
            "payload": {
                "headers": [
                    {"name": "From", "value": "updates@example.com"},
                    {"name": "Subject", "value": "Application update"},
                ]
            },
        }

        messages = list_status_messages(service, lookback=timedelta(hours=1))

        self.assertEqual(messages[0].category, "application")
        detail_call = service.users().messages().get.call_args_list[1]
        self.assertEqual(detail_call.kwargs["format"], "metadata")
        self.assertNotIn("body", detail_call.kwargs)

    def test_persists_messages_idempotently(self):
        message = GmailMessage(
            "m1", "t1", "2025-01-01T00:00:00+00:00", "a@example.com", "Subject", "status"
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "engine.sqlite"
            self.assertEqual(persist_status_messages(database, [message]), 1)
            self.assertEqual(persist_status_messages(database, [message]), 0)
            with sqlite3.connect(database) as connection:
                self.assertEqual(
                    connection.execute("SELECT count(*) FROM email_status_messages").fetchone()[0],
                    1,
                )

    def test_rejects_insecure_secret_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "client.json"
            secret.write_text("{}", encoding="utf-8")
            secret.chmod(0o644)
            with self.assertRaisesRegex(GmailIngestionError, "must not be accessible"):
                from job_engine.gmail_ingestion import authorize_gmail

                authorize_gmail(secret, Path(directory) / "token.json")
