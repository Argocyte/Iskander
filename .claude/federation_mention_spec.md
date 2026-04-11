# spec: Federation-Wide @Mention System — Private-by-Default with Opt-In Public Profiles

**Component:** Federation architecture (Phase B)  
**Relates to:** Issue #30 (Personal Node Federation), Issue #72 (Smart @mention autocomplete)  
**Phase:** Phase B Week 3–4 (federation discovery)

---

## Overview

Extend the smart @mention autocomplete (Issue #72) to work across cooperative federation using Instagram's private-account model: members discoverable by default only within their home cooperative; opt-in public profiles for cross-cooperative visibility.

This enables seamless cross-membership collaboration while preserving privacy defaults aligned with ICA Principle 4 (Autonomy).

---

## Problem Solved

**Without federation @mentions:**
- Members can only mention colleagues in their home cooperative
- Cross-cooperative collaboration requires manual coordination
- No discovery: can't find subject-matter experts across the federation

**With federation @mentions:**
- "@alice" autocomplete works across cooperatives (but respects privacy)
- Same-thread identity discovery: in a housing discussion, discover housing experts from other coops
- Seamless multi-membership experience

---

## Privacy Model: Instagram Pattern

**Private by Default (Recommended)**
```
Member profile setting: 
  [ ] Discoverable across federation (OFF by default)
  [ ] Allow cross-cooperative @mentions (OFF by default)
```

**Three Privacy States:**

1. **Private (Default)** — Profile not visible outside home coop; cannot be @mentioned cross-coop
2. **Public (Opt-In)** — Profile visible in federation directory; can be @mentioned anywhere
3. **Public-With-Approval** — Visible but @mentions require approval (like follow requests)

---

## @Mention Semantics

### Within Same Cooperative
```
User types: "@alice"
↓
Source: Local cooperative member list
↓
Mention: @alice (local username)
↓
Renders: Alice Smith (current display name)
```

### Across Cooperatives (Federation)
```
User types: "@alice"
↓
Source: Local + federation public members
↓
Suggestion: "Alice Smith (Leeds Housing) — public"
↓
Mention: @alice_leeds_housing
↓
OIDC sub: alice_sub_leeds (stable federation ID)
↓
Renders: Alice (Leeds Housing Coop)
```

---

## Same-Thread Identity Discovery

**Scenario:** Discussion about "Co-housing Model Pilot"

1. Member types: "@housing experts..."
2. Autocomplete queries federation directory (filtered by tags: co-housing, housing)
3. Results show public members from other coops
4. Member clicks → inserts @alice_leeds_housing
5. Discussion renders: "@Alice (Leeds Housing Coop)"
6. Alice gets notification (if public + opted-in)

**No explicit federation discovery needed** — discovery happens naturally in discussion context.

---

## Privacy Safeguards

### Enumeration Protection
- APIs require authentication
- Return results only for: home cooperative, opted-in public members, discussion participants
- Cannot query "all members from Coop X"

### Notification Gating
- Private members: no notification to non-members
- Public members: cross-coop notification works
- Approval-required: "Bob is asking to mention you..."

### Context Gating
You can see public profiles of members in:
1. Discussions you're participating in
2. Circles/groups you share membership in
3. Explicitly followed/connected members
4. (NOT) arbitrary federation search

---

## Implementation: Phase B Timeline

**Week 1–2:** Federation ID scheme (stable OIDC sub), member privacy_level table, federation directory API

**Week 3–4:** Smart mentions extended (federation source), cross-coop mention insertion, federation notifications

**Week 5+:** Thread-based discovery, multi-membership UX, privacy audit + opt-in flow

---

## Integration with Personal Node Federation (#30)

Personal Assistant era (Phase PA) will have members in multiple cooperatives simultaneously.

Federation @mentions enable seamless cross-cooperative work:
- "@alice from leeds" works same as "@carol from manchester"
- Personal Assistant shows unified inbox (mentions from all memberships)
- Same mention syntax everywhere

Foundational piece of PA multi-membership experience.

---

## Design Questions for Architect

1. **Mention Syntax:** Which is clearest?
   - @alice_coop_name (human-readable, familiar)
   - @alice/leeds_housing (path-like)
   - @alice@leeds.coop (email-like)
   - **Recommendation:** @alice_coop_name

2. **Privacy Defaults:** Private-by-default too restrictive?
   - Risk: Low federation adoption if locked down
   - Counter: ICA Principle 4 (Autonomy) suggests default private
   - **Recommendation:** Private-by-default; make opt-in easy in UX

3. **Approval Mode:** Support approval-required mentions?
   - Benefits: Gate mentions without blocking visibility
   - **Recommendation:** Phase B.5+ (not critical MVP)

4. **Discovery Heuristics:** Weight by relevance or randomize?
   - Same circles/tags as discussion (high relevance)
   - Random (fairness, prevents algorithmic bias)
   - **Recommendation:** Relevance-weighted + transparent

---

## Security Considerations

### Trust Boundary
- **Within Cooperative:** Trust members are vetted; @mention freely
- **Across Cooperatives:** Semi-trusted (external)
  - Verify OIDC sub isn't spoofed
  - Rate-limit cross-coop mentions
  - Allow blocking per-coop or per-member

### Rate Limiting
- Max 5 mentions of same person per day
- Max 20 mentions of new people per day
- Max 10 external mentions per discussion (prevent mention-bombing)

---

## Testing Checklist

- [ ] @alice (same coop) works
- [ ] @alice_leeds (cross-coop public) works
- [ ] Cannot mention @bob_private (not opted-in)
- [ ] Autocomplete shows federation results (if public)
- [ ] Privacy setting change takes effect immediately
- [ ] Notifications deliver to correct federation address
- [ ] Enumeration attack prevented
- [ ] Rate limiting blocks spam
- [ ] Thread-based discovery shows only participants
- [ ] Blocking works (don't mention me from Coop X)

---

## ICA Alignment

✅ **Principle 1** (Concern for Community) — Members collaborate across cooperatives

✅ **Principle 2** (Democratic Control) — Members control visibility; opt-in discovery

✅ **Principle 4** (Autonomy) — Each coop maintains control; federation respects boundaries

✅ **Principle 5** (Education) — Discovering experts across federation enables learning

---

## Phase C Implication

**Phase C @mention autocomplete (Issue #72) should be designed with federation in mind:**
- Architecture supports federation member directory queries
- Mention syntax allows federation scoping (@alice_coop_name ready for future)
- Privacy controls documented (enforcement in Phase B)

Don't implement federation in Phase C, but don't paint ourselves into a corner.

---

**Type:** spec  
**Phase:** B (Week 3–4)  
**Effort:** High  
**Depends on:** #30 (federation ID), #72 (smart mentions)  
**Enables:** #33 (Governance Inbox), Personal Assistant multi-membership

---

**Next Step:** Add to Phase B planning; architecture review when ready.
