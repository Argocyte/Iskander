# Sociocracy and Iskander: Governance Process Design for Cooperative Infrastructure

*April 2026*

---

## Abstract

Iskander provides the infrastructure — Loomio for decisions, Mattermost for chat, Nextcloud for files, the Clerk for AI-assisted participation. But infrastructure without governance process design is like a meeting room without an agenda: everyone shows up, nobody knows what to do, and the loudest voices win.

Sociocracy 3.0 (S3) is a governance framework built on consent, clear domains, and structured facilitation. It was designed for exactly the kind of organisation Iskander serves: self-governing groups where every member has equal standing and decisions must be both effective and legitimate.

This document maps S3's patterns to Iskander's FOSS stack, identifies what works natively, what needs Clerk extensions, and what remains a gap. It also draws on the Radical Routes network — a UK federation of housing and worker cooperatives using consensus governance since 1988 — as a real-world precedent for federated cooperative decision-making at scale.

The thesis: Iskander's architecture already supports most sociocratic governance patterns through Loomio's native features. The gaps are in the AI layer — the Clerk agent needs facilitation skills, not new platforms.

---

## 1. Why Governance Process Design Matters

### 1.1 The Participation Problem

Cooperative governance has a persistent failure mode: participation collapse. Members join with enthusiasm, attend the first few meetings, discover that governance is slow and confusing, and gradually disengage. The members who remain are those with the most time, confidence, or stubbornness — not necessarily those with the best judgement.

This is not a technology problem. Loomio is excellent software. Mattermost is excellent software. The problem is that most cooperatives have no structured process for turning member concerns into decisions, no clear allocation of decision-making authority, and no systematic way to review whether past decisions still serve the cooperative.

Academic research on Holacracy adoption (a sociocracy-derived system) found that organisations average 4.1 circle memberships per person — a significant governance overhead. Medium abandoned Holacracy after finding that the process overhead outweighed the benefits for their organisation. The Artisans Cooperative, after adopting sociocracy, simplified their circle structure within six months and imposed a maximum of two circle memberships per leader.

The lesson: governance process design must be lightweight enough that it reduces friction rather than adding it. Iskander's role is to make the process nearly invisible — the Clerk handles the bookkeeping so members can focus on the substance.

### 1.2 Iskander's Position

Iskander is not prescriptive about governance. A housing cooperative in Leeds, a worker cooperative in Bristol, and a platform cooperative in Berlin will all govern differently. What Iskander provides is:

- **Tools** that support multiple governance approaches (consent, consensus, advice process, ranked-choice)
- **An AI Clerk** that can facilitate any of these approaches without imposing one
- **A transparency layer** (Glass Box + decision-recorder) that makes governance auditable regardless of which process the cooperative uses
- **Templates and defaults** that help new cooperatives start with proven patterns rather than inventing everything from scratch

S3 is the default recommendation — not because it is the only valid approach, but because it maps most naturally to the toolset and to ICA cooperative principles.

---

## 2. Sociocracy 3.0 in Brief

### 2.1 Seven Principles

S3 is organised around seven principles that guide all patterns:

| Principle | Meaning | ICA Alignment |
|-----------|---------|---------------|
| **Effectiveness** | Devote time only to what brings you closer to achieving your objectives | P2: Democratic Control requires effective use of members' time |
| **Consent** | Do things in the absence of reasons not to | P2: Decisions need legitimacy, not unanimity |
| **Empiricism** | Test all assumptions through experimentation and revision | P4: Autonomy requires learning from your own experience |
| **Continuous Improvement** | Evolve incrementally to accommodate steady empirical learning | P5: Education and training as ongoing process |
| **Equivalence** | Involve people in making and evolving decisions that affect them | P1: Open membership; P2: Equal voting rights |
| **Transparency** | Record all information that is valuable for the organisation and make it accessible | P5: Information for members; Glass Box principle |
| **Accountability** | Respond when something is needed, do what you agreed to, and accept your share of responsibility | P2: Representatives accountable to membership |

Every S3 principle maps to at least one ICA cooperative principle. This is not coincidence — both frameworks describe how groups of equals govern themselves effectively.

