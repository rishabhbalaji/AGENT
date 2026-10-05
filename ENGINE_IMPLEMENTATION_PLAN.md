# Local Job Application Engine: Implementation Plan

## Purpose

Build a free, local-first job-search assistant hosted on `rbkasus`, using `rbkmsi` only for Ollama inference over Tailscale. The system discovers and ranks jobs, prepares application material, tracks outcomes, and automates only approved external ATS flows. LinkedIn remains manual and untouched by automation.

This file is the implementation plan. `Reference Documents/Local Job Application Engine Plan.md` is the imported conversation and should remain unchanged.

## Confirmed decisions

- Search profiles are modular and editable. The initial configuration must support full-time, part-time, exploratory, and future custom profiles, each with its own keywords, locations, employment types, salary floor, remote-work rules, schedule, exclusions, and score thresholds.
- UK SC Clearance is currently a hard exclusion. The user does not hold SC, so postings that require or request SC must be skipped regardless of wording. This rule remains configurable for a future profile change.
- Company exclusions must support exact names, aliases, domains, and an explanatory reason. Exclusions are applied before LLM scoring.
- LinkedIn and Indeed are permanently unauthenticated discovery-only sources. The engine must never use cookies, login sessions, Easy Apply, messages, posts, connection requests, or other authenticated actions on either service.
- The browser dashboard is the primary review interface. It is reachable through Tailscale, binds to the Tailscale interface rather than `0.0.0.0`, and is protected by authentication or an equivalent Tailscale access restriction.
- The dashboard maintains queues for convenient daily review; desktop notifications are not required.
- External ATS automation follows staged autonomy: manual approval during the pilot, then autonomous submission only for explicitly vetted companies and tested provider workflows. CAPTCHAs, MFA, unexpected pages, changed forms, ambiguous questions, and other safety challenges are always parked.
- Greenhouse is the first live ATS pilot. Workday and other account-creation flows must pass local fixture and designated test-posting checks before any live automation.
- The engine should discover and rank at least 15 suitable jobs per day when available. This is not a requirement to submit 15 applications, and submissions must never be forced when quality or safety checks fail.
- Part-time discovery runs continuously from 20:00 to 08:00 UK time. The schedule remains configurable.
- Remote roles must distinguish UK-remote, country-restricted remote, and worldwide remote, including right-to-work, tax, timezone, and location restrictions.
- The first release uses safe public sources and APIs before guest aggregators: public ATS feeds, GOV.UK Find a Job, Reed, Adzuna, and compatible remote-job sources. Aggregators can be added after rate-limit and reliability testing.
- SQLite is the initial database on SDA. Supabase and other hosted databases are excluded. PostgreSQL is deferred until measured local query or concurrency needs justify it.
- SDA is the only required storage device. Configure its filesystem by UUID at a fixed mount path and verify at startup that the data root resolves to the SDA device; the engine must never mount or depend on `/dev/sdb`.
- Runtime workers are Python processes supervised by systemd. Docker is reserved for optional isolated services.
- GitHub indexing begins with an explicit public-repository allowlist. Private repositories are a later opt-in feature.
- Development starts with fictional personas, synthetic postings, and local ATS fixtures. Live discovery and submissions are enabled only after the dry-run and safety gates pass.
- A self-hosted Vaultwarden instance on SDA and restricted to Tailscale is the intended future password-vault solution. It is not required for the first dry-run milestone.

## Version control

- Initialize this project as a local Git repository on `rbkasus`.
- Track source code, tests, schemas, configuration examples, migration scripts, systemd templates, and documentation.
- Never track personal resumes, persona data, job-posting snapshots, generated PDFs, email content, application history, credentials, model caches, browser profiles, or SDA runtime data.
- Use `.gitignore` plus a checked-in `.env.example`; secrets are supplied through the local password vault or systemd credentials.
- Make small commits at phase boundaries and before enabling a new worker class. Use branches for risky automation experiments.
- Do not add a remote or push data anywhere unless explicitly configured later.
- Record the current source revision with generated artifacts so outputs can be reproduced locally.

## Non-negotiable constraints

