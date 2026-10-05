# Evidence retrieval

`job_engine.evidence` creates deterministic `EvidenceChunk` records from:

- extracted local master-resume text, identified by its source path and PDF hash;
- text files in an already-created public GitHub repository index, identified
  by repository URL, branch, file path, and blob SHA.

Chunks have stable IDs derived from their source reference, ordinal, and content
hash. Repository retrieval only reads supported text suffixes and decodes
GitHub's base64 blob response. It does not clone repositories, inspect
unindexed paths, or send credentials.
