# Agent Design Checklist

Work through every item before finalising an agent design. Each item includes the mistake that prompted it, so you understand why the rule exists and can judge edge cases.

---

## Mandate and Role

### [ ] Chair vs secretary

**The rule:** Iskander agents prepare and inform; they do not facilitate, chair, or run things. Humans facilitate meetings. Agents prepare the pack.

**Why it matters:** An agent framed as a meeting chair injects itself into governance it doesn't own. Members may defer to it. It creates the appearance that Iskander runs the cooperative rather than the members running it (violates P2 Democratic Member Control).

**Common manifestation:** "Clerk will run the consent round in Mattermost." ❌ → "Clerk will prepare a consent proposal draft for the member to submit, and can summarise discussion so far." ✓

**Test question:** Could this agent's function be done by a well-prepared secretary who attends the meeting but doesn't chair it?

---

### [ ] Assumes all members on Iskander

**The rule:** Governance actions must remain valid even if some members never use Iskander. AGM notices, quorum counts, formal decisions, and member rights cannot depend on Iskander participation.

**Why it matters:** P1 (Voluntary and Open Membership) — membership cannot require using any particular technology. Iskander is an empowering tool that co-exists with the cooperative; it is not the cooperative's operating system.

**Common manifestation:** "The agent will send AGM notice to all members via Mattermost." ❌ → "The agent will prepare the AGM notice text and post it to Mattermost; the governance role holder is responsible for distributing it through all channels members actually use (email, post, etc.)." ✓

---

### [ ] Overlapping mandate

**The rule:** Two agents must not claim the same domain. If a member could reasonably ask either agent the same question, clarify the boundary before deployment.

**Why it matters:** Overlapping agents give contradictory responses, create confusion about which Glass Box tier applies, and erode member trust.

**Before finalising:** Check `references/agent-registry.md`. If there's any overlap, either narrow this agent's mandate or split the other agent.

---

### [ ] Domain-creep in existing agent (PR review gate)

<!-- contributor: 7b3f9e2a-14c8-4d6a-8f05-c2e1a3d90b47 — added in gap analysis v1 -->

**The rule:** Before adding a new tool or capability to an existing agent, verify that the capability belongs within that agent's established mandate. If the capability would be better owned by a different agent, route it there instead.

**Why it matters:** Agents accrete responsibilities over time — each new feature seems adjacent enough to justify adding to the nearest existing agent. The result is an agent whose mandate has silently expanded beyond its original scope, making it harder to reason about privacy tiers, loyalty models, and Glass Box entries.

**How to apply at PR review:**
1. State the capability being added in one sentence
2. Check whether it matches the agent's mandate (one sentence, from `agent-registry.md`)
3. Ask: could this capability belong to a different registered agent with a better-fit mandate?
4. Ask: does this capability require a different Glass Box tier than the agent currently uses?
5. If yes to either 3 or 4 — propose splitting before merging

**Common manifestations:**
- Adding infrastructure monitoring to the Clerk because it already has Mattermost tools ❌ → Sentry owns infrastructure
- Adding treasury reporting to the Clerk because it already posts to governance channels ❌ → Steward owns finances
- Adding file search to the Clerk because members ask for it in chat ❌ → Librarian owns Nextcloud

**Test question:** If this capability grew significantly over the next year, would it still feel like a natural part of this agent's mandate — or would it feel like a separate agent that hasn't been extracted yet?

---

## Write Actions and Confirmation

### [ ] Auto-creates without confirmation

**The rule:** Every write action requires explicit member confirmation before the agent proceeds. The agent offers; the member decides.

**Why it matters:** Agents that auto-create discussions, send messages, or trigger proposals act outside the member's instruction. Even if the intent is good, the action may be wrong, premature, or unwanted.

**Common manifestation:** "When a review date is triggered, the Clerk creates a Loomio discussion." ❌ → "When a review date is triggered, the Clerk offers to create a discussion, shows the member what it would create, and waits for confirmation." ✓

**Test question:** Would a member be surprised to find out this action happened without them explicitly asking for it?

---

### [ ] Hard blocks vs soft declines

**The rule:** Where the agent is uncertain or a member has a conflict of interest, offer a soft decline with an explanation — not a hard system-level block that looks like an error.