- No paid services, hosted databases, cloud storage, proxies, CAPTCHA solvers, or required subscriptions.
- Persistent data belongs on the reliable SDA HDD on `rbkasus`; the unreliable SSD must not be a dependency.
- No LinkedIn or Indeed login automation, LinkedIn Easy Apply automation, posts, connection requests, or outbound messages.
- Employer and LinkedIn messages are drafts only.
- External routes may be selected automatically, but every route still needs compatibility, legitimacy, and safety checks before action.
- Account creation may eventually be automated through a local vault adapter. CAPTCHA, MFA, phone checks, identity checks, and other security challenges may be attempted only through ordinary supported flows; if they fail or require human input, the job is parked with its resume and cover letter ready.
- The engine must fail closed when Ollama, storage, configuration, or a browser workflow is unavailable.
- All job-search profiles, schedules, locations, keywords, thresholds, repository links, and limits are editable configuration.
- The creative Agent Corner is isolated from credentials, application actions, browser sessions, and production job data.
- Fifteen suitable ranked jobs per day is a best-effort discovery target, never a submission quota. The system must report a shortfall rather than submit a weak, suspicious, or incompatible application.
- Initial development uses example profiles and a fictional persona; real keywords, resume data, repositories, and credentials are added later.

## Operating schedule

All times are UK local time and must be configurable:

- `06:00-14:00`: full-time discovery, scoring, and preparation.
- `14:00-20:00`: full-time discovery, scoring, preparation, and approved external-ATS applications.
- `20:00-08:00`: continuous part-time discovery, scoring, and preparation.
- Outside an active application window: drafting, maintenance, status ingestion, and isolated Agent Corner work may continue, but no applications are submitted.
- A configurable transition and maintenance window may pause or drain workers cleanly.

Gaming pause/resume must stop inference, tailoring, and application workers while allowing lightweight discovery to continue or queue.

## Chosen architecture

### Core services on `rbkasus`

- Python worker package for discovery, normalization, scoring orchestration, RAG, document generation, tracking, and ATS adapters.
- SQLite initially, stored on SDA. Supabase is explicitly out of scope; move to a locally hosted PostgreSQL instance only if actual query or concurrency needs justify the extra operational cost.
- FastAPI plus a small server-rendered UI for review queues and controls, bound to the configured Tailscale address and protected from public exposure.
- Playwright only for explicitly supported external ATS adapters.
- systemd as the required production supervisor.
- Docker Compose only for optional local dependencies such as Vaultwarden; no service may silently place state on the SSD.

### Optional control plane

Start with Python scheduling and explicit commands. Add self-hosted n8n after the core workflow is observable and tested. n8n may trigger workers and digest jobs, but must not own business logic or irreplaceable state.

### Inference on `rbkmsi`

- Ollama calls use a configurable Tailscale endpoint.
- Initial triage model: an installed lightweight/general model selected through configuration.
- Tailoring model: benchmark installed models against a fixed local evaluation set before choosing one.
- Embeddings: use a free local Ollama embedding model only if retrieval quality justifies its memory and storage cost.
- No model download or model switch may be required for the discovery-only path.

## Career-ops integration assessment

The upstream project `career-ops-hq/career-ops` is a useful open-source reference and candidate component. Its documented design includes local model runners, YAML profiles, Markdown/TSV tracking, public ATS scanning, URL-to-evaluation pipelines, ATS-safe PDF generation, cover-letter drafts, company research, repost detection, local data directories, and deterministic ATS/fact checks. It also has a strong human-in-the-loop boundary: it prepares forms but does not submit applications or send email. Its repository license is MIT; any reused code or substantial templates must retain the upstream copyright and license notice.

### Adopt

- Source-annotated resume and story provenance. No generated claim may exist without evidence from the persona, resume, or configured repository data.
- A structured evaluation report before document generation, including fit, gaps, legitimacy, company research, and route classification.
- Deterministic checks for CV facts and ATS structure, separate from model judgment.
- Public ATS/provider discovery, liveness verification, URL normalization, deduplication, repost/ghost-posting signals, and resumable scans.
- Application-scoped artifact bundles containing the job description, source CV, tailored CV, PDF, change notes, and decision metadata.
- Local Markdown/YAML/TSV conventions where they improve inspectability and portability.
- Local Ollama/OpenAI-compatible endpoint support, adapted to the existing Tailscale Ollama service.

