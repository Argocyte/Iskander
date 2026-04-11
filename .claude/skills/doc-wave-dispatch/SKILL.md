---
name: doc-wave-dispatch
description: Use when executing a documentation-only milestone — ADR writing, tracking file creation, GitHub issue filing, GitHub comments, cross-reference updates to existing files — where no code is written and no worktree is needed. Trigger phrases include "Q0 milestone", "write the ADRs", "file the issues", "post the comments", "documentation milestone", "coordination hub", or any plan phase whose deliverables are purely files and GitHub operations.
version: 1.0.0
---

# Documentation Wave Dispatch

## When This Applies

Documentation-only milestone work: ADRs, tracking files, SOUL.md cross-references,
plan/roadmap updates, GitHub issue filing, GitHub discussion/issue comments.

**No code writes → no worktree needed.** Skip `isolation: "worktree"` on all agents.

---

## Two-Wave Dispatch Pattern

Wave 1 and Wave 2 must be sequential (Wave 2 needs issue numbers from Wave 2 itself
to update the tracking file). Within each wave, agents run in parallel.

```
Wave 1 (parallel) — local file operations
  Agent A  →  Write new files (ADRs, specs, docs)
  Agent B  →  Create coordination/tracking hub
  Agent E  →  Update existing files (SOUL.md, plan.md, etc.)
        ↓
  Review confirmations — all return "filename → status ✓" only
        ↓
Wave 2 (parallel) — GitHub operations
  Agent C  →  Post comments on existing issues + discussions
  Agent D  →  File new issues (returns #N → title ✓)
        ↓
  Micro-update: fill real issue numbers into tracking file
```

---

## Agent Brief Format

Every agent prompt must be **self-contained**: no inherited session context.
Structure: **path** + **format reference** + **exact content spec** + **confirmation protocol**.

```
You are [doing X] for [project]. Worktree: [path].

Format reference: Read [existing file] first to match structure exactly.

[Detailed content spec per deliverable]

Confirmation protocol: return only `filename → created ✓` — NOT full file contents.
```

### Agent A — Writing new files (ADRs, docs)
- Always name a format reference file to read first (e.g., an existing ADR)
- List each file with its exact path and a 5-10 line content spec
- Return: one line per file

### Agent B — Tracking/coordination hub
- Name the pattern file to match (e.g., `phase-b-tracking.md`)
- Specify every section: hard dependencies, milestone table, issue cross-ref, discussion cross-ref, closed issues cited, out-of-scope reminders, new issues placeholder
- Return: one line

### Agent E — Existing file cross-references
- List each file + exactly what to add (and where in the file)
- "Read each file before editing" — state this explicitly
- Minimal targeted edits only — do not rewrite sections
- Return: one line per file, or "not found, skipped"

### Agent C — GitHub comments batch
- For **issues**: `gh issue comment <N> --body "..."`
- For **discussions**: GraphQL `addDiscussionComment` mutation
  - Get node ID first: `gh api graphql -f query='{ repository(owner:"...", name:"...") { discussion(number: N) { id } } }' -q '.data.repository.discussion.id'`
- Include the full comment body for each issue/discussion inline in the prompt
- Instruct: "check with `gh issue view` if in doubt — skip if a very similar comment already exists"
- Return: `#N → comment posted ✓` or `#N → skipped (duplicate)`

### Agent D — New issue filing
- Always run duplicate check first: `gh issue list --search "title words"`
- Use existing labels only — check with `gh label list`
- Include full body for each issue inline in the prompt
- Return: `#N — title → created ✓` or `skipped (duplicate found)`
- **After Agent D completes**: update tracking file's "new issues filed" section with real #N numbers

---

## Token Rules

| What | Do | Don't |
|------|----|-------|
| 4+ ADRs | Delegate to Agent A | Write in-context |
| 20+ GitHub comments | Delegate to Agent C | Write in-context |
| Issue filing | Delegate to Agent D | Write in-context |
| Tracking file | Delegate to Agent B | Write in-context |
| Agent outputs | Hold confirmations + #N numbers only | Hold full file contents |

**Main context holds:** plan file path + todos + confirmations + issue numbers.

---

## Pre-Dispatch Checklist

Before Wave 1:
- [ ] Confirm repo name: `gh repo view --json nameWithOwner -q .nameWithOwner`
- [ ] Resolve any user decisions that affect content (e.g. "which issue is superseded?")
- [ ] Identify one format-reference file per agent that needs to match existing style
- [ ] Confirm no worktree parameter on any Agent tool call

Before Wave 2:
- [ ] Wave 1 confirmations all received (no failed agents)
- [ ] For Agent C: have the full §6.3-style comment list ready inline
- [ ] For Agent D: have the full issue body list ready inline

After Wave 2:
- [ ] Update tracking file with real issue numbers (inline Edit or micro-agent)
- [ ] Mark todos complete

---

## Common Mistakes

**❌ Worktree on doc-only agents** — no code writes, no isolation needed, wastes setup time.

**❌ Letting agents return full file contents** — bloats main context. Confirmations only.

**❌ Wave 2 before Wave 1 complete** — tracking file needs real issue numbers from Wave 2;
filing issues before the tracking file exists means the placeholder section is stale instantly.

**❌ Vague agent content specs** — "write an ADR about the ops stack" → agent guesses.
Correct: list every section heading, every cross-reference, every issue number to cite.

**❌ Discussion comments via `gh issue comment`** — discussions need GraphQL.
Issues need `gh issue comment`. They are different API surfaces.

**❌ Filing issues without dedup check** — always `gh issue list --search` first.

---

## Real Example (Phase C.5 Q0, 2026-04-11)

Wave 1 (parallel, ~3 min):
- Agent A → `docs/adr/0003`, `0004`, `0005`, `0006-stub` — 4 files created ✓
- Agent B → `.claude/phase-c5-tracking.md` — created ✓
- Agent E → `steward/SOUL.md`, `clerk/SOUL.md`, `plan.md`, `roadmap.md`, `phase-b-tracking.md` — 5 files updated ✓

Wave 2 (parallel, ~12 min):
- Agent C → 21 issue comments + 5 discussion comments — 26 posted ✓, 0 skipped
- Agent D → 10 new issues → #134–#143 ✓, 0 duplicates

Tracking file updated with #134–#143 via micro-agent.

Total main-context output budget: ~500 tokens of confirmations + issue numbers.