### 2.2 Key Patterns

S3 defines 74 patterns in ten categories. The patterns most relevant to Iskander are:

**Consent Decision-Making**: A proposal is adopted unless there is a "reasoned and substantial objection" — meaning an argument that the proposal would harm the organisation or that there is a worthwhile improvement. This is fundamentally different from consensus (which requires active agreement from everyone) and majority voting (which can override minorities). Consent asks: "Is this good enough for now? Is it safe enough to try?"

The consent process follows a structured sequence:
1. Present the proposal
2. Question round (clarifying questions only — no opinions)
3. Response round (brief reactions — concerns, support, suggestions)
4. Amend the proposal if needed
5. Check for objections
6. If objections exist, integrate them into an amended proposal
7. Celebrate the agreement
8. Set a review date

**Circles**: Semi-autonomous teams with clear authority over a defined domain. Each circle governs its own internal affairs within the boundaries set by the broader organisation. Circles are not committees — they have genuine decision-making power within their domain.

**Domains**: The area of authority and accountability assigned to a circle or role. A clear domain answers: "What decisions can this circle make without asking anyone else?" Domain clarity prevents both overreach and paralysis.

**Drivers**: The reason behind a decision or action. S3 formalises this as: "In the context of [situation], [actor] needs [need] because [consequence]." A well-formed driver prevents solutions looking for problems.

**Navigate Via Tension**: Members notice gaps between what is and what could be. These tensions are not complaints — they are governance fuel. The system must capture them, route them to the right circle, and ensure they get processed.

**Evaluate and Evolve Agreements**: Every agreement has a review date. When the date arrives, the circle reviews: is this still working? Does it need amending? Should it be retired? Without this pattern, organisations accumulate zombie policies that no one follows but no one has formally ended.

**Double-Linking**: Each circle sends two representatives to the parent circle — one selected by the parent (leader) and one selected by the circle itself (delegate). This ensures information flows both ways and prevents top-down control.

### 2.3 How Consent Differs from Consensus

This distinction matters because Iskander supports both:

| Aspect | Consensus | Consent |
|--------|-----------|---------|
| Question asked | "Does everyone agree?" | "Does anyone object?" |
| Threshold | Active agreement from all | Absence of reasoned objections |
| Blocking | Any member can block for any reason | Objections must be reasoned and substantial |
| Speed | Slow — requires full alignment | Faster — "good enough for now, safe enough to try" |
| Risk of | Lowest-common-denominator decisions; burnout | Untested objections; need for review dates |
| Best for | Small groups, high-stakes identity decisions | Operational decisions, policy, role selection |
| Loomio type | Consensus proposal | Consent proposal |

Radical Routes, the UK cooperative federation, uses full consensus for major decisions at quarterly gatherings. This works because they meet four times a year for intensive multi-day sessions with skilled facilitation. It would not work for weekly operational decisions in a 50-member worker cooperative. Consent scales where consensus does not.

---

## 3. Radical Routes: A UK Precedent

### 3.1 Who They Are

Radical Routes is a secondary cooperative — a cooperative of cooperatives — founded in 1988. Its members are housing cooperatives, worker cooperatives, and social centres across the UK. They operate a mutual guarantee lending system (Rootstock) and share resources, knowledge, and political solidarity.

### 3.2 Their Governance Model

- **Quarterly gatherings**: All member cooperatives send delegates to four gatherings per year. Major decisions (new members, policy changes, loan approvals) are made by consensus at these gatherings.
- **Working groups**: Standing groups handle specific domains between gatherings — finance, membership, maintenance, mutual aid. Each working group has delegated authority for routine decisions within its domain.
- **RRFM14 model rules**: A set of model rules for member cooperatives that codify governance expectations — quorum, decision-making processes, membership procedures.
- **Conflict resolution**: A structured mediation process for disputes between members or between cooperatives.

### 3.3 What Iskander Learns from Radical Routes

**Federated governance works when domains are clear.** Working groups function because everyone knows what they can decide and what must go to the full gathering. This maps directly to S3 circles and domains.