### Adapt rather than copy wholesale

- Keep the engine's Python interfaces, SQLite event model, typed configuration, and systemd lifecycle as the primary architecture.
- Treat `career-ops` templates and modes as an import/reference layer, not as the source of truth for our runtime data.
- Use HTML plus Playwright or the existing LaTeX template according to the user's chosen resume format; keep the renderer behind an adapter.
- Preserve our configurable schedule, full-time/part-time/exploratory modes, SDA data root, dashboard queues, and Agent Corner isolation.
- Do not import its hosted/free-tier assumptions, external provider credentials, or CLI-specific orchestration.
- Do not enable any upstream operation that submits, emails, posts, connects, or bypasses a security challenge.

### Integration strategy

1. Pin a specific upstream commit and retain its MIT attribution before copying code or templates.
2. Reproduce the useful behavior with fixture tests first: provenance validation, ATS checks, liveness, URL identity, repost detection, and artifact-bundle layout.
3. Add a narrow `career_ops_adapter` boundary only where an upstream implementation saves substantial work and its data contract can be isolated.
4. Keep upstream-derived code or templates clearly attributed and separately reviewable; do not mix runtime data into the repository.
5. Compare outputs against our dummy persona and dummy postings before connecting real sources or credentials.

The project is therefore an accelerator for evaluation, document generation, and discovery ideas, not a replacement for the local orchestration, safety policy, or storage design in this plan.

## Data and configuration design

Use a versioned configuration directory on SDA:

- `profiles.yaml`: full-time, part-time, and exploratory search profiles.
- `schedule.yaml`: daily windows and pause behavior.
- `sources.yaml`: enabled sources, rate limits, and source-specific settings.
- `repositories.yaml`: manually maintained GitHub repository URLs.
- `policy.yaml`: thresholds, discovery targets, staged-autonomy rules, route compatibility rules, clearance exclusions, company exclusions, account-creation policy, retention, and fail-closed rules.
- `.env` or systemd credentials: secrets only; never commit tokens or passwords.

Store immutable source snapshots and generated artifacts with a job ID so every score, resume claim, and application event can be audited locally.
Store the engine data root at a fixed UUID-backed SDA mount path and refuse startup if the path is missing, read-only, or resolves to another device.

## Milestones, phases, and stages

The implementation uses three nested levels:

- **Milestone**: a major capability or release boundary.
- **Phase**: a related collection of phases within a milestone.
- **Stage**: the smallest independently deliverable task. Every stage is implemented on its own Git branch.

The branch name is the stage identifier followed by a short description:

```text
M0P0S0-initialize-repository
M0P0S1-define-storage-and-secrets
M1P0S0-create-python-scaffold
```

The exact numeric identifier is authoritative; the description is for readability.

### Branch and handoff policy

- `main` is the protected integration baseline and must remain untouched by implementation work.
- The first working branch is `M0P0S0-initialize-repository`; no implementation is performed directly on `main`.
- Each stage starts from the completed branch immediately before it and produces one coherent, working increment.
- A stage is complete only when its acceptance checks pass, its documentation is updated, and its branch is clean.
- At the end of each stage, the user takes over to review, push the branch to `git@github.com:rishabhbalaji/AGENT.git`, and create or switch to the next stage branch using the supplied commands.
- No stage may commit personal resumes, persona data, job snapshots, generated PDFs, email content, application history, credentials, model caches, browser profiles, runtime data, or secrets.
- The public repository must contain source, tests, schemas, configuration examples, migrations, systemd templates, and documentation only.
- A `.env.example` is tracked; the real `.env` is ignored and remains local.
- Changes are never pushed automatically. The user explicitly controls the public GitHub handoff.
- Risky automation experiments use a separate branch and must not be merged into the stable stage sequence until their fixture and safety checks pass.

### Stage completion contract

Every stage must provide:

1. A working tree that can be checked out and run from the documented instructions.
2. Tests or deterministic validation appropriate to the stage.
3. Updated documentation and configuration examples.
4. A concise handoff summary containing the stage branch, files changed, checks run, known limitations, and the commands to push and begin the next stage.
5. No required state written outside the configured SDA data root.

