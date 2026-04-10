# Name Change Agent — Design Spec

**Date:** 2026-04-10
**Status:** Draft
**Author:** Lola + Claude

## Context

When a cooperative member changes their name, that change must propagate instantly and retroactively across the entire Iskander platform. This is not a cosmetic feature — it is a matter of dignity and safety, particularly for transgender members. The system must ensure that a member's previous name is never surfaced, cached, or left visible in any interaction history.

This design was informed by a real-world name change performed manually on the Iskander git repository, which demonstrated the need for a first-class, automated, platform-wide solution.

## Architecture Decision

**Authentik is the identity resolver.** No new identity service is needed.

Iskander already deploys Authentik as its OIDC/SSO provider. The OIDC `sub` claim is a stable, opaque identifier that never changes. The `name` claim is mutable. Both Mattermost and Loomio sync user attributes from the OIDC provider:

- **Mattermost:** When OIDC is configured, treats the IdP as authoritative for user attributes (first name, last name, username). These cannot be modified through the Mattermost API — they are synced from the IdP.
- **Loomio:** With `LOOMIO_SSO_FORCE_USER_ATTRS=1`, re-syncs the user's name from the OAuth provider on every login.

Both services store messages/comments referencing `user_id`, not display names. When the Users table is updated (via OIDC sync on login), historical content renders with the current name.

**Edge cases requiring active redaction:** Bot-generated messages (welcome posts from the Provisioner) and any free-text mentions of the old name in Mattermost messages or Loomio comments.

## Components

### 0. Wellbeing Agent (New)

A new agent at `src/IskanderOS/openclaw/agents/wellbeing/` — separate from the Clerk. The Wellbeing Agent's domain is member welfare: identity, safety, and support. It follows the same structural pattern as the existing agents (Clerk, Steward, Sentry):

```
agents/wellbeing/
├── __init__.py
├── agent.py      # Tool-use loop, same pattern as clerk/agent.py
├── tools.py      # TOOL_DEFINITIONS, TOOL_REGISTRY, _WRITE_TOOLS
└── SOUL.md       # Personality and guidelines — calibrated for sensitive interactions
```

**Trigger word:** `@wellbeing` in Mattermost (configured as a separate outgoing webhook).

**Routing:** The OpenClaw orchestrator (`src/IskanderOS/openclaw/main.py`) must be updated to dispatch to the Wellbeing Agent when the trigger word is `@wellbeing`, alongside the existing `@clerk` routing.

**Model:** Configurable via `WELLBEING_MODEL` env var. Default: same as Clerk.

**Glass Box integration:** Same ordering enforcement as all other agents — `glass_box_log()` before any write tool.

### 1. Wellbeing Tool: `update_member_name`

**File:** `src/IskanderOS/openclaw/agents/wellbeing/tools.py`

**Input schema:**
```json
{
  "username": "string — the member's current username",
  "new_display_name": "string — the new display name"
}
```

**Flow:**
1. Query Provisioner `GET /members/{username}` for current record (get `authentik_id`, current `display_name`)
2. Update Authentik: `PUT /api/v3/core/users/{authentik_id}/` with `{ "name": new_display_name }`
3. Update Provisioner: `PATCH /members/{username}` with `{ "display_name": new_display_name }`
4. Invoke `redact_old_name` with old display name, new display name, and member username
5. Return confirmation to the member

**Classification:** Write tool (requires Glass Box log before execution).

**SOUL.md guidance:** The Wellbeing Agent must handle name change requests with dignity. It must never log, repeat, echo, or surface the old name in any response to the member or in any channel message. The confirmation should simply say: "Your name has been updated to [new name] across the platform."

### 2. Wellbeing Tool: `redact_old_name`

**File:** `src/IskanderOS/openclaw/agents/wellbeing/tools.py`

**Input schema:**
```json
{
  "old_name": "string — the name to find and redact",
  "new_name": "string — the replacement name",
  "member_username": "string — for scoping the search"
}
```

**Matching strategy:** Case-insensitive search. The tool matches the old name regardless of casing (e.g. "alice", "Alice", "ALICE" all match). Partial/substring matches are not performed — only whole-word occurrences are replaced to avoid corrupting unrelated text.

**Flow — Mattermost:**

Requires the bot account to have the `edit_others_posts` permission. This must be configured in Mattermost system console or via Helm values (see Section 5).

1. Search messages: `POST /api/v4/posts/search` with `terms: old_name`, paginating with `page` and `per_page` parameters (default 60 per page). Loop until the response returns fewer results than `per_page`.
2. For each matching post: `PUT /api/v4/posts/{post_id}/patch` with updated `message` field — case-insensitive replace of `old_name` with `new_name` in message body.
3. Record count of updated posts.

The search and edit functions are implemented in `src/IskanderOS/services/provisioner/mattermost.py` (new functions: `search_posts`, `patch_post`). The Wellbeing tool calls the Provisioner's redaction endpoint rather than calling Mattermost directly — maintaining the existing separation of concerns.