**Delegation is essential at scale.** A network of 30+ cooperatives cannot make every decision by full consensus. Delegates carry the authority of their cooperative, and working groups carry delegated authority for specific domains. Iskander's multi-membership PA layer (Issues #30-#37) addresses the same challenge: how does a member participate in governance across multiple organisations without drowning?

**Face-to-face matters.** Radical Routes' quarterly gatherings are not just decision-making events — they are community-building exercises. Digital governance tools supplement but do not replace human relationships. The Clerk should help members prepare for meetings, not replace meetings with asynchronous processes.

**Consensus has limits.** Radical Routes' consensus model works at gathering scale (30-60 delegates, skilled facilitation, multi-day schedule). It struggles with urgency and with decisions where strong minority objections are not easily resolved. S3's consent model offers a practical complement: consent for operational decisions, consensus for constitutional ones.

---

## 4. The Natural Fit: S3 Principles Meet ICA Principles

| S3 Principle | ICA Principle | How They Reinforce Each Other |
|-------------|---------------|-------------------------------|
| Effectiveness | P2: Democratic Control | Members' time is finite. Effective governance respects it. |
| Consent | P2: Democratic Control | Consent ensures every voice is heard without requiring unanimity. |
| Empiricism | P5: Education | Learning from experience is the cooperative's core strength. |
| Continuous Improvement | P5: Education | Governance evolves as the cooperative learns. |
| Equivalence | P1: Open Membership, P2: Democratic Control | Equal participation rights, equal decision-making power. |
| Transparency | P4: Autonomy (Glass Box), P5: Information | Members govern what they can see. |
| Accountability | P2: Accountable representatives | Roles and circles have clear responsibilities. |

The alignment is structural, not superficial. Both S3 and ICA describe governance by equals, which is why S3 patterns translate naturally to cooperative infrastructure.

---

## 5. How Iskander Implements Sociocracy

### 5.1 Pattern-by-Pattern Mapping

| S3 Pattern | Iskander Component | Status | Gap |
|------------|-------------------|--------|-----|
| Consent Decision-Making | Loomio consent proposals | **Native** | Clerk needs facilitation prompts for question/response rounds |
| Circle | Loomio subgroups + Mattermost channels | **Native** | No structured domain metadata on subgroups |
| Domain | Loomio group description field | **Partial** | Needs structured domain template (purpose, authority, constraints) |
| Driver | Loomio discussion threads | **Partial** | Needs driver statement template in Clerk |
| Navigate Via Tension | Clerk alerts + governance inbox | **Partial** | Needs tension-logging tool for member-reported tensions |
| Respond to Org. Drivers | Loomio discussion → proposal pipeline | **Native** | — |
| Role Selection | Loomio ranked_choice poll | **Native** | — |
| Evaluate and Evolve Agreements | — | **Missing** | Needs review-date tracking and Clerk reminders |
| Logbook | Glass Box + decision-recorder (PostgreSQL + IPFS) | **Native** | — |
| Proposal Forming | Clerk proposal drafting (`loomio_create_proposal_draft`) | **Native** | Needs S3 template variant |
| Objection | Loomio "block" stance on consent proposals | **Native** | Clerk needs objection-processing flow |
| Double-Linking | Multi-membership PA layer | **Phase PA** | Natural fit with personal node cross-coop links |
| Governance Backlog | Loomio tag filtering | **Partial** | Needs Clerk backlog management tool |
| Governance Meeting | Loomio + Mattermost | **Native** | Needs meeting facilitation skill |

### 5.2 What Works Natively

**Consent proposals in Loomio.** Loomio's consent proposal type directly implements S3 consent decision-making. Members can agree, abstain, disagree, or block. A block requires a written reason — mapping to S3's "reasoned and substantial objection." The proposal passes unless someone blocks. Loomio even supports a recommended workflow: sense check first (to test the water), then formal consent proposal.

**Subgroups as circles.** Loomio subgroups map naturally to S3 circles. Each subgroup has its own discussion space, its own proposals, its own membership. A cooperative can create subgroups for Finance, Operations, Membership, Communications — each functioning as a semi-autonomous circle with delegated authority over its domain.

