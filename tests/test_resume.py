import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from job_engine.resume import ResumeImportError, import_pdf


class ResumeImportTests(unittest.TestCase):
    def test_imports_text_and_records_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.pdf"
            path.write_bytes(b"fixture-pdf")
            page = Mock()
            page.extract_text.return_value = "Python developer"
            reader = Mock()
            reader.pages = [page]
            with patch("job_engine.resume.PdfReader", return_value=reader):
                document = import_pdf(path)
        self.assertEqual(document.page_count, 1)
        self.assertEqual(document.text, "Python developer")
        self.assertEqual(len(document.sha256), 64)

    def test_missing_file_is_explicit(self):
        with self.assertRaisesRegex(ResumeImportError, "missing"):
            import_pdf(Path("/missing/resume.pdf"))

    def test_empty_extraction_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.pdf"
            path.write_bytes(b"fixture-pdf")
            page = Mock()
            page.extract_text.return_value = ""
            reader = Mock()
            reader.pages = [page]
            with patch("job_engine.resume.PdfReader", return_value=reader):
                with self.assertRaisesRegex(ResumeImportError, "no extractable text"):
                    import_pdf(path)