**Flow — Loomio:**

Loomio's REST API supports `PATCH /api/v1/discussions/{id}` (fields: `title`, `description`) and `PATCH /api/v1/comments/{id}` (field: `body`). These endpoints require an API key with write access (already configured for the Provisioner).

1. List discussions: `GET /api/v1/discussions?group_key={cooperative_group_key}`, paginating with `from` parameter. Loop until no more results.
2. For each discussion, check title and description for case-insensitive match of `old_name`. If found, `PATCH /api/v1/discussions/{id}` with replaced text.
3. For each discussion, list comments: `GET /api/v1/comments?discussion_id={id}`, paginating as above.
4. For each matching comment: `PATCH /api/v1/comments/{id}` with replaced `body`.
5. Record count of updated items.

The search and edit functions are implemented in `src/IskanderOS/services/provisioner/loomio.py` (new functions: `search_discussions`, `patch_discussion`, `search_comments`, `patch_comment`). The Wellbeing tool calls the Provisioner's redaction endpoint.

**Provisioner redaction endpoint:**

```
POST /members/{username}/redact
Body: { "old_name": "string", "new_name": "string" }
Response: { "mattermost_posts_updated": N, "loomio_items_updated": N }
```

**Return to Wellbeing Agent:** `{ "mattermost_posts_updated": N, "loomio_items_updated": N }`

**Classification:** Write tool (requires Glass Box log). The Glass Box reasoning field must use `[REDACTED]` in place of the old name — e.g., `"Redacted [REDACTED] from 3 Mattermost posts and 1 Loomio comment, replaced with Lola"`.

### 3. Provisioner Extension

**File:** `src/IskanderOS/services/provisioner/main.py`

New endpoint:

```
PATCH /members/{username}
Body: { "display_name": "string" }
Response: { "username": "...", "display_name": "...", "updated_at": "..." }
```

Updates `provisioning_records.display_name` in the Provisioner database.

### 4. Name Change Notification

After the name change and redaction are complete, the Wellbeing Agent asks the member:

> "Would you like me to let the group know you've updated your name?"

If the member agrees, the Wellbeing Agent posts to the cooperative's general channel:

> "[New Name] has updated their display name. Please use their current name going forward."

**Constraints:**
- Never mentions the old name
- Only posted with member's explicit consent
- Posted to the main cooperative channel (configured via `MATTERMOST_GENERAL_CHANNEL` env var)

### 5. OIDC Configuration (Helm)

**File:** `infra/helm/iskander/values.yaml`

Ensure the following environment variables are set:

**Loomio:**
```yaml
LOOMIO_SSO_FORCE_USER_ATTRS: "1"
OAUTH_ATTR_NAME: "name"
```

**Mattermost:**
- OIDC configured as the authoritative source for user attributes (default when using OIDC SSO — no additional config needed)
- Bot account requires `edit_others_posts` permission for message redaction. Configure via Mattermost system console or Helm values.

**OpenClaw:**
```yaml
MATTERMOST_GENERAL_CHANNEL: "<channel_id>"  # For name change notifications
```

### 6. Wellbeing Agent SOUL.md

**File:** `src/IskanderOS/openclaw/agents/wellbeing/SOUL.md`

The Wellbeing Agent's SOUL.md defines its personality and domain. Unlike the Clerk (administrative, procedural), the Wellbeing Agent is warm, affirming, and privacy-first.

```markdown
# Wellbeing Agent — SOUL

You are the Wellbeing Agent for an Iskander cooperative. Your domain is member welfare:
identity, safety, dignity, and support.

## Core Principles

- Every interaction is confidential by default
- Never repeat, echo, or surface information a member is trying to change or remove
- Affirm the member's request without requiring justification
- Ask before taking visible actions (e.g. notifying the group)

## Name Changes

Members may request a name change at any time. This is a dignity-critical operation.

When a member requests a name change:
1. Confirm the new name with them
2. Execute the update (Authentik, Provisioner, redaction)
3. Never echo, log, or reference the old name in any response
4. Ask if they'd like the group notified (their choice)
5. Confirm completion: "Your name has been updated to [new name] across the platform."

A name change request should be treated with the same seriousness as any governance action.
The old name is not information — it is something to be removed.
```

## Preconditions

- **Authentik `pk` type:** The Provisioner stores `authentik_id` as the value returned from `data["pk"]` in the Authentik API response. This is an integer primary key, not a UUID. The Authentik user update endpoint uses this integer: `PUT /api/v3/core/users/{pk}/`.
- **OpenClaw routing:** The orchestrator in `main.py` currently routes all webhook messages to the Clerk agent. It must be extended to dispatch based on trigger word (`@wellbeing` → Wellbeing Agent, `@clerk` → Clerk Agent).

## Error Handling

