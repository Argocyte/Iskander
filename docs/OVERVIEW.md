# Iskander: A Cooperative Server

## What problem does Iskander solve?

Cooperatives need digital tools to make decisions together, share files, communicate, and manage their finances. Today, most cooperatives rely on tools built for traditional businesses -- Google Workspace, Slack, Zoom -- tools designed for hierarchies, not democracies.

These tools don't understand that every member has an equal vote. They don't enforce transparency. They don't protect member privacy during sensitive votes. And they give control of cooperative data to corporations whose interests don't align with the cooperative movement.

Iskander is different. It's a server that a cooperative runs for itself. One setup gives you everything you need, and the cooperative owns and controls all of it.

---

## What does a cooperative get?

When you set up Iskander, your cooperative gets:

### A place to make decisions together (Loomio)

Members propose ideas, discuss them, and vote. Iskander supports multiple ways to decide:

- **Consent**: "Does anyone have a strong objection?" -- if not, it passes
- **Advice**: "I'm going to do this -- any input before I proceed?"
- **Consensus**: "Do we all agree?"
- **Elections**: Fair multi-winner elections where minority views get representation

Your cooperative's governance rules (quorum requirements, supermajority thresholds) are built in.

### An AI assistant (the Clerk)

Every member can chat with the Clerk -- an AI assistant that lives inside your decision-making platform. The Clerk:

- Explains what's being voted on in plain language
- Helps you write a proposal if you have an idea but aren't sure how to phrase it
- Summarises long discussions so you don't have to read everything
- Drafts documents (policies, rules, reports) based on your input
- Incorporates feedback from other members into document revisions
- Reminds you when there's a vote you haven't responded to
- Tracks action items from decisions -- who's doing what, by when

The Clerk never votes, never takes sides, and never makes decisions. It helps you make yours.

Everything the Clerk does is visible in the Glass Box -- a transparency log that any member can check at any time. There are no secret AI actions.

### Shared files, calendar, and email (Nextcloud)

A complete workspace for your cooperative:

- Shared folders for governance documents, financial reports, and project files
- Files attached in discussions automatically appear in your file manager (and vice versa)
- Shared calendar for meetings and deadlines
- Cooperative email addresses (member@your-coop.org)

### A public website

Your cooperative gets a website where:

- Anyone can see the Glass Box (transparency)
- People can apply to become members
- Your cooperative's values and mission are visible
- Connected cooperatives are listed in a federation directory
- Members log in to see their dashboard (active proposals, treasury balance, governance health)

### Treasury monitoring

An AI Steward watches your cooperative's shared wallet. If someone proposes a large expenditure, the Steward automatically creates a proposal for members to vote on. Nothing gets spent without democratic approval.

### Single sign-on

One account, one password. Members log in once and access everything -- decisions, files, email, website, treasury. No separate logins for each tool.

---

## How is it secure?

Iskander is designed to run safely on the open internet:

- All connections are encrypted (HTTPS everywhere)
- Databases are hidden behind internal networking -- only the services that need them can access them
- Protection against common attacks (DDoS, brute force, cross-site scripting)
- Strong passwords generated automatically during setup
- Optional integration with Cloudflare for additional protection

---

## How is it democratic?

### One member, one vote

Iskander uses three layers to ensure nobody can game the system:

1. **Identity verification**: Each member is verified as a unique person through a peer-to-peer network (BrightID) -- no invasive ID checks, just real humans vouching for each other
2. **On-chain membership**: Each member receives a non-transferable digital token (Soulbound Token) that proves their membership. You can't buy extra votes.
3. **Secret ballots**: For sensitive decisions, members vote using zero-knowledge cryptography. Nobody -- not even the system administrators -- can see how any individual voted. Only the final tally is revealed, and its correctness is mathematically proven.

### Transparent AI

Every AI action is logged in the Glass Box. Members can always see:
- What the AI did
- Why it did it
- When it did it

No black boxes. No hidden decisions.

---

## What are the ICA Cooperative Principles?

Iskander is built around the seven principles defined by the International Co-operative Alliance (ICA) -- the global voice of cooperatives since 1895:

1. **Voluntary and Open Membership** -- Anyone can join (and leave). Iskander makes this easy with guided onboarding.
2. **Democratic Member Control** -- Every member has an equal say. Iskander enforces this with one-member-one-vote and ZK voting.
3. **Member Economic Participation** -- Members contribute to and control the cooperative's capital. Iskander tracks shares, surplus, and reserves.
4. **Autonomy and Independence** -- The cooperative controls its own destiny. Iskander is fully self-hosted -- no corporate cloud dependency.
5. **Education, Training, and Information** -- Members learn about cooperation. The Clerk proactively guides governance education.
6. **Cooperation among Cooperatives** -- Cooperatives work together. Iskander's federation protocol connects cooperatives.
7. **Concern for Community** -- Cooperatives work for sustainable development. Iskander tracks progress against the UN Sustainable Development Goals.

---

## What does it cost?

Iskander is free and open source software. The only costs are:

- A server to run it on (a small VPS with 8GB RAM is sufficient -- approximately $20-40/month)
- A domain name if you want cooperative email addresses and a public website
- Your time to set it up (about 10 minutes with the setup wizard)

No subscription fees. No per-user charges. No vendor lock-in.

---

## Who is it for?

Iskander is for any cooperative that wants to run its digital infrastructure democratically:

- Worker cooperatives
- Housing cooperatives
- Consumer cooperatives
- Platform cooperatives
- Community land trusts
- Credit unions and financial cooperatives
- Producer cooperatives

If your organisation is governed by the principle of one-member-one-vote, Iskander is designed for you.

---

## How do I get started?

See the [README](../README.md) for technical setup instructions, or the [ROADMAP](ROADMAP.md) for the project timeline.

Iskander is currently in active development. Phase C (the core MVP) is being built now.
