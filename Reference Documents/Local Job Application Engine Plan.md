Local Job Application Engine Plan
Before we begin this task.
Tell me what you know about my current laptop, it's specifications and how I have set up ollama and models. Then we can discuss a plan to build a job application engine, that interact with once a week, to see where all the engine has applied for me. We can get new local models if necessary. Use jev if needed, multiple agents, mcps and tools. ,Anything and everything free is on the table. It should have access to my linkedin, indeed (for part time job search in the UK) and other job portals, I intend on it running 24/7 so 18 hours for main job search and 6bhours for part time.
The only time intend to stop is when I would play games. And I'll restart it once I am done. We can also do n8n, Rag also.
Ask me questions if you have doubts.

Linkedin Auto Apply, should not be done, It can send me a list of auto apply jobs with tailor made resumes and I will apply using linkedin auto apply, but for external links it should.

Stop linking google drive, nothing stays on cloud, everything on local device alone. I will give a 3/4 page master resume, along with readonly access to my github so it can add the right projects, and apply for me.

rbkasus will run this via systemd, and llm calls will be made to the gaming laptop (rbkmsi)

Explain further, what the issue is here. I think it should be fine right ? what is the alternative ?

YES, I should not get banned for any reason. No post should be made on my behalf, although maybe potential empployers connections can be sent a message letting them know of me.

Additional minute details like, my full name, and all that I'll feed into the engine. willingness to relocate, job application locations, visa status etc.


What I know about your setup
rbkmsi (gaming laptop, LLM host): MSI Vector 18HX AI A2XW — Core Ultra 9 275HX (24C/24T, up to 5.4 GHz), RTX 5070Ti 12 GB VRAM, 32 GB DDR5, 1 TB SSD, Windows 11 Home, Wi‑Fi 7, Thunderbolt 5, 2.5GbE. Ollama runs inside WSL, exposed over the tailnet via Tailscale Serve (WSL listens on 127.0.0.1:11435, tailnet address 100.93.206.16:11434), with OLLAMA_KEEP_ALIVE=-1 and OLLAMA_CONTEXT_LENGTH=24576. Installed models: qwen3-coder-64k (validated at a true 65k context, ~10.5 GB VRAM), qwen3-coder:30b, qwen3-coder:30b-16k, qwen3:14b, qwen3:14b-16k, gemma4:31b. We found earlier that the 30B coder variants sit at ~10.4 GB VRAM, so only one big model is resident at a time and swapping is slow.

rbkasus (server, will host the engine): 2018 Asus X510UNR, i5‑8250U (4C/8T), 24 GB RAM, Ubuntu Server 24.04 on a 1 TB HDD (~900 GB usable), Docker Compose running your *arr stack, Jellyfin, Immich, Minecraft and the OpenCode front end. You have a LaTeX resume template and a job_applications.csvjob_applications.csv tracker already.

Your answers, folded in
LinkedIn: no automated Easy Apply. Engine produces a weekly "apply these yourself" list with a tailored PDF per job; it auto-applies only where the posting leads to an external company/ATS page.

Storage: Google Drive dropped. Everything (master resume, GitHub index, vector DB, tracker DB, generated PDFs) lives on rbkasus. GitHub access via a fine-grained read-only token.

Runtime: systemd on rbkasus; all LLM calls go to rbkmsi over Tailscale (WireGuard-encrypted, still local).

Credentials — the actual issue, explained below.

No bans, no posts. Employer-contact messages: drafted, not sent (reasoning below).

Point 4: what the cookie problem really is
Storing your LinkedIn/Indeed session cookies locally on rbkasus is fine from a privacy standpoint — that part is not the issue. The problem is what a logged-in automated session does to your account:

LinkedIn's rules explicitly prohibit using "software, devices, scripts, robots or any other means" to access or automate the site, and enforcement is behavioural, not legal.

A headless Chromium on a Linux server, logged in as you, running 18 hours a day, with a device fingerprint LinkedIn has never seen before, is the exact signature they look for. The outcome is usually a "confirm it's you" checkpoint, forced 2FA, or a restriction — any of which also kills an unattended run at 3 a.m.

Cookies expire and get invalidated on checkpoints, so you'd be re-logging in constantly, which is itself a signal.

The alternative: never log in at all. Job discovery on LinkedIn and Indeed does not need an account. JobSpy is an open-source library that pulls postings from LinkedIn, Indeed, Glassdoor, Google Jobs and others without credentials. Combined with the official free UK APIs — Adzuna's API covers api.adzuna.com/v1/api/jobs/gb/search and Reed's free Jobseeker API — plus direct polling of company ATS boards such as Greenhouse's public boards-api.greenhouse.io/v1/boards/{token}/jobs endpoint, you get more coverage than a logged-in LinkedIn session would, with zero account risk. The only thing that ever touches your LinkedIn account is you, clicking Easy Apply during the weekly review. Your account is untouchable because it is literally never used by the engine.

Consequence for employer messaging (your point 5): sending LinkedIn messages requires that logged-in session, and automated messaging is one of the most aggressively enforced behaviours. My recommendation: the engine drafts a personalised message per shortlisted job (recruiter/hiring manager name where it can find one publicly), and you send them in the same weekly session. Still your call, but this is the line between "zero ban risk" and "some ban risk."

Proposed architecture
Everything below is free and self-hosted. Split into two machines and one clear boundary: rbkasus does everything except inference.

Discovery layer (no LLM needed, runs continuously)

