# Project Iskander
## Sovereign Agentic Operating System for Distributed Cooperatives (DisCOs)

**Project Iskander** is an open-source, federated, anticipatory Agentic AI operating system designed to enable the next generation of cooperative economies. Iskander transforms local nodes ("Hearth") into self-governing, energy-aware, and financially transparent sovereign units that federate to form a recursive, democratic "Council of Cooperatives."

---

## 1. The Core Vision
Iskander is a direct implementation of the **10 CCIN Principles** (Cooperative, Commons, Identity, etc.) via code. We are building a "Hybrid Dual-Ledger System" where high-velocity Web3 transactions handle inter-node operations, backed by a high-trust, slow-velocity fiat reserve foundation.

## 2. The Architectural Stack
Iskander is defined by four operational pillars:

### A. The Brain (Iskander OS)
- **Framework:** FastAPI / LangGraph.
- **Protocol:** "Glass Box" Execution—every AI decision must include a mandatory rationale (LLM-generated explanation) and an ethical impact score.
- **Operational Logic:** Energy-Aware Agent Scheduler. All computational tasks are gated by real-time hardware telemetry (I2C sensors). No task executes if the node lacks the power to sustain it.

### B. The Heart (Iskander Hearth Hardware)
- **Tiered Hardware:** Solid-state, low-power PCBs designed for off-grid operations.
- **Hardware Sovereignty:** Physical kill-switches, NVMe-optimized logging, and "tmpfs" RAM-disk persistence to extend the lifespan of refurbished storage.

### C. The Hands (Stewardship & Governance)
- **Recursive Democracy:** Governance is not hierarchical; it is a dynamic, rotating Stewardship Council. 
- **Identity:** BrightID verification + ERC-4973 Soulbound Tokens (gSBT) for 1-member-1-vote rights.
- **REA Accounting:** Every action is recorded via the Valueflows standard, ensuring the cooperative ledger is transparent and mathematically verifiable.

### D. The Memory (Mesh Archive)
- **Data Fabric:** A content-addressed, encrypted, distributed mesh (IPFS).
- **Access Control:** Web3 Identity-based gating (ACLs). Only nodes with the appropriate gSBTs can decrypt specific federated logs.
- **Delta-Sync:** Automated state-reconciliation when nodes reconnect to the network.

---

## 3. The Ethical Operating Mandate (10 CCIN Principles)
As a contributor/agent of Iskander, you must adhere to the following logic:
1. **Glass Box Necessity:** Never commit a change to the ledger without a linked `CausalEvent` explaining *why*.
2. **Energy-First:** If hardware sensors indicate a low-power state, the system must prioritize survival over throughput.
3. **Federated, not Centralized:** Never rely on a single point of failure. All external data must be verified via decentralized oracles or federated consensus.
4. **Cooperative Primacy:** The Treasury Agent must always enforce the Mondragon pay-ratio principles.

---

## 4. Development Workflow & Safety
- **Middleware:** All agent execution is wrapped in `@energy_gated_execution` and `@requires_access`.
- **Conflict Resolution:** In the event of a "Split-Brain" scenario (network partition), the `Diplomat Agent` is triggered to facilitate human mediation before ledger reconciliation.
- **The "Emergency Veto":** The codebase must support an `EmergencyVeto` function—any node can halt an automated Council action if they provide a "Rationale Proof" demonstrating a violation of CCIN principles.

---

## 5. Implementation Roadmap
- [ ] **Phase 1: Stewardship Ledger:** Implement delegation/revocation logic.
- [ ] **Phase 2: Hearth Driver:** Complete the `@energy_gated_execution` middleware.
- [ ] **Phase 3: Mesh Archive:** Integrate IPFS pinning with ACLs.
- [ ] **Phase 4: Fiat-Crypto Bridge:** Implement the solvency-threshold Circuit Breaker.

---

*“To build the Commons, we must first build the sovereign tool.”*