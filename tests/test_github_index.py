import unittest

from job_engine.github_index import GitHubIndexError, GitHubRepositoryIndexer


class GitHubIndexTests(unittest.TestCase):
    def test_indexes_only_allowlisted_public_repository(self):
        payloads = {
            "https://api.github.com/repos/rishabhbalaji/example": {
                "default_branch": "main",
            },
            "https://api.github.com/repos/rishabhbalaji/example/git/trees/main?recursive=1": {
                "tree": [
                    {"path": "README.md", "sha": "abc", "size": 12, "type": "blob", "url": "https://api.github.com/blob/abc"},
                    {"path": "src", "sha": "tree", "type": "tree", "url": "https://api.github.com/tree/tree"},
                ],
            },
        }
        calls = []

        def fetcher(url):
            calls.append(url)
            return payloads[url]

        indexes = GitHubRepositoryIndexer(
            ("https://github.com/rishabhbalaji/example",),
            fetcher=fetcher,
        ).index()

        self.assertEqual(indexes[0].default_branch, "main")
        self.assertEqual(indexes[0].files[0].path, "README.md")
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("Authorization" not in call for call in calls))

    def test_rejects_non_github_or_non_https_urls(self):
        with self.assertRaises(GitHubIndexError):
            GitHubRepositoryIndexer(("http://github.com/example/repo",)).index()
        with self.assertRaises(GitHubIndexError):
            GitHubRepositoryIndexer(("https://gitlab.com/example/repo",)).index()

    def test_empty_allowlist_is_rejected(self):
        with self.assertRaises(ValueError):
            GitHubRepositoryIndexer(())