**Mattermost channels as circle chat.** Each Loomio subgroup can have a corresponding Mattermost channel for real-time coordination. When the Finance circle needs to discuss something quickly, they use their Mattermost channel. When they need a decision, they move to Loomio.

**Ranked-choice for role selection.** S3's role selection pattern uses consent-based nomination. Loomio's ranked_choice poll type supports this: members rank their preferred candidates, and the result reflects collective preference without the social dynamics of open nomination.

**Glass Box as logbook.** S3's logbook pattern requires that all governance decisions, agreements, domain descriptions, and role assignments be recorded and accessible. The Glass Box + decision-recorder already does this: every decision is logged to PostgreSQL, pinned to IPFS, and queryable through the Clerk.

**Proposal forming via Clerk.** The Clerk already drafts proposals for members (`loomio_create_proposal_draft` in `tools.py:235-257`). The draft function returns formatted text that the member reviews and submits themselves — never bypassing human agency.

### 5.3 What Needs Extension

**Driver statement templates.** S3 drivers follow a specific format: "In the context of [situation], [actor] needs [need] because [consequence]." The Clerk should offer this template when a member wants to start a discussion, helping them articulate the problem before jumping to solutions. This is a Clerk prompt template, not a platform change.

**Tension logging.** Navigate Via Tension is one of S3's most powerful patterns. A member notices something that could be better — a process that's slow, a policy that doesn't fit, a responsibility gap. Currently, they would start a Loomio discussion or mention it in Mattermost, where it might get lost. The Clerk needs a `log_tension` tool that captures these observations, tags them to the relevant circle's domain, and surfaces them in the governance backlog.

**Agreement review scheduling.** Every S3 agreement has a review date. Currently, once a Loomio proposal passes, there is no mechanism to revisit it on a schedule. The Clerk needs to track review dates in the decision-recorder's metadata and alert the relevant circle when a review is due. This prevents zombie policies — agreements that no one follows because no one remembered to update them.

**Objection processing.** When a Loomio consent proposal receives a block, the S3 process requires structured objection integration: understand the objection, explore whether the proposal can be amended to address it, and re-test for consent. The Clerk should guide this process — "The block from [member] says [reason]. Would you like to amend the proposal to address this?" — without overriding the facilitator's judgement.

**Meeting facilitation.** S3 governance meetings follow a structured format: opening round, agenda building, consent to agenda, per-item processing (present → question round → response round → consent check), closing round. The Clerk could support this in Mattermost by posting prompts at each stage, tracking who has spoken in each round, and flagging when the group skips a step. Not a replacement for human facilitation — an aide-mémoire that keeps structure when the group forgets.

---

## 6. The Clerk as Governance Facilitator

### 6.1 What the Clerk Already Does

The Clerk (SOUL.md) is "partisan — in favour of the cooperative's values, its ICA principles, and the wellbeing of its members." It answers governance questions, summarises discussions, drafts proposals, posts decision summaries, and reminds members of deadlines. It never votes, never takes sides on substance, and logs every action to the Glass Box.

### 6.2 What S3 Facilitation Adds

S3 facilitation is procedural, not substantive. A good S3 facilitator does not have opinions about the proposal — they ensure the process is followed correctly. This maps perfectly to the Clerk's existing design constraints.

**Question round facilitation.** When a consent proposal is active, the Clerk can prompt: "This proposal is in the question round. Questions for clarification only — responses and reactions come in the next round." This prevents the common failure where the question round becomes a debate.

**Sense check before proposal.** Before a member creates a formal consent proposal, the Clerk can suggest a sense check first: "Would you like to run a sense check before creating the formal proposal? This helps gauge initial reactions without committing to a vote." Loomio supports sense check polls natively.

**Driver formatting.** When a member asks the Clerk to help draft a discussion, the Clerk can ask: "Can you describe the situation, what you need, and why it matters? I'll help you format it as a driver statement." This produces better-quality discussions because the problem is clearly articulated before solutions are proposed.