### Milestone and stage map

#### Milestone 0 — Foundation and repository safety

**M0P0 — Repository and local-environment foundation**

- **M0P0S0 — Initialize repository** (`M0P0S0-initialize-repository`): initialize local Git, create the protected `main` baseline, create the first stage branch, and add the initial project documentation.
- **M0P0S1 — Add repository exclusions** (`M0P0S1-add-repository-exclusions`): create `.gitignore` rules for secrets, personal data, runtime state, generated artifacts, model caches, browser profiles, and SDA data.
- **M0P0S2 — Add safe configuration contract** (`M0P0S2-add-configuration-contract`): add `.env.example`, configuration examples, secret-handling documentation, and validation rules without real values.

**M0P1 — SDA storage and host prerequisites**

- **M0P1S0 — Define SDA data root** (`M0P1S0-define-sda-data-root`): document the fixed mount path and UUID-based `/etc/fstab` approach for SDA.
- **M0P1S1 — Add storage safety check** (`M0P1S1-add-storage-safety-check`): refuse startup when the data root is missing, read-only, or resolves to a device other than SDA; never mount or depend on `/dev/sdb`.
- **M0P1S2 — Verify host prerequisites** (`M0P1S2-verify-host-prerequisites`): document and check Python, systemd, LaTeX/PDF tooling, Tailscale, and network reachability to Ollama.

#### Milestone 1 — Configuration-first executable skeleton

**M1P0 — Application scaffold**

- **M1P0S0 — Create Python package** (`M1P0S0-create-python-package`): add the typed package layout, dependency metadata, CLI entry point, and structured logging.
- **M1P0S1 — Implement configuration loader** (`M1P0S1-implement-configuration-loader`): load modular profiles, schedules, sources, repositories, and policy configuration with schema validation.
- **M1P0S2 — Implement operating modes** (`M1P0S2-implement-operating-modes`): resolve full-time, part-time, exploratory, drafting, paused, and maintenance modes using UK local time.

**M1P1 — Local state and dry-run**

- **M1P1S0 — Add SQLite migrations** (`M1P1S0-add-sqlite-migrations`): create the initial schema and event model under SDA.
- **M1P1S1 — Add dry-run health command** (`M1P1S1-add-dry-run-health-command`): load example configuration, validate storage, resolve the current mode, and write one health/event record.
- **M1P1S2 — Add fictional fixtures** (`M1P1S2-add-fictional-fixtures`): add a fictional persona, synthetic postings, and route-decision fixtures without live accounts.

#### Milestone 2 — Discovery and job intelligence

**M2P0 — Public discovery**

- **M2P0S0 — Add ATS source contract** (`M2P0S0-add-ats-source-contract`): define normalized posting and source-health interfaces.
- **M2P0S1 — Add public ATS adapters** (`M2P0S1-add-public-ats-adapters`): implement the first direct public adapters, beginning with Greenhouse-compatible boards.
- **M2P0S2 — Add public feed adapters** (`M2P0S2-add-public-feed-adapters`): add GOV.UK Find a Job, Reed, Adzuna, and compatible remote-job feeds.
- **M2P0S3 — Add safe aggregator adapter** (`M2P0S3-add-guest-aggregator-adapter`): add guest/public aggregators only after rate-limit and reliability tests pass.

**M2P1 — Normalization and policy filtering**

- **M2P1S0 — Normalize and deduplicate postings** (`M2P1S0-normalize-and-deduplicate-postings`): retain source URLs, raw snapshots, stable identities, repost signals, and expiration state.
- **M2P1S1 — Implement modular profile matching** (`M2P1S1-implement-profile-matching`): apply configurable keywords, locations, employment types, salary floors, schedules, and score thresholds without an LLM.
- **M2P1S2 — Implement clearance exclusion** (`M2P1S2-implement-clearance-exclusion`): detect SC Clearance wording variants and exclude those postings before scoring.
- **M2P1S3 — Implement company exclusions** (`M2P1S3-implement-company-exclusions`): apply exact names, aliases, domains, and documented reasons before scoring.
- **M2P1S4 — Implement remote eligibility** (`M2P1S4-implement-remote-eligibility`): classify UK-remote, country-restricted, and worldwide roles and check right-to-work, tax, timezone, and location restrictions.

