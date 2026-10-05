# Public GitHub allowlist indexing

`GitHubRepositoryIndexer` accepts explicit HTTPS URLs from
`config/examples/repositories.yaml` and reads public repository metadata and
the default-branch file tree through GitHub's unauthenticated API.

The indexer:

- rejects non-GitHub and non-HTTPS URLs;
- never discovers repositories outside the configured allowlist;
- never sends tokens, cookies, or authentication headers;
- records file paths, object hashes, sizes, and API URLs;
- does not clone repositories or modify Git state.

The repository allowlist is empty by default. Add only public repositories
that are explicitly approved for evidence retrieval.
