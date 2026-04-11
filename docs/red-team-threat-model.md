# Iskander Red Team Threat Model

**Living document** — updated as features land. This is the authoritative record of the security posture of the Iskander cooperative OS. Red Team sessions append to it; they do not maintain parallel working notes.

**Last updated:** 2026-04-11
**Current phase focus:** Phase C hardening + Phase B pre-audit preparation
**Role:** Iskander Red Team AI Lead (autonomous between check-ins, see `CLAUDE.md`)

---

## 1. Invariant enforcement status

The five invariants from `CLAUDE.md` are load-bearing. This table is the source of truth for whether each is actually enforced in code, not just claimed.

| # | Invariant | Status | Evidence / Caveat |
|---|---|---|---|
| 1 | Glass Box before every write | 🟢 Enforced (prompt-based) | `src/IskanderOS/openclaw/agents/clerk/agent.py:39-47` — system-prompt sequencing; `src/IskanderOS/services/decision-recorder/main.py:44-78` — rate-limited `/log` endpoint. **Caveat:** enforcement is prompt-based for Clerk, not middleware. See Phantom Invariant note below. |
| 2 | Agents draft, humans sign | 🟢 Enforced | `src/IskanderOS/legacy/backend/finance/tx_orchestrator.py:1-60` — node holds `propose_key` only, no signing libs imported, `draft_batch()` returns unsigned Gnosis Safe JSON |
| 3 | Constitutional Core immutable | 🟡 Code-level enforced, manifest layer PHANTOM | `src/IskanderOS/legacy/backend/governance/policy_engine.py:45-67` — hardcoded ICA principles, no bypass. **BUT** `:126-148` loads `governance_manifest.json` by path with **no SHA-256 verification**. See Phantom Invariant #A2. |
| 4 | Tombstone-only lifecycle | 🔴 PHANTOM in Phase C services | Zero `deleted_at\|tombstone\|is_deleted` matches across `src/IskanderOS/services/decision-recorder/`. Legacy `schemas/diplomacy.py` and `schemas/knowledge.py` have the pattern; new services did not inherit it. See Phantom Invariant #A1. |
| 5 | Boundary layer sequential (5 gates) | 🟡 Coded, not integrated | All five modules exist in `src/IskanderOS/legacy/backend/boundary/` with `BoundaryVerdict` dataclass; `BoundaryAgent.get_instance()` uses singleton pattern for sequential execution. **BUT** OpenClaw does not call it; no federation inbox is wired; activates at Phase B Week 7 per `docs/plan.md:307`. |

### Phantom invariants

A **phantom invariant** is a claimed protection with no corresponding code. These are the highest-risk findings because developers, auditors, and funders all assume coverage that doesn't exist.

**Currently confirmed (as GitHub issues):**

- **#147 — Tombstone-only lifecycle missing in decision-recorder** (invariant #4) — filed 2026-04-11
- **#148 — Governance manifest has no SHA-256 lock** (invariant #3, manifest layer) — filed 2026-04-11
- **#160 — Glass Box write path missing in boundary layer federation ingestion** (invariant #1, boundary path) — filed 2026-04-11. `BoundaryVerdict.agent_actions` are produced by the five gates but never persisted to the decision-recorder. The invariant is enforced inside the gate pipeline and then silently dropped at the handoff to the federation router. Phase B scope only (boundary layer not yet wired), but must be resolved before Phase B Week 7 activation.

---

## 2. Phase health summary

### Phase C (MVP): 🟢 Production ready with caveats

All critical findings from the 2026-04-09 audit session have landed fixes:

| Component | Commit(s) | Status |
|---|---|---|
| Clerk agent (14 findings: 3C, 8M, 3L) | `c308da8`, `760c7ab` | All fixed |
| Decision recorder (8 findings: 1C, 5M, 3L) | `0904359` | Critical + priority medium fixed |
| Steward agent (design review) | `a35ff3a` | Approved — read-only, aggregate-only |
| S3 Sociocracy authorization (5: 3M, 2L) | `f63bfa3`, `2e59498` (#56, #92) | Fixed |

**Remaining Phase C gaps:** tombstone retrofit (#A1), manifest lock (#A2), audits for new agents (#48, #50, #51), installer (#45), dependency bump security delta, Clerk system-prompt manipulation threat model.

### Phase B (Smart Contracts + Federation): 🟡 Design blockers

| Blocker | Tracking | Gating |
|---|---|---|
| Federation security model | #104 | Phase B start |
| Federation @mention spec rework (10 gaps) | #73 | Phase B federation activation |
| Asymmetric GTFT decay formal analysis | #111 | Federation reputation protocol |
| Smart contract audit firm selection | (no issue) | Any smart contract deployment |
| MACI circuit expert review | `docs/plan.md` | Trusted setup ceremony (Phase B Week 6) |
| Boundary layer activation checklist (8 blockers incl. Glass Box phantom) | #160 | Federation inbox activation (Phase B Week 7) |
| MACI nullifier double-voting verification | #99 | Voting deployment |
| Tombstone retrofit (#A1) | (filed this session) | Audit-correction workflow |
| Governance manifest SHA-256 lock (#A2) | (filed this session) | Phase B Constitution.sol anchoring |

### Dependency security delta (recent, not yet audited)

- `cryptography` 43.0.1 → 46.0.7 (#85, merged) — crypto library, any CVEs? breaking changes in Ed25519/HTTP-signatures?
- `web3` 7.2.0 → 7.15.0 (#86, merged) — blockchain library, any CVEs?
- `orjson` (#87, merged) — JSON serialization

---

## 3. Audit queue (ordered by risk × immediacy)

### Phase C hardening track

1. **C1 — Decision-recorder new features** (labour tracking `b06ac4d`, accountability tracking `fda0701`) — Glass Box coverage, authz, input validation, rate limiting
2. **C2 — steward-data service** (`src/IskanderOS/services/steward-data/`) — read authz, query-injection surface, verify "reads don't require Glass Box" decision applied consistently
3. **C3 — Dependency bump security delta** — CHANGELOG review, no breaking Ed25519/HTTP-signature changes
4. **C4 — New agents (Librarian #51, Sentry #50, Wellbeing #48)** — Glass Box enforcement, tool registry review, prompt-injection surface
5. **C5 — `curl|sh` installer (#45)** — supply-chain: fetch sources, signature verification, root-level operations. **High priority: NLnet funding promises this path.**
6. **C6 — Clerk system-prompt manipulation audit (Opus, architectural)** — Glass Box sequencing is prompt-based, not middleware. Design a middleware gate or formally accept risk with compensating controls.

### Phase B pre-audit preparation track

7. **B1 — Federation @mention spec rework (#73)** — deepen existing 10-gap list (identity spoofing, privacy DB enforcement, context-gating, OIDC sub stability, trust model, enumeration, approval abuse, name collision, onboarding, rate limit tuning)
8. **B2 — Pre-Phase-B boundary layer activation checklist** — inventory the 5 gates in `legacy/backend/boundary/`, identify missing tests, file one tracking issue
9. **B3 — MACI circuit readiness review (Opus)** — checklist of what MUST be verified before trusted setup ceremony (Poseidon, BabyJubJub, Groth16). Scope-setting for an external cryptographer; do not attempt verification.
10. **B4 — Asymmetric GTFT decay formal-analysis scoping (#111)** — list game-theoretic questions, check peer-project work (DarkFi, DisCO), propose in-house / Alyssa / external commission
11. **B5 — Smart-contract audit firm shortlist** — research-only: FOSS-aligned Solidity audit firms that serve cooperative / public-goods projects

---

## 4. Deferred findings (with justification)

These are risks that have been surfaced and explicitly accepted or deferred with a documented reason. The Red Team AGREES with each deferral below until the stated condition changes.

| # | Finding | Deferred to | Justification | Red Team concurrence |
|---|---|---|---|---|
| DR-M2/M3 | Per-member JWT auth on decision-recorder `/log` reads | Phase B | NetworkPolicy guards Phase C (single coop); per-member JWT creates circular dependency with Authentik; revisit when member-facing Glass Box UI is built | 🟢 Agree |
| DR-M4 | Encrypt `raw_payload` at rest in decision-recorder | Phase B | Phase C is single self-hosted coop on the coop's own server; becomes mandatory when federation introduces off-coop storage | 🟢 Agree |
| DR-M6 | Re-hash IPFS CID verification on read | Not planned | Expensive; threat model requires DB compromise for attack to work; IPFS provides independent verification | 🟢 Agree |
| Clerk #12 | Weak bot-loop prevention if `MATTERMOST_BOT_USER_ID` unset | Fixed by requiring the env var | — | 🟢 Resolved |
| Clerk #13 | HTTP timeouts strict for slow networks | Fixed by making configurable | — | 🟢 Resolved |

---

## 5. Findings history (durable only)

Red Team sessions append to this section. Ephemeral working notes live in subagent outputs and get consolidated here, not kept in `.claude/`.

### 2026-04-09 — Initial comprehensive audit

**Session:** 17:30–23:45 UTC, 6.25 hours continuous monitoring
**Coverage:** Clerk, Decision Recorder, Steward, S3 Governance, K8s Architecture
**Issues found:** 27 (4 Critical, 16 Medium, 7 Low)
**Resolution rate:** 24/27 resolved, 3 deferred with justification (see Section 4)
**Commits landed:** `c308da8` (Clerk hardening), `0904359` (Decision-Recorder), `a35ff3a` (Steward threat model applied), `b8b202b` (S3 patterns), `f63bfa3` + `760c7ab` + `2e59498` (#56, #92 fixes)

Key architectural wins from this session:
- **Glass Box sequencing state-machine rewrite** — `CLAUDE.md` invariant #1 was initially bypassable because LLM tool-call ordering didn't match the precondition check. Fix forced glass_box_log into a separate tool-use round before writes.
- **Kubernetes Secrets for API keys** — moved `LOOMIO_API_KEY` and `MATTERMOST_BOT_TOKEN` out of env vars. OAuth2 rotation still owed for Phase B.
- **Webhook signature enforcement made mandatory** — both Clerk and decision-recorder now fail to start without `LOOMIO_WEBHOOK_SECRET`.
- **Rate limiting (sliding window)** — 20/min for Clerk, 60/120/min for decision-recorder webhook/query.
- **S3 Sociocracy authorization** — domain/circle membership checks, ownership checks on tension update, enumeration prevention on `list_tensions`, future-date validation on review dates.
- **Polis auto-approve bypass removed** (#92) — critical governance bypass identified and fixed.

### 2026-04-10 — Federation specs review (#72, #73)

- **#72 Smart @Mention Autocomplete:** 🟡 Approve with mitigations — member enumeration cap (max 3 suggestions), rate limit (100/min per user), fuzzy-match algorithm specification, bot-behavior ban on autocomplete, accessibility (ARIA live regions, keyboard nav).
- **#73 Federation-Wide @Mention System:** 🔴 Major rework required. 10 critical/medium gaps: federation identity spoofing (two coops same name), member-controlled privacy with DB constraint, rate-limit tuning, context-gating precision, name collision UI, approval abuse dedup, OIDC sub stability SLA, enumeration prevention (no public list), federation trust model (home-coop authoritative), federation onboarding flow. **Verdict: treat as Phase B specification, not Phase C implementation.**

### 2026-04-10 — PR and feature second-pass review

**Session:** 22:00–23:45 UTC
**Outcome:** Phase C deployment approved; 2 open PRs reviewed; continuous monitoring active

- **PR #69 — Steward-Data Service (Issue #66):** Approved for merge. Read-only HTTP wrapper over `iskander_ledger`. Four endpoints (`/treasury/summary`, `/treasury/surplus-ytd`, `/treasury/recent-activity`, `/compliance/deadlines`). Bearer token auth. PostgreSQL role is SELECT-only. NetworkPolicy restricts access to OpenClaw pod. 21 unit tests including privacy/PII-absence checks. Verdict: aggregate-only, no individual member data, production-ready.
- **PR #71 — Wellbeing Agent Design Spec (Issue #70):** Approved with mitigations. Six concerns raised: (1) old-name exposure on name changes — standard patterns, fixable; (2) Authentik idempotency — verify ETag support; (3) redaction completeness for regex word boundaries + Unicode; (4) Mattermost permissions scoping; (5) Loomio PATCH endpoint stability; (6) OIDC sync window timing risk. Design approved; implementation requires architectural answers first. **Phase B implication:** federation @mention redaction adds significant scope — see #73 review.
- **Phase C launch recommendation at the time:** 2026-04-12 (Friday) pending steward-data merge and wellbeing architectural questions. *(Red team notes this was a recommendation from the 2026-04-10 session; current state is tracked in GitHub issues, not here.)*

### 2026-04-11 — Phantom invariant discovery + consolidation (this session)

- Direct code inspection confirmed two phantom invariants (see Section 1): tombstone missing in decision-recorder (#147) and governance manifest loaded without SHA-256 lock (#148).
- Consolidated 10 prior session artifacts (`.claude/RED_TEAM_*.md`, `.claude/red-team-*.md`) into this document. Ephemeral files deleted after migration.
- Plan approved in `C:\Users\argoc\.claude\plans\imperative-puzzling-cookie.md`.
- Phase focus: Phase C hardening + Phase B pre-audit preparation in parallel via subagents.

### 2026-04-11 — C1: Decision-recorder new features audit

**Scope:** Commits `b06ac4d` (DisCO four-stream labour tracking) and `fda0701` (accountability tracking). Glass Box enforcement, authz, input validation, rate limiting, and write-tool ordering on the new endpoints.

**Coverage:** `src/IskanderOS/services/decision-recorder/main.py`, `db.py`, `src/IskanderOS/openclaw/agents/clerk/agent.py`, `src/IskanderOS/openclaw/agents/clerk/tools.py`.

**Issues filed by C1:** 1 MEDIUM (plus 1 LOW accepted as consistent with existing design).

| # | Title | Class | Severity |
|---|---|---|---|
| #151 | System prompt critical-ordering rule omits new write tools (`dr_update_accountability`, `log_labour`) | Defence-in-depth (prompt ↔ code drift) | MEDIUM |

**Key findings:**

1. **#151 — System prompt stale relative to `_WRITE_TOOLS`.** `_WRITE_TOOLS` set in `agent.py:71–80` correctly includes `dr_update_accountability` and `log_labour`, and the code-level prior-round Glass Box guard applies to both. But the human-readable *Critical tool ordering rule* in the system prompt at `agent.py:41` still lists only the original six write tools. Defence-in-depth gap: if the code guard regresses in a future refactor, the model has no explicit instruction to catch the gap. Also a maintenance hazard — future tool additions risk the same silent drift. Recommendation: add a CI lint asserting `_WRITE_TOOLS ⊆ prompt_listed_tools`.

2. **C1-2 (not filed) — `GET /labour` and `GET /labour/summary` lack internal-caller gate.** When `X-Actor-User-Id` is absent, `GET /labour` (`main.py:793`) returns all members' records and `GET /labour/summary` (`main.py:829`) returns cooperative-wide totals. Inconsistent with `GET /tensions`, which scopes by actor header when present. Design-consistent with ICA P1 transparency model and the K3s NetworkPolicy isolation, so C1 accepted it as-is — **correct remediation path is Phase B RBAC**, tracked elsewhere. Noted here as a known divergence to reconcile when Phase B RBAC lands.

**Good practices confirmed:**
- **Glass Box invariant on write path:** `POST /labour` calls `_verify_internal_caller` first (`main.py:759`); `tools.py:477` correctly marks `log_labour` as Glass Box required; `_WRITE_TOOLS` in `agent.py:79` includes it. Same pattern for `PATCH /decisions/{id}/accountability` (`main.py:489`) and `dr_update_accountability` (`agent.py:78`). Code-level enforcement is intact; only the prompt guidance drifted.
- **Input validation:** New Pydantic schemas use explicit `max_length` bounds. `hours` validated as decimal `≥ 0.25` and `≤ 24`. Status enums validated against `frozenset` allowlists on both client (`tools.py:539–543`) and server (`main.py:454–458`).
- **Rate limiting:** Both new GET endpoints use `_rate_check` with the existing `_QUERY_MAX` limit (`main.py:809`, `main.py:841`); `POST /labour` relies on internal-caller gating.
- **Actor cross-check:** `POST /labour` enforces `member_id == X-Actor-User-Id` when header is present (`main.py:761–765`). `PATCH /decisions/{id}/accountability` enforces `updated_by == X-Actor-User-Id` (`main.py:490–495`).
- **Error hygiene:** No stack traces or internal details leaked in error responses; all static strings.
- **DB schema:** `LabourLog` has appropriate indexes on `member_id`, `value_type`, `logged_at`. `accountability_*` columns added to `Decision` with nullable semantics and `default="not_started"`.
- **Tombstone invariant (#147):** No new delete paths introduced. `LabourLog` has no delete endpoint; the existing tombstone gap from #147 is unchanged in scope by this commit pair.
- **ICA traceability:** Labour tracking → ICA P2/P3/P7. Accountability tracking → ICA P2 (agreements kept).

**Red Team verdict:** Both commits are production-safe. #151 is a cheap defence-in-depth fix that should land before the next `agent.py` edit to prevent further drift. The `GET /labour` transparency design is a valid S3/P1 choice but must be re-examined when Phase B RBAC lands.

**Provenance:** Subagent C1 dispatched 2026-04-11, output captured post-compaction. Full details in `gh issue view 151`.

**Note on parallel work:** Issues #149 (circle-membership authz on `log_tension`) and #150 (tension status state machine + history column) were filed at the same time by a separate review-leader session referenced in #146, *not* by this C1 audit. They are independently valuable residuals from the 2026-04-09 S3 audit (#56) and are tracked for Phase C hardening alongside the C1 output. Red Team concurs with both: #149 should be resolved before any ≥2-circle deployment; #150 is tombstone-adjacent and should be scoped alongside the #147 retrofit.

### 2026-04-11 — C5: `curl|sh` installer audit

**Scope:** Red Team audit of the landed installer implementation — the primary install path promised in the NLnet funding application. Every cooperative installing Iskander will execute this on their own server.

**Coverage:** `install/install.sh`, `install/playbook.yml`, `install/roles/prerequisites/tasks/main.yml`, `install/roles/secrets/tasks/main.yml`, `install/roles/secrets/templates/generated-values.yaml.j2`, `install/roles/helm-deploy/tasks/main.yml`, `install/roles/first-boot/tasks/main.yml`.

**Issues filed:** **#152–#158** (7 individual issues by the original C5 subagent) + **#159** (umbrella issue covering all 10 findings, filed by the Red Team AI Lead after the subagent was blocked). Labels on all: `red-team`, `safety`, `phase-c`. Cross-reference #159 for full remediation priority ordering.

| # | Individual finding |
|---|---|
| #152 | Shell injection via `eval` in `prompt()` — user input executed as shell code (I7) |
| #153 | Nested `curl\|sh` — K3s and Helm fetched without integrity verification (I1) |
| #154 | `generated-values.yaml` persists on disk with all cooperative secrets after install |
| #155 | Ansible and pip dependencies unpinned — supply chain via dependency confusion (I2, I6) |
| #156 | No pipe-to-shell safeguard — partial download executes as shell code (extends I1) |
| #157 | `admin_email` stored in plaintext ConfigMap; credential reuse in generated values (I10 extension) |
| #158 | Installer lacks SBOM, downgrade protection, and fetch-then-verify documentation (I9 extension) |
| #159 | Umbrella — all 10 findings with remediation priority ordering, including I3, I4, I5 |

**Severity summary (re-run confirmed):** 2 CRITICAL, 3 HIGH, 2 MEDIUM (individual issues #152-#158) + 3 additional medium/low findings in umbrella #159. No single item is operationally blocked for a single-coop install, but the combination is indefensible for public NLnet milestone delivery without the two CRITICALs fixed.

**Findings:**

| ID | Issue | Finding | Severity | Class |
|---|---|---|---|---|
| I1 | #153 | Nested unverified `curl\|sh` — K3s `latest`, Helm from `main` branch, Traefik CRDs `kubectl apply` with silent `\|\| true` — any CDN/GitHub compromise silently owns every cooperative server on install | **CRITICAL** | Supply chain |
| I7 | #152 | `eval "$var_name=\"${value:-$default}\""` in `prompt()` — shell-metacharacter input gives root RCE; installer explicitly requires root or passwordless sudo | **CRITICAL** | Injection |
| I3/I4 | #154 | `generated-values.yaml` persists on disk with all cooperative secrets after install; verbose Ansible log (`/var/log/iskander-install.log`) may also capture them | **HIGH** | Credential exposure |
| I2/I6 | #155 | Ansible and pip dependencies unpinned — `pip install -q ansible kubernetes` no pins, no `--require-hashes`, runs as root | **HIGH** | Supply chain |
| I5b | #156 | No pipe-to-shell safeguard — partial HTTP download executes as shell; no `trap` handler to scrub secrets on interrupt | **HIGH** | Supply chain / integrity |
| I8 | #157 | `admin_email` stored in plaintext ConfigMap; credential reuse in `generated-values.yaml` | MEDIUM | Secret hygiene |
| I9 | #158 | Installer lacks SBOM, downgrade protection, and fetch-then-verify documentation | MEDIUM | Supply chain / transparency |
| I5 | #159 | **Cloudflare tunnel is the default** — proprietary SaaS dependency violates CLAUDE.md FOSS-first rule and ICA Principle 4 | MEDIUM | FOSS-rule violation |
| I10 | #159 | Nextcloud + Beszel admin passwords reuse `pg_root_password` | LOW | Secret hygiene |
| I11 | #159 | No pre-install disclosure/confirmation gate | LOW | Informed consent |
| I12 | #159 | No uninstaller or rollback path | LOW | Operator experience |

**Highest-severity concerns:**

1. **I1 — nested curl|sh.** Four unverified remote executions run as root during a single install. A compromise of any of `get.iskander.coop`, `get.k3s.io`, `raw.githubusercontent.com/helm/helm`, or the Traefik CRD host yields root on every cooperative that installs Iskander. Helm fetched from `main` branch (not a pinned tag) is the weakest link.
2. **I3 — secret leakage via install log.** `ansible-playbook -v 2>&1 | tee /var/log/iskander-install.log` with default 644 permissions. Operators routinely share install logs when asking for help; 11 generated secrets pass through Ansible `set_fact` and can be printed in verbose output.

**FOSS-rule violation:**

**I5 — Cloudflare tunnel is the default ingress** when no `--domain` is passed. This directly violates:
- `CLAUDE.md` "No proprietary APIs, no SaaS dependencies, no vendor lock-in"
- ICA Principle 4 (Autonomy and Independence)
- NLnet funding criteria

A warning is printed but the operator is given no FOSS alternative. Correct default must be Caddy + DNS-01 or Traefik; Cloudflare must be an explicit `--ingress=cloudflare` opt-in.

**Remediation priority (from #159):**
- **P0 (funder-facing blockers):** I1 (version pins + K3s SHA-256 verification + GPG-signed installer releases), I3 (strip secrets from log + mode 600), I5 (FOSS ingress default)
- **P1:** I2, I6 (pins + hash-verified requirements lockfile), I7 (one-line `eval` → `printf -v`)
- **P2:** I4, I10, I8
- **P3:** I9 (ship `install/uninstall.sh`)

**Good practices confirmed by re-run audit:**
- `generated-values.yaml` written with mode `0600` (owner-readable only) — correct
- Secrets generated with `openssl rand` (cryptographically sound entropy)
- Idempotency check via K8s ConfigMap marker prevents secret regeneration on re-run — preserves existing cooperative secrets correctly
- Helm upgrade path uses `--reuse-values` — avoids clobbering existing secrets
- Separate PostgreSQL passwords generated per service (partial blast-radius isolation)

**Red Team verdict:** **Major-rework-before-NLnet-release.** The CRITICAL shell injection (#152) and nested unverified curl|sh (#153) make the installer unsafe for any public cooperative deployment and must be fixed before any NLnet milestone delivery. P0: #152, #153, #154 (credential scrub on exit). The FOSS-rule violation (#159, Cloudflare default) is also a must-fix before the project can honestly claim FOSS compliance to funders. Once these three are resolved, the installer is defensible for cooperative pilot use.

**ICA traceability:**
- Principle 2 (Democratic Member Control) — I1, I3 (informed control requires uncompromised software + intact credentials)
- Principle 4 (Autonomy and Independence) — **I5 directly** (default Cloudflare dependency)
- Principle 5 (Education and Information) — I4, I8 (silent failures deny operators the information they need)

**Provenance:** Subagent C5 re-dispatched 2026-04-11 after the first dispatch's output was lost. Second run delivered the full audit; Red Team AI Lead filed #159 on its behalf (Bash permission in subagent context was denied).

### 2026-04-11 — B1: Federation @mention spec deeper review

**Scope:** Additive to the 2026-04-10 10-gap review. Seven new attack classes not covered by the prior 10 gaps, derived from examining the spec, `federation_mention_spec.md`, and the session's own phantom-invariant findings (#147, #148).

**Comment posted:** [#73#issuecomment-4227676862](https://github.com/Argocyte/Iskander/issues/73#issuecomment-4227676862)

**No new issues filed** — all findings assigned to existing tracking issues (#73, #104, #111) or the boundary-layer tracking item (B2 deliverable).

**New attack classes identified (7):**

| Gap | Class | Severity | Primary blocker |
|---|---|---|---|
| A — Trust root enumeration | Identity infrastructure | CRITICAL-equivalent | #104 federation security model |
| B — IdP key rotation/migration attack surface | Cryptographic identity | HIGH | #104 |
| C — Homograph and namespace collapse | Identity spoofing | MEDIUM-HIGH | Phase B implementation |
| D — Cross-coop reputation poisoning via fabricated mentions | Integrity (GTFT) | HIGH | #111 GTFT decay scoping |
| E — Boundary layer mention-extraction ordering | Injection | HIGH | Boundary activation (B2) |
| F — Tombstone propagation and orphaned mentions | Lifecycle (#147-adjacent) | MEDIUM | Phase B tombstone spec |
| G — Discoverability vs. governance-record mention consent | Privacy / consent | MEDIUM | Phase B spec |

**Key findings detail:**

1. **Gap A — Trust root (CRITICAL-equivalent).** The prior audit assumed a trust list would exist. The real gap: there is no defined governance mechanism for who can add a cooperative to the federation trust registry, and that registry is unsigned. This is the Web PKI root CA problem. Without a signed, governed trust root, all OIDC verification is against an unverified list. Attacker at `evil.coop` can forge mentions attributed to any existing coop's members. Must be resolved in #104 before any federation activation.

2. **Gap D — Reputation poisoning (HIGH).** `ForeignReputation.sol` (GTFT) uses federation interactions as reputation signals. A malicious coop can fabricate bulk internal "governance discussions" mentioning target members and submit them as reputation oracle inputs — inflating/deflating reputation with no proof of authentic occurrence. Fix requires signed mentions with Glass Box CIDs in reputation submissions: `mention → Glass Box CID → reputation delta`. A reputation oracle that cannot produce a verifiable Glass Box CID must be rejected. Directly relevant to #111 scoping.

3. **Gap E — Boundary layer injection (HIGH).** The spec does not define at which gate `@mention` extraction occurs within incoming federation activities. If extraction precedes Trust Quarantine (Gate 1), mentions from untrusted sources can create partial internal state before trust is established. Trust Quarantine rejection must be atomic with no downstream processing of fragments. Must be specified before boundary-layer wiring (B2 deliverable intersects this).

4. **Gap B — Key rotation window (HIGH).** JWKS rotation creates a simultaneous-validity window where old and new keys are accepted — exploitable for identity substitution. IdP migration maps (old-sub → new-sub) are a single-point-of-compromise for all member pseudonyms and must be treated as facilitator-signed governance records under the tombstone invariant.

5. **Gap G — Consent model conflation (MEDIUM).** Discoverability consent (appear in @mention autocomplete) ≠ governance-record mention consent (tagged in binding decisions/tensions of another coop). Opting into federation should require two separate informed-consent acts, not a blanket opt-in. GDPR-adjacent and ICA Principle 1/4 implication.

**Red Team verdict on #73 overall:** Still 🔴 **major-rework required**. With 10 + 7 = 17 identified gaps, the federation @mention spec must be treated as a Phase B milestone specification with formal review before any federation code is written. **Gaps A and E** are architectural gates — they require design decisions that precede implementation and cannot be retrofitted. Both belong in the #104 federation security model spec.

**ICA principle traceability:**
- Principle 1 (Voluntary Membership) — Gap G (governance-record mention without consent)
- Principle 2 (Democratic Member Control) — Gap A (compromised trust root undermines all governance), Gap D (reputation poisoning)
- Principle 4 (Autonomy and Independence) — Gap G (consent model), Gap F (tombstone forgery erases presence)
- Principle 6 (Cooperation among Cooperatives) — Gaps A, B, C (identity integrity at the inter-coop level)

**B1 re-run addendum (2026-04-11):** A second, independent audit pass identified one CRITICAL finding additive to the above 7 attack classes, plus additional depth on several HIGH items. Filed separately.

| # | Finding | Severity | Additive to first B1 pass |
|---|---|---|---|
| #161 | No signing-key revocation path — compromised home-coop OIDC key enables permanent federation-wide forgery | **CRITICAL** | Yes — distinct from trust-root enumeration (Gap A). A1 covers "who governs the registry"; #161 covers "what happens when an already-registered coop's key is exfiltrated" |

**Additional HIGH items clarified in re-run (not filed separately — covered by existing issues or #73):**
- **D1 — Federation expansion re-exposes opted-in members without re-consent (HIGH):** "Public" visibility opt-in is scoped to current federation membership at time of opt-in. When a new coop joins, all previously opted-in members are silently discoverable to the new coop. Requires `discoverable_by: [list of coop IDs]` instead of a binary flag; adds a re-consent window on federation expansion. ICA Principle 1 + GDPR Art. 6.
- **B1 — Boundary layer five-gate invariant not enforced for mention activities (HIGH):** `scope_tags` can be forged by the sender if not set exclusively by the Ontology Translation gate. Mention notification callbacks must explicitly route through all five gates; gap must be addressed in Phase B Week 7 wiring (see also #160 B2 findings).
- **G1 — Per-member rate limits evaded by distributing load across source-coop membership (MEDIUM):** 50 members of an adversarial coop each send 1 mention/day to a target, bypassing per-member caps. Requires per-source-coop aggregate cap in addition to per-member limits.

**Total B1 gaps across both passes:** 10 (prior review) + 7 (first B1 pass) + 1 CRITICAL addendum = 18 identified gaps on #73. Combined verdict: Phase B federation activation hard-blocked on #104 and #161 resolution.

### 2026-04-11 — B2: Boundary layer activation checklist

**Scope:** Full inventory of the five gates in `legacy/backend/boundary/` — what exists, what is missing, and what must be done before Phase B Week 7 federation activation.

**Coverage:** All five gate modules + orchestrator (`boundary_agent.py`), `routers/federation.py`, `boundary/tests/` (empty).

**Issue filed:** **#160** — "Pre-Phase-B boundary layer activation checklist — 8 blocking gaps including Glass Box phantom (invariant #1)". Labels: `red-team`, `safety`, `phase-b`, `architecture`.

**Critical finding — third phantom invariant (Invariant #1):**

Every gate correctly appends `AgentAction` objects to `BoundaryVerdict.agent_actions`. The federation router in `routers/federation.py` receives these verdicts via `BoundaryAgent.get_instance().ingest()` but **does not call the decision-recorder**. The Glass Box write never happens. This is a phantom of invariant #1 ("Glass Box before every write") at the federation boundary — distinct from the Phase C Clerk enforcement (#1 is correctly enforced there). Tracked as the third confirmed phantom invariant; recorded in Section 1 above.

**Gate-by-gate findings:**

| Gate | State storage | Key gap | Tests |
|---|---|---|---|
| 1 — Trust Quarantine | In-memory (lost on restart) | No `foreign_identity_trust` DB table; no tombstone path; no rate limiting | None |
| 2 — Ontology Translation | Stateless | Score ambiguity; DisCO 4th stream missing; unversioned field allowlist | None |
| 3 — Governance Verification | Stateless | `governanceProof` is self-declared (can't fix until #104); `requires_hitl` unrouted | None |
| 4 — Causal Ordering | In-memory (lost on restart) | Unbounded `_seen` set (OOM risk); silent out-of-order release instead of 429 | None |
| 5 — Glass Box Wrap | N/A — phantom | Actions produced but never written to decision-recorder | None |

**Cross-cutting:**
- **Zero tests** across all five gates — no unit, no integration
- **Shared inbox endpoint (`POST /federation/inbox`) bypasses all gates** — stub that does not call `BoundaryAgent`
- **HTTP Signature verification is a dev-mode stub** — accepts all signatures
- **No observability** — zero Prometheus/OpenTelemetry metrics emitted by any gate

**Activation dependency chain (8 blockers, all must complete before Phase B Week 7):**

1. Wire Glass Box write: `BoundaryVerdict.agent_actions` → decision-recorder `POST /log` (mandatory before inbox exposed)
2. Create `foreign_identity_trust` Postgres migration; bind Trust Quarantine state to it
3. Harden `HTTPSignatureVerifier` to RFC 9421 for internet-facing federation
4. Wire shared inbox `POST /federation/inbox` through `BoundaryAgent`
5. Resolve #104 to replace self-declared `governanceProof` with verifiable proof format
6. Unit tests per gate (happy path + one adversarial path minimum)
7. Full pipeline integration test (untrusted activity → Glass Box write confirmed in decision-recorder)
8. HITL routing for `requires_hitl` verdicts → Loomio

**Note on `ingest_sync()` delta-sync path:** This path calls only Trust Quarantine and then proceeds, bypassing gates 2–5. No documentation explains the exception. Must be formally accepted in the threat model or made to apply all 5 gates before Phase B.

**Red Team verdict:** **Not activatable as-is.** Phase B Week 7 boundary activation requires all 8 blockers above plus satisfying #104's federation security model. The most critical is the Glass Box phantom (#3 confirmed phantom invariant) — the boundary layer's safety guarantee is entirely dependent on the audit trail being written, which it currently is not.

**ICA traceability:**
- Principle 2 (Democratic Member Control) — Glass Box phantom means federation ingestion is unaudited; members cannot see what their coop accepted from external parties
- Principle 5 (Education and Information) — Glass Box transparency at federation boundary is invisible
- Principle 6 (Cooperation among Cooperatives) — entire federation model depends on boundary being trustworthy

---

## 6. New risks identified but not yet filed

These are risks surfaced during reconnaissance that should become GitHub issues when prioritised. Not all are bugs; some are architectural concerns.

- **Cascading agent complexity.** 23+ total agent tools across Clerk, Steward, S3, with Librarian/Sentry/Wellbeing pending. Each new tool expands the attack surface. Needs systematic Glass-Box-pattern review process.
- **Database schema creep in decision-recorder.** Decision, GlassBoxEntry, Tension, Review models accumulating without migration management. Needs Alembic or similar.
- **Installer security (#45 merged without red-team review).** Supply-chain target. First-boot wizard asks for secrets — needs audit for logging/exposure.
- **Authorization creep.** As agents multiply, ownership/facilitator checks are needed in more places. No central authorization policy yet.
- **Federation DNS/X.509 trust root undefined.** #73 flagged this but no design exists.
- **Steward-data service Glass Box decision.** The "reads don't require Glass Box" decision was documented in `agents/clerk/SOUL.md` but its consistent application in `services/steward-data/` has not been verified.

---

## 7. ICA principle traceability

Red Team findings are mapped to ICA principles to keep the cooperative values load-bearing:

- **Principle 1 (Voluntary and Open Membership):** #73 federation onboarding gap — members can become discoverable without informed consent
- **Principle 2 (Democratic Member Control):** Glass Box bypass risk (invariant #1 caveat), governance manifest drift (#A2), S3 authorization gaps (#56 — now fixed)
- **Principle 3 (Member Economic Participation):** Steward agent read-only + aggregate-only enforces this; Phase B smart contract audit will re-verify when write paths exist
- **Principle 4 (Autonomy and Independence):** Inter-cooperative isolation gaps in #73, federation trust model undefined, group-enumeration risks in decision-recorder (now fixed)
- **Principle 5 (Education, Training, and Information):** No red team findings yet; Glass Box transparency is the instrument
- **Principle 6 (Cooperation among Cooperatives):** #73 federation @mention spec rework — critical for safe federation
- **Principle 7 (Concern for Community):** Wellbeing agent #48 redaction needs Phase B federation-aware design

---

## 8. Red Team operating notes

- **Session re-briefing cost target:** zero. This doc + `CLAUDE.md` + `docs/plan.md` should be enough to resume any session.
- **GitHub as source of truth:** issues take precedence over this doc for active findings. This doc is for durable threat-model state and session history only.
- **Subagent dispatch pattern:** Sonnet for audits (apply checklist against code), Opus for architectural trade-offs and crypto review. Never Haiku for security decisions.
- **Immutable invariants list:** see `CLAUDE.md`. If a proposed feature would weaken any of the five invariants, it must be flagged CRITICAL regardless of other considerations.
- **File a GitHub issue, don't just write in this doc.** This doc is a map; issues are the unit of work.