#### Milestone 3 — Evidence, ranking, and document preparation

**M3P0 — Local evidence and retrieval**

- **M3P0S0 — Import local master resume** (`M3P0S0-import-master-resume`): load a later user-provided resume from a local SDA path.
- **M3P0S1 — Index public GitHub allowlist** (`M3P0S1-index-public-github-allowlist`): import only explicitly listed public repositories using read-only access.
- **M3P0S2 — Add evidence retrieval** (`M3P0S2-add-evidence-retrieval`): create traceable resume and repository chunks.
- **M3P0S3 — Add claim validator** (`M3P0S3-add-claim-validator`): reject generated claims and bullets that lack local evidence.

**M3P1 — Ranking and drafts**

- **M3P1S0 — Add structured triage** (`M3P1S0-add-structured-triage`): score fit and extract role, salary, location, sponsorship, seniority, work mode, source, and route.
- **M3P1S1 — Add model-output validation** (`M3P1S1-add-model-output-validation`): validate strict schemas and record prompts, models, versions, and revisions.
- **M3P1S2 — Generate tailored documents** (`M3P1S2-generate-tailored-documents`): produce resumes, PDFs, cover letters, ATS answers, and LinkedIn message drafts locally.
- **M3P1S3 — Add deterministic document gates** (`M3P1S3-add-document-gates`): run fact and ATS checks and create repair queue items on failure.

#### Milestone 4 — Review interface and controlled applications

**M4P0 — Tailscale-only review dashboard**

- **M4P0S0 — Create FastAPI dashboard** (`M4P0S0-create-fastapi-dashboard`): add the server-rendered browser interface and queue navigation.
- **M4P0S1 — Secure dashboard binding** (`M4P0S1-secure-dashboard-binding`): bind to the Tailscale interface, add authentication or equivalent access restriction, and avoid `0.0.0.0`.
- **M4P0S2 — Add daily review queues** (`M4P0S2-add-daily-review-queues`): implement discovered, shortlisted, apply-yourself, drafted, parked, applied, rejected, interview, and archived states.
- **M4P0S3 — Add review actions** (`M4P0S3-add-review-actions`): implement approve, reject, park, edit, export, and mark-applied operations.

**M4P1 — ATS pilot**

- **M4P1S0 — Build ATS fixtures** (`M4P1S0-build-ats-fixtures`): test supported forms before live postings.
- **M4P1S1 — Pilot Greenhouse manually** (`M4P1S1-pilot-greenhouse-manually`): require approval for every submission and record local evidence.
- **M4P1S2 — Add staged autonomy gates** (`M4P1S2-add-staged-autonomy-gates`): allow autonomous submission only for vetted companies and tested providers.
- **M4P1S3 — Park unsafe workflows** (`M4P1S3-park-unsafe-workflows`): park CAPTCHAs, MFA, changed forms, unexpected pages, ambiguous questions, and unsupported account creation.
- **M4P1S4 — Evaluate Vaultwarden integration** (`M4P1S4-evaluate-vaultwarden-integration`): prepare a future SDA/Tailscale Vaultwarden adapter without storing secrets in code or job records.

**M4P2 — Local model integration**

- **M4P2S0 — Add Ollama connectivity** (`M4P2S0-add-ollama-connectivity`): verify a Tailscale endpoint and exact configured model, and expose fail-closed structured JSON transport without changing deterministic policy decisions.

#### Milestone 5 — Operations, status tracking, and isolation

**M5P0 — Daily operations**

- **M5P0S0 — Add systemd workers** (`M5P0S0-add-systemd-workers`): supervise discovery, scoring, drafting, dashboard, and application workers.
- **M5P0S1 — Add pause and resume** (`M5P0S1-add-pause-and-resume`): stop inference, tailoring, and applications during gaming while allowing lightweight discovery to queue.
- **M5P0S2 — Add retention and local backups** (`M5P0S2-add-retention-and-backups`): retain application evidence indefinitely, raw snapshots for approximately 12 months, and prune redundant caches.
- **M5P0S3 — Add recovery checks** (`M5P0S3-add-recovery-checks`): test reboot recovery, Ollama outages, read-only SDA, and resumable workflows.

