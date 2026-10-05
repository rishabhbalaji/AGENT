# Posting normalization

`job_engine.normalization.normalize_posting` converts a
`NormalizedPosting` plus fetch metadata into a `PostingRecord`.

The record contains:

- a SHA-256 stable identity derived from source name and source job ID;
- the original source URL;
- the raw source snapshot;
- `active`, `expired`, or `unknown` expiration state;
- repost and duplicate-count signals after deduplication.

URL canonicalization is available for fallback identity and removes common
tracking parameters without changing the retained source URL. The normalizer
does not score, exclude, or submit postings; those are separate policy stages.