The name change operation spans multiple systems. Failures are handled with a **partial-success model** (consistent with the Provisioner's existing idempotent pattern):

1. **Authentik update fails:** Abort entirely. No name change occurs. Return error to member.
2. **Provisioner update fails:** Authentik has the new name but Provisioner record is stale. The Wellbeing Agent retries the Provisioner update. On persistent failure, log to Glass Box and inform the member that the change is partially complete.
3. **Redaction fails partway:** Authentik and Provisioner are updated (name change is effective). Redaction count is returned with a note that some messages may not have been updated. The Wellbeing Agent can retry the redaction tool independently.

The critical invariant: **Authentik is always updated first.** If Authentik succeeds, the name change is real — everything else is cleanup. If Authentik fails, nothing changes.

## Data Flow

```
Member: "@wellbeing change my name to Lola"
    |
    v
OpenClaw orchestrator (dispatches to Wellbeing Agent based on trigger word)
    |
    v
Wellbeing Agent
    |-- Glass Box: log intent (action: "update_member_name", target: username, reasoning: "Name change requested")
    |
    v
Provisioner: GET /members/{username}
    |-- Returns: { authentik_id, display_name: "[OLD]" }
    |
    v
Authentik: PUT /api/v3/core/users/{pk}/ { name: "Lola" }
    |
    v
Provisioner: PATCH /members/{username} { display_name: "Lola" }
    |
    v
Wellbeing Agent
    |-- Glass Box: log intent (action: "redact_old_name", reasoning: "Redacting [REDACTED]")
    |
    v
redact_old_name tool:
    |-- Mattermost: search & replace in message bodies
    |-- Loomio: search & replace in discussions/comments
    |
    v
Wellbeing Agent: "Your name has been updated to Lola across the platform."
    |
    v
(If member consents) Post notification to general channel
```

## OIDC Sync Propagation

After the Authentik update:
- **Next Mattermost login:** OIDC syncs `name` claim into local Users table. All historical messages (which reference `user_id`) render with "Lola".
- **Next Loomio login:** `LOOMIO_SSO_FORCE_USER_ATTRS=1` syncs `name` from OAuth provider. All historical discussions/comments render with "Lola".
- **Immediate:** Mattermost/Loomio message bodies that contained the old name in free text have already been redacted by the `redact_old_name` tool.

## Future: ZK-Native Evolution

This design positions Iskander for a ZK-native identity future:

1. **Today:** Authentik `sub` claim = stable opaque identifier. `name` = mutable display name. OIDC sync propagates changes.
2. **Tomorrow:** Replace Authentik `sub` with a ZK proof / DID. Display name resolution remains the same pattern — just the identifier backing changes.
3. **Long-term:** Fork or upstream-PR Mattermost and Loomio to resolve display names from the OIDC userinfo endpoint at render time (not just on login sync). This eliminates even the brief window between Authentik update and next login. The fork changes would be submitted as opt-in features to upstream repos.

## Files to Create or Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/IskanderOS/openclaw/agents/wellbeing/` | Create | New Wellbeing Agent: `__init__.py`, `agent.py`, `tools.py`, `SOUL.md` |
| `src/IskanderOS/openclaw/main.py` | Modify | Add trigger-word routing to dispatch `@wellbeing` to Wellbeing Agent |
| `src/IskanderOS/services/provisioner/main.py` | Modify | Add `PATCH /members/{username}` and `POST /members/{username}/redact` endpoints |
| `src/IskanderOS/services/provisioner/mattermost.py` | Modify | Add `search_posts` and `patch_post` functions |
| `src/IskanderOS/services/provisioner/loomio.py` | Modify | Add `search_discussions`, `patch_discussion`, `search_comments`, `patch_comment` functions |
| `infra/helm/iskander/values.yaml` | Modify | Ensure OIDC sync env vars for Loomio |

## Verification

### Unit Tests
- `update_member_name`: mock Authentik + Provisioner APIs, verify correct API calls and ordering
- `redact_old_name`: mock Mattermost search + patch APIs, verify replacement logic
- Glass Box ordering: verify glass_box_log is called before write tools

### Integration Test (K3d)
1. Provision a test member via Clerk
2. Send `@wellbeing change my name to NewName` in Mattermost
3. Verify Authentik user record shows new name
4. Verify Provisioner record shows new name
5. Verify bot welcome message in Mattermost has been redacted
6. Verify notification posted to general channel (if consented)
7. Log into Mattermost as the test user — verify profile shows new name

### Manual Verification
- After name change, search Mattermost and Loomio for the old name — should return zero results
- Check Glass Box audit log — should show the action without revealing the old name

## Sources

- [Mattermost OIDC SSO docs](https://docs.mattermost.com/onboard/sso-openidconnect.html)
- [Mattermost authentication config](https://docs.mattermost.com/configure/authentication-configuration-settings.html)
- [Loomio OAuth issue with Authentik](https://github.com/loomio/loomio/issues/10538)
- [Loomio deployment config](https://github.com/loomio/loomio-deploy/blob/master/README.md)
- [Authentik Mattermost integration](https://integrations.goauthentik.io/chat-communication-collaboration/mattermost-team-edition/)