**M5P1 — Status and isolation**

- **M5P1S0 — Add dedicated Gmail ingestion** (`M5P1S0-add-dedicated-gmail-ingestion`): add read-only IMAP status ingestion for a dedicated application account; never send email.
- **M5P1S1 — Isolate Agent Corner** (`M5P1S1-isolate-agent-corner`): separate data, process, credentials, browser sessions, job records, and outbound actions.
- **M5P1S2 — Evaluate n8n** (`M5P1S2-evaluate-n8n`): add self-hosted n8n only if it reduces operational friction without owning business logic or irreplaceable state.

The detailed implementation guidance and exit criteria for these stages are defined below. A stage may be split into additional numbered stages later, but existing stage identifiers must not be silently renumbered after they have been handed off.

### User-controlled stage handoff

At the end of each completed stage, provide the user with commands customized to the actual current branch and next stage. The normal pattern is:

```bash
# Review the completed stage
git status
git log --oneline --decorate -5
git diff main...HEAD --stat

# Publish the completed stage when the user is ready
git remote add origin git@github.com:rishabhbalaji/AGENT.git  # once only
git push -u origin M0P0S0-initialize-repository

# Start the next stage from the completed stage
git switch -c M0P0S1-add-repository-exclusions
```

The branch names in the commands must be replaced with the actual completed and next stage branches. The assistant must not run `git push`, create a GitHub repository, merge into `main`, or switch to the next stage without the user's explicit handoff. If the remote already exists, the `git remote add` command must be omitted.

### Phase 0: Host and storage verification

1. Identify the SDA filesystem UUID, configure a fixed `/etc/fstab` mount path, and confirm ownership, available space, and persistence across reboot on `rbkasus`.
2. Define the engine data root and verify Docker, systemd, Python, Java/LaTeX tooling, and network reachability to Ollama.
3. Confirm that logs, caches, databases, generated PDFs, backups, and future Vaultwarden state resolve under the SDA data root and never `/dev/sdb`.
4. Create a local-only secret handling procedure for the GitHub token and Tailscale/Ollama endpoint. Defer email credentials and vault integration until those features are enabled.

Exit criteria: a documented data root and a storage test proving the engine can restart without writing required state to the SSD. Git is initialized before implementation commits begin.

### Phase 1: Configuration-first skeleton

1. Create the Python package, typed configuration loader, schema validation, structured logging, and CLI.
2. Add schedule resolution and mode selection for full-time, part-time, exploratory, drafting, and paused states.
3. Add SQLite migrations and an event table before implementing sources.
4. Add dry-run mode as the default.
5. Add example profiles, a fictional persona fixture, and a route-decision interface without connecting live accounts.
6. Add compatibility fixtures for the adopted career-ops concepts: evaluation reports, provenance records, ATS checks, and application artifact bundles.

Exit criteria: configuration changes alter behavior without code edits; invalid configuration fails before workers start.

### Phase 2: Discovery-only pipeline

1. Implement source adapters in priority order: public ATS feeds, GOV.UK Find a Job, Reed, Adzuna, compatible remote-job feeds, then guest/public aggregators where permitted.
2. Apply per-source rate limits, jitter, retries, backoff, and source health tracking.
3. Normalize postings, deduplicate by stable content identity, retain source URLs and raw snapshots, and detect expired postings.
4. Add configurable profile matching without using an LLM.
5. Evaluate career-ops provider/scanner behavior against our adapter contract before selecting any provider implementation for reuse.

Exit criteria: repeated polling produces stable deduplicated records, respects limits, and never authenticates to LinkedIn or Indeed.

### Phase 3: Resume and repository knowledge

1. Import the master resume from a local path.
2. Import only public repository URLs listed in `repositories.yaml` using read-only GitHub access. Private repositories remain a separate opt-in feature.
3. Create traceable chunks for resume claims and repository evidence.
4. Add retrieval and a claim validator that rejects unsupported resume bullets.

Exit criteria: every generated claim links to local evidence; missing evidence is reported instead of invented.

### Phase 4: Ranking and document drafts