**Review date prompts.** When a proposal passes, the Clerk asks: "When should this agreement be reviewed? S3 recommends reviewing all agreements on a regular cycle." The review date is stored in the decision-recorder's metadata.

### 6.3 What the Clerk Must Not Do

The Clerk must not become a governance gatekeeper. Members should always be free to:

- Create discussions without using the driver format
- Submit proposals without running sense checks
- Skip question rounds if the group prefers informal discussion
- Choose consensus over consent, or advice process over either

S3 templates and prompts are defaults, not requirements. The Clerk offers structure; the cooperative decides whether to use it. This is consistent with ICA Principle 4 (Autonomy) — even internal governance tools should serve the membership, not constrain it.

---

## 7. Governance Burnout Prevention

### 7.1 The Problem

Governance burnout is the primary threat to cooperative democracy. It manifests as:

- Declining participation in votes and discussions
- Quorum failures
- Decision fatigue — members voting quickly to clear their backlog rather than deliberating
- Circle overload — members serving on too many circles simultaneously
- Facilitator burnout — the same few people running every meeting

### 7.2 How S3 Addresses It

**Clear domains reduce decision volume.** When each circle has a well-defined domain, most decisions are made by the 3-7 people in the relevant circle, not by the whole cooperative. A 50-member worker cooperative does not need all 50 members to approve every purchase order — the Finance circle handles routine spending within its delegated authority.

**Consent is faster than consensus.** Consent asks "any objections?" rather than "does everyone agree?" This is substantially faster for routine decisions. Consensus is reserved for constitutional matters where full alignment genuinely matters.

**Review dates prevent accumulation.** Agreements that expire or require review reduce the total governance burden over time. Without review dates, cooperatives accumulate an ever-growing set of policies that members must know and follow.

**Time-boxed rounds keep meetings short.** S3's structured rounds (question, response, consent check) with time limits prevent meetings from expanding to fill all available time.

### 7.3 How Iskander Reinforces It

**The Clerk as participation equaliser.** The Clerk summarises long discussions so members do not need to read every comment. It explains proposals in plain language. It reminds members of deadlines. This reduces the effort required to participate meaningfully.

**The governance inbox (Phase PA).** For members in multiple cooperatives, the PA's governance inbox triages governance items by urgency and significance. Members see what needs attention now and can defer what does not.

**Circle membership limits.** Based on the Artisans Cooperative's experience (max 2 circles per person), Iskander should recommend and help enforce circle membership limits. The Clerk can flag when a member is being nominated for a third circle: "You're already in the Finance and Operations circles. S3 recommends a maximum of two circle memberships to prevent burnout."

