# Local resume import

`job_engine.resume.import_pdf` imports a local PDF resume without sending it
to a network service or storing a copy in the repository. The returned
`ResumeDocument` contains extracted text, page count, absolute source path,
and a SHA-256 hash for reproducibility.

Example:

```python
from pathlib import Path

from job_engine.resume import import_pdf

resume = import_pdf(Path("/path/to/master-resume.pdf"))
```

Resume files matching `*.pdf` and `resume*` are ignored by Git. A later stage
will persist only approved provenance and evidence records in local runtime
storage; this stage does not submit or transmit resume content.
