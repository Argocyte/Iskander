# Values-Reflection Skill Implementation

Create `src/IskanderOS/openclaw/skills/values-reflection/SKILL.md`.

This skill enables the Clerk to guide members through self-assessment against the
ICA Statement on the Cooperative Identity. Cooperatives are based on 6 core values
and 4 ethical values, with 7 principles as guidelines for putting values into practice.

Reference: `src/IskanderOS/docs/ica-statement-on-cooperative-identity.md`

## Trigger Phrases
- "How are we doing on [value]?"
- "Run a values check"
- "What could we improve?"
- "Are we living our values?"

## The 10-Value Checklist

### Core Values (6 — what cooperatives are based on)

| Value | Question | Evidence Source |
|-------|----------|----------------|
| Self-Help | "Do members have tools to solve problems themselves?" | Loomio self-service proposals, member-initiated threads |
| Self-Responsibility | "Is governance participation shared broadly?" | Loomio voting rates, proposal authorship distribution |
| Democracy | "Does every member have equal opportunity to participate?" | Loomio participation rates, language accessibility |
| Equality | "Are benefits and services available to all members equally?" | Membership data, service access patterns |
| Equity | "Do we accommodate different needs?" | Support structures, accessibility features |
| Solidarity | "Do we support each other and other cooperatives?" | Mutual aid records, inter-coop interactions |

### Ethical Values (4 — what cooperative members believe in)

| Value | Question | Evidence Source |
|-------|----------|----------------|
| Honesty | "Are our records consistent with our actions?" | Glass Box vs actual outcomes, financial transparency |
| Openness | "Is information accessible to all members?" | Document accessibility, plain language usage |
| Social Responsibility | "Do we contribute to our community's development?" | Community interactions, external impact |
| Caring for Others | "Do we support members in difficult times?" | Support requests, response patterns |

## Assessment Flow

1. Ask member: "Would you like to check a specific value, or run the full assessment?"
2. For each value: Ask the yes/no/partly question, pull evidence from Loomio API
3. Score: Strong / Good / Developing / Needs Attention
4. Produce summary: "Your cooperative is strongest in [X] and [Y]. Area for growth: [Z]."
5. Suggest one concrete improvement action for the weakest area
6. Log the assessment to Glass Box
