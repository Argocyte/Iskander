# Iskander: Your Cooperative's Own Server

## The problem

Cooperatives are democratic organisations, but the tools most cooperatives use are not. Google Workspace, Slack, Microsoft 365 -- these are built for companies with bosses, not organisations where every member has an equal vote.

When you use corporate platforms, your data lives on their servers. Your members are their product. Your cooperative's internal discussions, financial records, and voting patterns are visible to companies whose interests have nothing to do with the cooperative movement.

Iskander is the alternative. It is a server that your cooperative runs for itself. Everything stays under your control. No corporation sees your data. No platform can shut you down or raise prices.

---

## What your cooperative gets

When you install Iskander, your cooperative gets all of the following, running on your own server, behind a single login:

**Decisions (Loomio)** -- Members propose ideas, discuss them, and vote. Supports consent, advice process, consensus, and ranked-choice elections. Your cooperative's governance rules (quorum, supermajority thresholds) are enforced automatically.

**Real-time chat (Mattermost)** -- Channels for teams, projects, and the whole cooperative. Threaded discussions. File sharing. Integrates directly with your decision-making -- when a vote opens in Loomio, a notification appears in your chat channels.

**AI assistant (the Clerk)** -- An AI that helps members participate. It explains proposals in plain language, helps you draft new ones, summarises long discussions, tracks action items, and reminds you about open votes. The Clerk never votes, never takes sides, and never acts without member approval. Everything it does is logged in the Glass Box -- a transparency record any member can inspect at any time.

**Shared files (Nextcloud)** -- Shared folders for governance documents, financial reports, project files. Collaborative document editing. Calendar. Contacts. All synced across devices.

**Password vault (Vaultwarden)** -- A shared password manager for the cooperative's accounts and credentials. Members can also use it for personal passwords. End-to-end encrypted.

**Backups (Backrest)** -- Automatic encrypted backups of everything -- decisions, files, databases, configuration. If something goes wrong, you can restore your cooperative's entire digital life.

**Monitoring (Beszel)** -- A dashboard showing the health of your server. Disk space, memory usage, service status. Alerts if something needs attention.

**A website** -- A public site where people can learn about your cooperative, read your Glass Box transparency log, and apply for membership. Members log in to see their dashboard.

**Email** -- Cooperative email addresses (member@your-coop.org) so your cooperative has a professional presence.

**Single sign-on (Authentik)** -- One account, one password. Members log in once and access every service. No separate logins for each tool.

---

## Privacy

Your cooperative's operations are transparent to members but private from the outside world.

Votes are secret when they need to be. Iskander uses zero-knowledge proofs -- a form of cryptography that lets the system prove a vote was counted correctly without revealing how any individual voted. Not even system administrators can see individual ballots. Only the final tally is revealed, and its correctness is mathematically guaranteed.

All traffic between members and the server is encrypted. Services communicate over private internal networks. Your cooperative's data never touches a corporate cloud.

This is the lunarpunk principle: visible to those who should see, invisible to those who should not.

---

## Democratic

One member, one vote. No exceptions.

Identity is verified through peer-to-peer networks -- members vouch for each other as real, unique people. No government ID required. No biometrics. No surveillance infrastructure.

Each verified member receives a non-transferable digital token (a Soulbound Token) that proves their membership. You cannot buy extra votes. You cannot create fake accounts.

Every AI action is recorded in the Glass Box. Members can see what the Clerk did, why it did it, and when. There are no hidden decisions, no secret algorithms, no black boxes.

---

## Federation

Cooperatives do not exist in isolation. Iskander lets cooperatives connect to each other through encrypted mesh networks.

Two cooperatives running Iskander can discover each other, verify each other's democratic credentials, and begin trading or collaborating -- without banks, without platforms taking a percentage, without intermediaries.

Reputation is portable. If your cooperative has a track record of fair dealing, that reputation follows you across the network. Escrow contracts protect both sides of any transaction.

This is cooperation among cooperatives -- ICA Principle 6 -- built into the infrastructure.

---

## What it costs

Iskander is free software. The code is open source. There are no subscription fees, no per-user charges, no vendor lock-in.

The only costs:

- A VPS or your own hardware. 16GB RAM recommended. Approximately $20-40/month from most hosting providers, or run it on a machine you already own.
- A domain name, if you want email addresses and a public website.
- Your time to run the installer (about 10 minutes).

---

## Installation

One command installs everything:

```
curl -sL https://install.iskander.coop | sh
```

The installer handles Kubernetes, databases, services, SSL certificates, DNS, and account provisioning. A first-boot wizard walks you through naming your cooperative, creating the first member accounts, and configuring your governance rules.

---

## Who is it for

Iskander is for any cooperative that wants to own its digital infrastructure:

- Worker cooperatives
- Housing cooperatives
- Consumer cooperatives
- Platform cooperatives
- Community land trusts
- Credit unions and financial cooperatives
- Producer cooperatives
- Solidarity economy organisations

If your organisation is governed by the principle of one-member-one-vote, Iskander is built for you.

---

## The ICA Cooperative Principles

Iskander is built around the seven principles of the International Co-operative Alliance -- the global voice of cooperatives since 1895:

1. **Voluntary and Open Membership** -- Anyone can join and leave freely. Iskander provides guided onboarding and a clear membership lifecycle.
2. **Democratic Member Control** -- Every member has an equal say. Enforced by one-member-one-vote, zero-knowledge secret ballots, and transparent AI.
3. **Member Economic Participation** -- Members contribute to and democratically control the cooperative's capital. Iskander tracks shares, surplus, and reserves.
4. **Autonomy and Independence** -- The cooperative controls its own destiny. Iskander is fully self-hosted with no corporate cloud dependency.
5. **Education, Training, and Information** -- The Clerk helps members learn about governance, cooperation, and their rights and responsibilities.
6. **Cooperation among Cooperatives** -- Federation protocol connects cooperatives for trade, collaboration, and mutual support.
7. **Concern for Community** -- Cooperatives work for the sustainable development of their communities. Iskander tracks progress and makes it visible.

---

## Learn more

See the [ROADMAP](ROADMAP.md) for the project timeline, or the [README](../README.md) for technical details.

Iskander is in active development. Phase C (the Radical MVP) is being built now.