Sources: JobSpy (LinkedIn guest, Indeed, Glassdoor, Google Jobs), Adzuna API, Reed API, gov.uk Find a Job RSS, and direct ATS feeds (Greenhouse, Lever, Ashby, Workable, SmartRecruiters — all public JSON, and all are places the engine can apply directly).

Two search profiles: main (18h window) and parttime (6h window), each with its own keywords, locations, radius, salary floor. Switch is time-of-day based, configurable.

Dedup by normalised company+title+location hash; store in a local Postgres (or SQLite) with the full posting text.

Rate limits per source with jitter; your home IP, no proxies, no CAPTCHA solvers. If a source throws a CAPTCHA, it backs off for hours rather than fighting it.

Knowledge layer (RAG)

Master resume (3–4 pages) chunked by role/project/skill; GitHub repos indexed via the API (READMEs, languages, topics, recent activity) into Qdrant or pgvector on rbkasus.

Embeddings via a small model on rbkmsi's Ollama (e.g. nomic-embed-text or bge-m3, both tiny next to your 30B models).

Hard rule enforced in prompts and by a validator: every bullet in a tailored CV must trace back to a retrieved chunk. No invented experience.

Reasoning layer (rbkmsi Ollama)

Stage A, cheap triage: qwen3:14b in JSON mode scores fit (0–100), extracts salary/location/visa-sponsorship/seniority signals, and classifies the apply route (Easy Apply vs external ATS vs email).

Stage B, tailoring for anything above threshold: a stronger general-purpose model. Your coder models are tuned for code, not prose; Qwen3-30B-A3B-Instruct-2507 is a MoE with only ~3B active parameters, so it runs fast while spilling into system RAM the same way your qwen3-coder:30b does, and it's available on Ollama. We'd validate it against gemma4:31b and qwen3:14b on a few real postings before committing.

Output: tailored CV rendered through your existing LaTeX template to PDF (tectonic in Docker), a cover letter, ATS-question answers, and a draft recruiter message.

Application layer (external links only)

Deterministic Playwright fillers for the big ATS platforms (Greenhouse, Lever, Ashby, Workable) — these forms are predictable, so no LLM browsing is needed.

For custom career pages: an LLM-driven browser agent. Skyvern is open-source, has a Playwright-compatible SDK, an MCP server, and a documented job-application pipeline; browser-use is the lighter alternative and works with Ollama models. I'd start with browser-use and move to Skyvern if reliability is poor.

Human pacing: cap of N applications/day (I'd suggest 10–15 to start), randomised delays, real Chromium under Xvfb rather than headless-shell. Anything that asks for a login, account creation (Workday), or a CAPTCHA gets screenshotted and parked in your weekly queue instead of being forced.

Confirmation tracking: a dedicated job-search email address that the engine reads over IMAP (read-only) so it can mark applications as confirmed / rejected / interview, and surface anything needing your reply.

Orchestration and your weekly interaction

n8n handles scheduling, the main/part-time window switch, pause/resume webhooks, retries, and the weekly digest. The heavy lifting (JobSpy, RAG, Playwright) lives in Python worker containers that n8n calls over webhooks — n8n is bad at long-running browser sessions, Python is good at it.

A small local dashboard (FastAPI + HTMX, on the tailnet) with four tabs: Applied (auto), Apply yourself (Easy Apply list with PDFs), Parked (needs you), Drafts (messages). Optional Telegram bot for the Sunday digest.

MCP servers for filesystem, Postgres, GitHub, and browser so OpenCode can also drive and debug the engine using the same tools.

Pause for gaming

One command (or a desktop shortcut on rbkmsi) hits an n8n webhook that stops the apply and tailoring queues, then runs ollama stop for the loaded model to free your 12 GB VRAM. Discovery keeps running because it needs no GPU. Resume reverses it. The engine also self-pauses any LLM stage if Ollama is unreachable, so if you just launch a game and forget, nothing breaks — it queues.

Questions before I write the build plan
Roles and keywords — this was the one question left unanswered. What titles/keywords for the main search (e.g. Java/Spring backend, Python/ML engineer, DevOps/Linux, NLP research?), and what counts as part-time (dev/freelance only, or also retail/tutoring/warehouse-type work)?

Time windows — when should the 6-hour part-time window run? Overnight UK time is my default suggestion, since part-time boards refresh mornings.

"Use jev if needed" — I'm not sure what "jev" refers to. Jan (the local LLM app), a specific library, or a typo?

n8n-centric or code-centric — n8n as the visible control plane with Python workers behind it (my recommendation), or skip n8n and do pure Python with APScheduler plus the dashboard? You said "we can also do n8n," so I want to confirm it's a want and not a maybe.

Employer messages — drafts only that you send (zero risk), or automated sending with a hard cap like 3/day (some risk)?

Dedicated email — are you willing to create a fresh address just for applications so the engine can read confirmations over IMAP? Reading your main inbox is the alternative but I'd rather not.

GitHub scope — public repos only, or private too (the fine-grained token can be limited to specific repos either way)?

Workday — many UK corporates use it and it requires per-employer account creation. Park those for you, or let the engine create accounts using the dedicated email?

Once you answer, I'll turn this into a staged build plan (milestones, compose stack, systemd units, agent breakdown) sized for OpenCode to implement on rbkasus.

No. We don't use it. Keep it only on SDA. the ssd is unreliable

Create a fork of this shared session.


