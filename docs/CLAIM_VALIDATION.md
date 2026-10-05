# Claim validation

Every generated factual claim must be represented as a `Claim` with non-empty
text and one or more unique IDs from the local `EvidenceChunk` set. The
validator resolves those IDs and returns `ValidatedClaim` records containing
the complete supporting chunks.

Claims without evidence, claims citing unknown chunks, repeated evidence IDs,
and empty claim text are rejected explicitly. This keeps generated material
traceable to the local resume or explicitly allowlisted public repositories.
