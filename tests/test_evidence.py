import base64
import unittest

from job_engine.evidence import repository_evidence, resume_evidence
from job_engine.github_index import RepositoryFile, RepositoryIndex
from job_engine.resume import ResumeDocument


class EvidenceTests(unittest.TestCase):
    def test_resume_chunks_are_stable_and_traceable(self):
        resume = ResumeDocument("/private/resume.pdf", "a" * 64, 1, "Python\n\nAutomation")
        chunks = resume_evidence(resume, chunk_size=7)
        self.assertEqual(chunks[0].source_type, "resume")
        self.assertIn("sha256=", chunks[0].source_ref)
        self.assertEqual(len(chunks[0].content_sha256), 64)
        self.assertEqual(chunks[0].chunk_id, resume_evidence(resume, chunk_size=7)[0].chunk_id)

    def test_repository_retrieval_decodes_only_indexed_text_files(self):
        index = RepositoryIndex(
            "https://github.com/example/repo",
            "example",
            "repo",
            "main",
            (
                RepositoryFile("README.md", "abc", 4, "https://api.github.com/blob/abc"),
                RepositoryFile("image.png", "def", 4, "https://api.github.com/blob/def"),
            ),
        )
        content = base64.b64encode(b"Python evidence").decode("ascii")
        chunks = repository_evidence(
            index,
            fetcher=lambda url: {"encoding": "base64", "content": content},
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].source_type, "github")
        self.assertIn("README.md", chunks[0].source_ref)

    def test_invalid_chunk_size_is_rejected(self):
        resume = ResumeDocument("/private/resume.pdf", "a" * 64, 1, "text")
        with self.assertRaises(ValueError):
            resume_evidence(resume, chunk_size=0)
