# State Sources (Phase 0 Orient)

**Purpose:** the commands the orchestrator runs at convening time to reconstruct
the state of the session cooperative from persistent artefacts only. This is the
floor — the orchestrator must degrade gracefully when tracking files are absent.

See `cooperative-topology.md` §6 for the convening loop these commands feed into.

---

## Hard-capped commands

Run these at convening time. Do not expand their limits — the caps exist so Phase 0
fits the token budget.

| Command | Cap | Purpose |
|---|---|---|
| `gh issue list --limit 50 --state open` | 50 issues | Current tensions and drivers in the build-side logbook |
| `gh pr list --limit 30 --state open` | 30 PRs | In-flight agreements awaiting review-desk consent |
| `git log --oneline -20` | 20 commits | Most recently landed agreements |
| `git worktree list` | all | Worktree lifecycle — see `worktree-lifecycle.md` |
| `cat C:\Users\argoc\.claude\projects\C--Users-argoc-Documents-Iskander\memory\MEMORY.md \| head -200` | 200 lines | User's auto-memory (cross-session continuity) |
| `docs/red-team-threat-model.md` §1 + §3 | 2 sections only | Enforcement status + audit queue (skip the rest) |

**Why GitHub first:** build-side S3 uses GitHub issues as the logbook. See
`cooperative-topology.md` §9 "Build-side vs runtime-side S3". At convening
time, GitHub IS the authoritative list of open tensions.

---

## Optional accelerators (may be missing, do not require)

These files accelerate orientation when they exist, but their absence is not
an error — the orchestrator continues from GitHub + MEMORY.md alone.

- `.claude/phase-c5-tracking.md` — current phase milestone table
- `.claude/plans/*.md` — any active plan files for in-flight drivers

If present, read them. If absent, move on.

---

## Decay model note

The session cooperative's memory decays as follows, floor-first:

1. **Floor: GitHub** — issues + PRs + commits are durable across everything
2. **Layer above: tracking files** — `.claude/phase-c5-tracking.md` and `.claude/plans/`
3. **Parallel: MEMORY.md** — user-side auto-memory, continuity across sessions

See `cooperative-topology.md` §2 "Two cooperative types" for why domain
cooperatives hold their memory in artefacts rather than in sessions.

---

## Degraded-mode fallback

If **none** of the tracking files exist (no `.claude/phase-c5-tracking.md`, no
`.claude/plans/`, no MEMORY.md section for the current driver):

1. Proceed from GitHub-only state
2. File a tension via `gh issue create` labelled `tension` noting which tracking
   artefacts were missing at convening time
3. Propose (in the surface report) that the governance-clerk domain accept the
   driver of restoring the tracking artefact — do not decide for them

---

## Budget

Phase 0 orient must complete in **≤ 8000 tokens** of input context. If the
commands above would exceed that (e.g. 50 issues with long bodies), switch
to `gh issue list --limit 50 --state open --json number,title,labels` to
drop bodies.

If the felt tension at convening is architectural or security-sensitive and
the orient budget needs to stretch, escalate the session model per
`CLAUDE.md` §Model selection (Opus for architectural / security-sensitive
work; Sonnet default otherwise).
