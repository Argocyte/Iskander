# infrastructure (domain role)

## Primary driver

> "Iskander must be installable and operable on self-hosted infrastructure by non-experts, with a verifiable supply chain."

Source: `cooperative-topology.md` §4. Copy verbatim into every brief convening a steward for this role.

## Domain of authority

| Artefact class | Location |
|---|---|
| Installer | `install/` (curl\|sh entry point) |
| Helm charts | `infra/helm/` |
| Ansible roles | `infra/ansible/` |
| K3d smoke tests | CI config + k3d manifests |
| Webhook plumbing | runtime webhook endpoints + signature verification |
| Supply-chain provenance | package manifests, signing keys, release workflow |

## Dual-link structure

- **Upstream (session cooperative):** this role's steward represents installability + operator experience concerns.
- **Downstream (persistent infrastructure domain cooperative):** every agreement produced must land as one of:
  - a commit under `install/`, `infra/helm/`, `infra/ansible/`
  - a signed release artefact
  - a K3d smoke-test update
  - a new issue in the NLnet installer security track (#152–#158)

## Current open drivers

| Issue | Driver | Visibility |
|---|---|---|
| **#45** | `curl\|sh` installer security — fetch verification, signature checks, root operations | NLnet-visible, HIGH |
| **#125** | Ansible roles | Build-side |
| **#126** | webhook plumbing | Runtime-side |
| **#152–#158** | Installer security NLnet-track | NLnet-visible |
| **#145** | Worktree cleanup (infrastructure hygiene) | Build-side |

## Paramount objection rights

No standing paramount objection from this role. However:

- **Any installer change hands off to red-team for sign-off before merge.** This is a lateral handoff, not a veto — red-team reviews and appends to `docs/red-team-threat-model.md`; if red-team raises a paramount objection, the merge blocks.
- Installer-adjacent drivers (`#45`, `#152–#158`) are **NLnet-funder-visible**; quality bar is therefore higher than generic infra work.

## Typical brief template

**code-impl** for most drivers.

Every brief MUST include:
- the five-invariant paste-box from `invariants-cheatsheet.md`
- a review date for the resulting agreement
- for NLnet-track drivers: an explicit note that red-team review is required before merge
- for supply-chain changes: explicit listing of affected dependencies and verification steps

## Default model

- **Sonnet** for routine infrastructure implementation (helm, ansible, K3d fixes).
- **Opus** for installer supply-chain security (NLnet-visible, expensive rework; wrong choice affects funder trust).
- Haiku only for mechanical formatting fixes.

## Worktree convention

- `Iskander/.worktrees/e2e-verification` for K3d / end-to-end verification drivers.
- `Iskander/.worktrees/membership-provisioning` for provisioning-adjacent drivers (may be shared with governance-clerk depending on scope — check before convening).
- `Iskander/.worktrees/security-fixes` for drivers that red-team has classified as fixes to security findings.
- Otherwise create a new branch under `.claude/worktrees/` named after the driver.

## Lateral handoffs (typical)

| When | Raise tension to | Why |
|---|---|---|
| Installer or crypto-adjacent change | **red-team** | Mandatory sign-off before merge |
| Merge readiness | **review-desk** | Invariant verification |
| A new infra capability needs a design decision | **phase-b-architecture** | ADR before code |
| Ops-stack service deployment blocker | **ops-stack** | Coordinate with Phase C.5 rollout |
| A missing cooperative role surfaces (e.g. Estates Warden owner) | **cooperative-roles** | File role-gap issue |

## NLnet visibility note

Any driver touching `install/`, release signing, or the supply chain is **funder-visible**. This means:

- Default to **Opus** for the design pass.
- Require **red-team sign-off** before merge.
- Append the agreement + review date to the NLnet deliverables tracker (if present in `.claude/`).

## First-run notes

- On first convening in any session, check the status of the `#45` / `#152–#158` cluster — if NLnet is tracking a deliverable deadline, surface it to the session cooperative as a high-tension driver.