**Participation quality tracking.** The `context_depth` field (Issue #35) tracks whether members voted from a digest, a summary, or the full context. If a cooperative sees most votes coming from digest-level engagement, the Clerk can alert the governance committee. This is an early warning system for participation collapse.

### 7.4 Radical Routes' Lesson

Radical Routes' quarterly gatherings work partly because they happen only four times a year. The interval allows delegates to prepare, communities to discuss, and energy to regenerate. Digital governance tools that demand continuous engagement will produce burnout faster than quarterly in-person gatherings.

Iskander's Clerk should respect this rhythm. Not every tension needs immediate processing. Not every discussion needs a response today. The Clerk can batch non-urgent governance items into weekly or fortnightly digests rather than generating a stream of notifications.

---

## 8. What's Missing: Gaps and Opportunities

### 8.1 Patterns That Need New Clerk Tools

| Pattern | What's Needed | Complexity |
|---------|--------------|------------|
| Navigate Via Tension | `log_tension()` tool — capture, tag, route to relevant circle | Medium |
| Evaluate and Evolve | Review date tracking + scheduled Clerk reminders | Medium |
| Governance Backlog | Backlog view — logged tensions not yet processed into proposals | Low |
| Meeting Facilitation | Structured round prompts in Mattermost | High |
| Objection Integration | Guided amendment workflow after a block | Medium |

### 8.2 Patterns That Need Governance Templates

| Template | Purpose |
|----------|---------|
| Circle charter | Define circle purpose, domain, accountabilities, members, review date |
| Domain description | Structured definition of decision-making authority |
| Driver statement | "In the context of X, we need Y because Z" format |
| Agreement record | Decision + rationale + review date + responsible circle |

### 8.3 Patterns That Emerge from Multi-Membership (Phase PA)

**Double-linking.** In S3, double-linking ensures information flows between nested circles. In a federation of cooperatives, members who belong to multiple cooperatives are natural double-links — they carry context between organisations. The PA's governance inbox (Issue #33) should surface cross-cooperative relevance: "Your housing cooperative is discussing energy contracts. Your energy cooperative has relevant experience with supplier X."

**Cross-cooperative learning.** S3's continuous improvement principle applies across the federation. When one cooperative discovers a better way to run consent processes, the Clerk could surface this to other cooperatives (with permission) as a governance pattern to consider.

---

## 9. Recommendations

### 9.1 For Iskander Development

Five concrete features, ordered by impact and implementation cost:

1. **Consent process templates in the Clerk** (low cost, high impact). Add S3 driver format and consent process prompts to the Clerk's proposal drafting. This requires SOUL.md updates and new prompt templates, no infrastructure changes.

2. **Agreement review scheduling** (medium cost, high impact). Track review dates in decision-recorder metadata. Clerk alerts circles when reviews are due. Prevents zombie policies.

3. **Tension logging** (medium cost, medium impact). New Clerk tool to capture and route member-reported tensions. Surfaces in governance backlog. Feeds the Navigate Via Tension pattern.

4. **Governance templates** (low cost, medium impact). Documentation-only: circle charter, domain description, driver statement templates. Available to all cooperatives as starting points.

5. **Meeting facilitation skill** (high cost, medium impact). Structured round facilitation in Mattermost. This is the most complex feature and should be deferred until the simpler tools are proven.

### 9.2 For Cooperatives Using Iskander

- **Start with consent, not consensus**, for operational decisions. Reserve consensus for constitutional matters (changes to rules, membership decisions, values statements).
- **Create circles early.** Even a 5-member cooperative benefits from separating governance domains. A Finance circle and an Operations circle prevent every discussion from involving everyone.
- **Set review dates on every agreement.** If the Clerk asks "when should this be reviewed?" — answer the question. Agreements without review dates become governance debt.
- **Limit circle membership.** Two circles per member is a reasonable maximum. Three is the danger zone. Four is burnout.
- **Use the driver format.** "In the context of X, we need Y because Z" forces clarity before discussion begins. The Clerk will help you draft it.

### 9.3 For the Cooperative Movement

Sociocracy and cooperative principles share a common ancestor: the belief that people affected by decisions should make those decisions. S3's contribution is a practical toolkit for making this work at scale without burning out the participants.

Iskander's contribution is infrastructure that makes the toolkit invisible. The Clerk handles the facilitation prompts, the review reminders, the tension routing. Members experience governance as something that flows naturally — tensions are captured, proposals are well-formed, decisions are reviewed, circles have clear authority.

The goal is not to impose S3 on every cooperative. The goal is to make good governance easy and bad governance hard. If a cooperative prefers consensus, Iskander supports that. If they prefer advice process, Iskander supports that too. But for cooperatives that want structured, scalable, burnout-resistant governance — S3 through Iskander is the recommended path.

---

## References

1. Bockelbrink, B., Priest, J., & David, L. (2024). *A Practical Guide for Evolving Agile and Resilient Organizations with Sociocracy 3.0.* https://sociocracy30.org/
2. Radical Routes. (2024). *The Radical Routes Toolkit.* https://toolkit.radicalroutes.org.uk/
3. Loomio. (2024). *Sociocratic Decision-Making with Loomio.* https://www.loomio.com/
4. International Co-operative Alliance. (2015). *Guidance Notes on the Co-operative Principles.*
5. Artisans Cooperative. (2024). *Sociocracy Transition: Lessons Learned.*
6. Robertson, B. J. (2015). *Holacracy: The New Management System for a Rapidly Changing World.* Henry Holt.
7. DisCO.coop. (2019). *If I Only Had a Heart: A DisCO Manifesto.* Transnational Institute.