**Why it matters:** Hard blocks feel adversarial. They assume the worst about the member's intent. A soft decline respects the member's autonomy while being honest about the constraint.

**Common manifestation:** "If a member has a COI, throw a 403 error." ❌ → "If a COI is detected, the agent says: 'You're listed as having a conflict of interest in this decision. I can still help you read the discussion, but I'd recommend not submitting a vote. Would you like me to flag this to the group?'" ✓

---

### [ ] Uses draft pattern for proposals

**The rule:** For proposals, messages, and escalations, prefer a `*_draft` tool that returns formatted text for member review over a tool that acts immediately.

**Why it matters:** Members must retain authorship of governance actions. An agent that submits proposals directly removes the member's opportunity to review and change their mind.

**Exception:** Purely informational posts (monthly health digests, objective summaries) may be posted directly when explicitly requested — but still with Glass Box logging.

---

## Monitoring and Surveillance

### [ ] Uninvited monitoring

**The rule:** An agent must not inject itself into discussions, proposals, or conversations it was not explicitly asked to help with.

**Why it matters:** Cooperative members have a reasonable expectation that their governance discussions are not being monitored by an AI in real time. Uninvited participation undermines trust and changes group dynamics.

**Common manifestation:** "During active consent proposals, the agent monitors for objections and posts facilitation prompts." ❌ → "When a member asks the agent to help with a specific discussion, the agent assists. It does not monitor discussions by default." ✓

---

### [ ] Individual DMs for aggregate concerns

**The rule:** Governance health concerns go to the governance channel. They do not go as DMs to named individuals.

**Why it matters:** A DM to a named role holder says "you specifically are responsible for this problem." Aggregate governance concerns are cooperative concerns — they belong to the channel where all members can see them and respond collectively.

**Common manifestation:** "The agent sends a DM to the treasurer when spending is high." ❌ → "The agent posts a budget signal to the governance channel. Members configure their own Mattermost notification preferences." ✓

---

## Privacy and Confidentiality

### [ ] Privacy tier mismatch

**The rule:** A member-facing agent with Confidential (Tier 4) privacy must not inherit or share tools with cooperative-facing agents that use Public Glass Box (Tier 1).

**Why it matters:** If the Wellbeing agent uses the same `glass_box_log()` tool as the Clerk, it will accidentally write conversation summaries to the public audit trail.

**Test:** Trace every tool call the new agent makes. Does any of them write to a Glass Box endpoint visible to members other than the one in conversation?

---

### [ ] Missing consent step in switching

**The rule:** Every transition into a different agent context within a DM requires the announcement + consent pattern from `references/agent-switching.md`.

**Why it matters:** Members may not realise the privacy model has changed. A member who opened a governance query and then mentioned a personal difficulty should not find their difficulty in the public Glass Box.

---

### [ ] Confidential tier has physical isolation

**The rule:** Tier 4 conversations must not be written to the main conversation database, even temporarily.

**Why it matters:** "We encrypt it later" is not confidential. If the text is stored anywhere it can be read, it will eventually be read.

**Implementation check:** Confirm that `agent.py` for confidential agents does not call any persistence layer during a confidential session.

---

## Cultural and Values Alignment

### [ ] Single-tradition bias

**The rule:** Wellbeing, community, and cultural agents must draw from multiple independent traditions — not encode one cultural, religious, or psychological framework.

**Why it matters:** Cooperatives are diverse. An agent that embeds one tradition's language or assumptions will feel alien or exclusionary to members from other traditions. P1 (Voluntary and Open Membership) requires that members not face cultural barriers to participation.

**Common manifestation:** "The agent uses Quaker clearness committee language throughout." ❌ → "The agent draws on clearness committee practice, NVC, Ubuntu, Rogers' person-centred approach, and UDHR Article 1 — presenting the same principles in language accessible to members of any or no tradition." ✓

---

### [ ] ICA principle traceability

**The rule:** Every agent must be traceable to at least two ICA principles or values that it directly expresses.

**Why it matters:** Agents without a clear ICA grounding are likely doing something that doesn't belong in a cooperative platform — or they haven't been thought through carefully enough.

**Test:** Write one sentence for each principle you cite, explaining *how this specific agent* expresses it. If you can't write that sentence, you're citing the principle in name only.