1. Add structured triage output: fit score, role family, location, salary, sponsorship, seniority, work mode, source, and route.
2. Validate model output against a strict schema and store the prompt/model/version used.
3. Generate tailored resume drafts, cover letters, ATS answers, and LinkedIn message drafts using the existing LaTeX template where available.
4. Render PDFs locally and expose all drafts for review.
5. Add deterministic fact and ATS gates inspired by career-ops; a failed gate produces a repair queue item rather than silently lowering quality.

Exit criteria: deterministic test postings produce valid structured results and traceable documents; this phase performs no submissions.

### Phase 5: Review dashboard and daily workflow

1. Add queues for discovered, shortlisted, apply-yourself, drafted, parked, applied, rejected, interview, and archived states.
2. Add approve, reject, park, edit, export, and mark-applied actions.
3. Add a daily-review view with generated PDFs, draft messages, status changes, and clear shortfall reporting.
4. Add read-only IMAP ingestion later through a dedicated application Gmail account, with no email sending. Existing personal Gmail is out of scope for the initial integration.

Exit criteria: the complete daily review can be performed locally through the Tailscale-only dashboard without opening a cloud dashboard.

### Phase 6: External ATS pilot

1. Build fixture-based tests for supported ATS forms before using live postings.
2. Begin with Greenhouse and manual approval for every submission; route selection remains policy-driven rather than hard-coded to a single provider.
3. Require a complete posting, validated documents, known form fields, policy approval, and an approved company/provider allowlist entry before submission.
4. Add autonomous submission only after the provider-specific fixture, recovery, and safety checklist passes.
5. Park Workday and all other account-creation flows until they pass local fixtures and designated test-posting checks.
6. Use the future Vaultwarden adapter for credentials; never write passwords into the repository or job records.
7. Screenshot and park every unexpected page, failed security challenge, missing answer, or validation error while preserving a resumable workflow.
8. Record confirmation and evidence locally.

Exit criteria: the pilot can be paused instantly, submits only approved external forms, and has a tested recovery path.

### Phase 7: Operations and Agent Corner

1. Add systemd units and timers for each worker class.
2. Add health checks, pause/resume, retention, local backups on SDA, and recovery instructions.
3. Add the Agent Corner as a separate process, data directory, and tool policy with no production credentials or action APIs.
4. Add n8n only if it reduces operational friction after the core is stable.

Exit criteria: gaming pause, reboot recovery, Ollama outage, and Agent Corner isolation are tested.

## Initial test cases

- Empty and invalid configuration.
- Schedule boundaries for full-time `06:00-20:00`, part-time `20:00-08:00`, pause, and configurable maintenance windows.
- Duplicate postings from multiple sources.
- Remote-location and right-to-work classification.
- SC Clearance wording variants and hard exclusion.
- Company exclusion names, aliases, domains, and reasons.
- Expired or missing job descriptions.
- Ollama unavailable during discovery and during drafting.
- Unsupported resume claim requested by a job.
- Posting requiring login, CAPTCHA, Workday account creation, or an unknown form.
- Unexpected ATS field or changed page structure.
- Pause during a running worker and resume after reboot.
- SDA unavailable or read-only.
- Agent Corner attempting to access a credential, job record, browser, or outbound action.
- Git status and history excluding all runtime data, personal data, and secrets.
- Reproducibility of a generated artifact from its source revision and stored local evidence.
- Fifteen-job discovery shortfall when fewer than fifteen legitimate jobs pass validation.
- Staged-autonomy approval, allowlist, and provider safety gates.
- Account creation through a Vaultwarden adapter with no secret leakage.
- Dashboard access through the Tailscale interface without public binding.
- SDA UUID mount verification and refusal to use `/dev/sdb`.

## Immediate next action

Do not install the full stack yet. First initialize Git and create the Phase 0/1 scaffold. The first executable milestone is a dry-run CLI that loads editable example configuration, resolves the current operating mode, validates the UUID-backed SDA data root, and writes one health/event record under that root. The first browser milestone is a Tailscale-only FastAPI review dashboard. In parallel, pin and inspect the upstream career-ops commit before reusing any implementation or template. Real SDA paths, resume assets, tracker data, repositories, vault data, and credentials can be added later.
