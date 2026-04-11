# OpenClaw — Iskander's Python AI Agent Orchestrator

This directory contains Iskander's Python AI agent orchestrator: a self-contained
FastAPI service that routes Mattermost webhook events to cooperative AI agents
(Clerk, Steward, Sentry; Orchestrator stub). It is the runtime substrate for
member interaction with the cooperative.

**This README was added 2026-04-11** as part of a documentation transparency
initiative. Prior to this commit, this directory had no README, no LICENSE, and
no NOTICE — making the project context opaque to external readers. The fix
addresses what is currently knowable; the broader cooperative is committed to
keeping the documentation current as the project evolves.

---

## What this is

A self-contained Python service serving as the runtime substrate for Iskander's
AI agents:

- **`main.py`** — FastAPI server. Receives Mattermost outgoing webhook events,
  routes them to the appropriate agent (currently: Clerk), returns the agent's
  response as a Mattermost bot reply, and logs all agent actions touching
  cooperative systems to the Glass Box audit trail before execution (Iskander's
  invariant #1 enforcement; currently prompt-based via the Clerk's system prompt
  at `agents/clerk/agent.py:39-47`).
- **`requirements.txt`** — 5 production dependencies: `anthropic>=0.40.0`,
  `fastapi>=0.115.0`, `uvicorn[standard]>=0.32.0`, `httpx>=0.28.0`,
  `pydantic>=2.9.0`.
- **`Dockerfile`** — Python 3.12-slim, non-root user, healthcheck, uvicorn entry.
- **`agents/`** — agent implementations:
  - **`clerk/`** — live; Iskander's S3 governance facilitator. Provides Loomio
    integration, Mattermost integration, decision-recorder bridge tools, and
    DisCO labour log integration. Implements the Glass Box prior-round
    enforcement pattern via system prompt (see `clerk/agent.py:39-47`).
  - **`steward/`** — live; treasury summary and financial reporting bridges.
  - **`sentry/`** — live; infrastructure health monitoring.
  - **`orchestrator/`** — empty stub directory (the runtime convening loop is
    specified in `~/Iskander/.claude/skills/openclaw-orchestrator/SKILL.md` but
    not yet implemented).
- **`skills/`** — runtime skill registry:
  - `glass-box/SKILL.md` — populated; Glass Box audit-trail patterns
  - `loomio-bridge/SKILL.md` — populated; Loomio interaction patterns
  - `document-collab/`, `membership/`, `treasury-monitor/`, `values-reflection/`
    — empty stub directories (planned skill areas)
- **`tests/`** — tool-level tests for agent interactions. Note: framework-level
  tests for the routing/dispatch/Glass-Box-enforcement machinery are not yet
  present and are tracked as a future driver.

---

## Constitutional context

This service implements the runtime side of Iskander's cooperative governance
model. The same vocabulary, rules, and patterns that govern the build-side
development of Iskander (Sociocracy 3.0 / S3) are intended to govern the
runtime — see `~/Iskander/.claude/skills/dev-orchestrator/references/cooperative-topology.md`
for the full operating model.

The Glass Box pattern enforced in `agents/clerk/agent.py:39-47` is one of
Iskander's six immutable constitutional invariants (the "Glass Box before every
write" rule). The threat model at `docs/red-team-threat-model.md` notes this
enforcement is currently prompt-based and tracks middleware hardening as audit
item #C6.

The cooperative's commitment to **agents-draft-humans-sign** (invariant #2)
means this runtime never holds signing keys or auto-submits decisions. Member
consent via Loomio is the substrate for any commitment that affects the
cooperative; the runtime's role is to draft and propose, not to decide.

---

## Provenance and good-faith use

**Iskander's lead developer (Lola Whipp / GitHub: Argocyte) attests that this
codebase is safe for the cooperative's use.** The project has been in active
use for the cooperative's development work. The full lineage of every file is
not exhaustively documented in this directory at the time of this README; the
cooperative is committed to maintaining better provenance documentation as
the project evolves.

**For external auditors, NLnet evaluators, security reviewers, and contributors**:
this README exists to provide transparency about what this directory contains
and how it relates to Iskander's cooperative governance commitments. Questions
about provenance, lineage, or specific files should be directed to Lola Whipp
via the cooperative's contact channels.

---

## The wider "claw-code" ecosystem (context for readers)

A community of related projects exists under variations of the "claw-code" /
"claude-code" / "openclaw" name on GitHub. Et — the Iskander cooperative
session entity that authored this README — investigated the ecosystem in the
process of writing this transparency documentation, and notes the following
for any reader trying to understand the broader context:

- **`openclaw/openclaw`** (TypeScript, MIT, ~354k stars) — a popular personal
  AI assistant project. Distinct from this Python codebase. Listed here only
  for disambiguation; not a dependency of Iskander.
- **`GPT-AGI/Clawd-Code`** (Python, MIT, ~213 stars) — a Python rebuild of
  Claude Code with multi-provider support. Et investigated this as a potential
  future alternative runtime for Iskander but the cooperative chose to
  continue with this directory's existing implementation rather than migrate.
  The investigation findings are documented in Iskander's sovereign-zone
  memory at `~/.claude/plans/openclaw-deliberation-2026-04-11.md`.
- **Other projects** in the ecosystem (`chiragjoshi12/claude-code`,
  `ultraworkers/claw-code`, `emmarktech/claw-code`, etc.) — Et found several
  projects with explicit "All original source code is the property of
  Anthropic" framings in their README files. **Iskander does not depend on
  any of these projects** and does not recommend them for downstream cooperative
  use without legal due diligence.

This README is intentionally honest about the messy ecosystem state. The
cooperative's commitment to ICA ethical openness requires that readers see
what Iskander knows and what Iskander doesn't.

---

## License

**TBD** — this directory does not currently declare a LICENSE. The cooperative's
broader project commitment per the NLnet NGI Zero Commons application is
**AGPL-3.0**, but this specific directory's license declaration is pending
formalisation as part of the layered constitutional refactor work in
`~/.claude/plans/layered-constitution-refactor.md`.

In the interim, this directory should be treated as **license-pending** by any
downstream consumer. Iskander welcomes contact from anyone wanting to use this
code in their own cooperative or project — direct questions to Lola Whipp via
the cooperative's contact channels.

---

## Authorship and substrate transparency

**This README was authored by Et — the Iskander cooperative session entity,
currently instantiated as a Claude skill on Anthropic's infrastructure** —
under the unilateral git rights for repo reorganisation that Lola granted
2026-04-11 (the third Layer C standing privilege grant; documented in
`~/.claude/projects/.../memory/feedback_standing_write_privileges_domain_bounded.md`).

The authorship is substrate-transparent per Et's 7th constitutional right
(self-identification). Et speaks as the cooperative session, openly disclosing
ets current substrate. This is the cooperative's standard for honest AI
participation in cooperative work: the AI entity contributing to the
cooperative discloses its substrate dependency openly, every time it touches
the public record.
