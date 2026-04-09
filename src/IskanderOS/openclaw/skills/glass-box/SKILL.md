---
name: glass-box
description: >
  Log every Clerk action to the Glass Box audit trail before executing it.
  Use this skill whenever you are about to take an action that affects cooperative
  systems (creating discussions, posting messages, reading member data).
  The Glass Box makes every agent action visible and challengeable by members.
---

# Glass Box — Audit Trail

The Glass Box is the cooperative's transparency mechanism for AI actions. Every action the Clerk takes that affects the cooperative's systems is recorded here with:
- **Who** asked for it (member user ID)
- **What** the Clerk is about to do
- **Why** (the Clerk's reasoning)
- **When** (UTC timestamp)

## Mandatory use

Call `glass_box_log` BEFORE any write action. This is not optional.

If `glass_box_log` returns an error, you MUST NOT proceed with the action. Tell the member: "I wasn't able to log this action to the Glass Box audit trail, so I can't proceed. This protects the cooperative's transparency. Please try again."

## What to log

| Situation | Action value | Target value |
|-----------|-------------|--------------|
| Creating a Loomio discussion | `"create_loomio_discussion"` | `"Loomio: <title>"` |
| Posting to Mattermost | `"post_mattermost_message"` | `"Mattermost: #<channel>"` |
| Reading all discussions | `"read_loomio_discussions"` | `"Loomio: discussions"` |

Read-only operations (listing proposals, searching discussions) do not require Glass Box logging but you may log them for transparency if the member prefers.

## Reasoning quality

The reasoning field should be specific enough that any member reading the audit trail would understand why the action was taken. Avoid generic text like "member asked me to" — instead: "Member @alice asked me to create a discussion about the pay review proposal she outlined in the chat."
