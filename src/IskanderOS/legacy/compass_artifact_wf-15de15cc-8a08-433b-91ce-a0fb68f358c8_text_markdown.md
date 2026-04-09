# Iskander: a complete FOSS architecture map for cooperative AI + Web3

**Every layer of a cooperative AI + Web3 stack can be built from actively maintained, Docker-deployable open-source software today.** This architecture map identifies the best real, installable FOSS tool for each component of Iskander — a system combining decentralized infrastructure, blockchain governance, AI agents, human-in-the-loop deliberation, and multi-channel member interfaces. The full stack runs on Docker Compose with Traefik as the routing layer, requiring roughly **32 GB RAM and 500 GB SSD** for a development deployment, or **128 GB RAM, GPU, and 2 TB SSD** for production with embedded Wikipedia. All recommended tools had active commits in 2025–2026 and carry permissive or copyleft FOSS licenses.

---

## Layer 1: commons infrastructure anchors decentralized storage and identity

This foundational layer provides content-addressed storage, permanent archival, self-sovereign identity, and a searchable local Wikipedia corpus — the shared knowledge commons that AI agents and humans draw from.

### Decentralized storage

**Kubo (IPFS)** is the primary content-addressed storage node. The Go implementation ships as `ipfs/kubo` on Docker Hub (MIT/Apache-2.0), exposing an HTTP gateway on port 8080, an RPC API on port 5001, and a libp2p swarm on port 4001. Version **v0.40.1** is current, with active development through 2026. A single Docker run command launches a full node:

```
docker run -d --name ipfs -e IPFS_PROFILE=server \
  -v ipfs_data:/data/ipfs -p 4001:4001 \
  -p 127.0.0.1:8080:8080 -p 127.0.0.1:5001:5001 \
  ipfs/kubo:v0.40.1
```

**AR.IO Node** (`github.com/ar-io/ar-io-node`, AGPL-3.0) serves as the Arweave permaweb gateway, indexing transactions into SQLite with GraphQL query support and ArNS name resolution. It deploys via `docker compose up --build` and runs on hardware as modest as a Raspberry Pi. For Filecoin integration, **Lotus** (`filecoin-project/lotus`, Apache-2.0) provides the reference node, though its full chain sync is resource-heavy.

| Tool | GitHub | Docker Image | License |
|------|--------|-------------|---------|
| Kubo (IPFS) | `ipfs/kubo` | `ipfs/kubo:v0.40.1` | MIT/Apache-2.0 |
| AR.IO Node | `ar-io/ar-io-node` | Docker Compose | AGPL-3.0 |
| Lotus (Filecoin) | `filecoin-project/lotus` | `filecoin/lotus` | Apache-2.0/MIT |

### Decentralized identity and verifiable credentials

**Walt.id Identity** (`github.com/walt-id/waltid-identity`, Apache-2.0) is the recommended all-in-one identity stack. It provides Issuer, Verifier, and Wallet APIs supporting W3C Verifiable Credentials in JWT, SD-JWT, and JSON-LD formats plus ISO mdoc credentials and OpenID4VC protocols. DID methods include did:key, did:jwk, did:web, did:ebsi, and did:cheqd. The entire stack deploys with `cd docker-compose && docker compose up`. It was **actively updated through February 2026** with Helm charts for Kubernetes scaling.

For Hyperledger Aries interoperability, **ACA-Py** (`openwallet-foundation/acapy`, Apache-2.0) is the production-ready SSI agent, now maintained by the OpenWallet Foundation. Its Docker image `ghcr.io/openwallet-foundation/acapy-agent:py3.12-1.2-lts` supports AnonCreds, W3C VC JSON-LD, DIDComm messaging, and multi-tenancy. **Veramo** (`decentralized-identity/veramo`, Apache-2.0) offers a modular JavaScript alternative with plugin-based DID management if TypeScript integration is preferred.

### Wikipedia as a searchable local corpus

English Wikipedia contains **~7 million articles and 5+ billion words**. The compressed XML dump (`enwiki-YYYYMMDD-pages-articles.xml.bz2`) is roughly **24 GB**; uncompressed XML runs to ~90 GB. Dumps are released monthly at `dumps.wikimedia.org` under CC-BY-SA 4.0.

**Kiwix-serve** (`github.com/kiwix/kiwix-tools`, GPL-3.0) provides instant human-readable access. The Docker image `ghcr.io/kiwix/kiwix-serve` serves ZIM-format archives with HTTP search API endpoints (`/search?pattern=<query>`, `/suggest?term=<term>`). The English Wikipedia ZIM files come in three sizes: **Maxi (~100 GB** with images), **Nopic (~25 GB**, text only), and **Mini (~5 GB**, intros only). Deploy with:

```
docker run -v /path/to/zim:/data -p 8080:8080 \
  ghcr.io/kiwix/kiwix-serve '*.zim'
```

For AI-agent-accessible semantic search, the pipeline is: **WikiExtractor** (`attardi/wikiextractor`, AGPLv3) extracts clean plaintext JSON from the XML dump → chunk into ~500-token passages (~**30 million chunks**) → embed with an open model like `BAAI/bge-small-en-v1.5` (384 dimensions) via Ollama or sentence-transformers → store in **Qdrant** (`qdrant/qdrant`, Apache-2.0). Estimated vector storage: **~46 GB** at 384 dimensions, or **~92 GB** at 768 dimensions. Pre-built Wikipedia embeddings exist on Hugging Face (`Cohere/wikipedia-22-12-en-embeddings`, ~35M passages), which can accelerate initial loading.

---

## Layer 2: blockchain governance from L3 chains to cooperative smart contracts

### Deploying an Ethereum L3 for development and production

**Arbitrum Nitro Testnode** (`github.com/OffchainLabs/nitro-testnode`) is the fastest path to a local L1→L2→L3 chain. Running `./test-node.bash --init --l3node` spins up a complete stack via Docker Compose: a dev-mode Geth L1, an Arbitrum L2 sequencer with batch-poster and validator, and an L3 node. The L2 listens on ports 8547/8548, the L3 on 3347/3348. It supports custom gas tokens (`--l3-fee-token`) and token bridges (`--l3-token-bridge`). The underlying **Nitro** engine (`OffchainLabs/nitro`) uses BSL-1.1 licensing — free for L3s settling to Arbitrum One/Nova, otherwise requiring Arbitrum Expansion Program approval. Hardware: **8+ cores, 16 GB+ RAM** for full nodes.

**OP Stack** (`github.com/ethereum-optimism/optimism`, MIT) provides the alternative L2/L3 framework. Docker images exist for op-node, op-batcher, op-proposer, and op-challenger at `us-docker.pkg.dev/oplabs-tools-artifacts/images/`. Community-maintained **simple-optimism-node** (`smartcontracts/simple-optimism-node`, MIT) offers the easiest Docker Compose setup. Sequencer requirements: **16 GB RAM, 4 cores minimum**; archive nodes need 2 TB+ SSD and 32 GB RAM.

For lightweight local development without running a full L3, **Foundry/Anvil** (`github.com/foundry-rs/foundry`, MIT/Apache-2.0) is the clear winner. The Docker image `ghcr.io/foundry-rs/foundry:latest` provides Anvil (local testnet), Forge (testing), and Cast (CLI) in a single container. Anvil offers instant mining, state forking, impersonation, and sub-second block times.

### DAO governance contracts ranked by cooperative suitability

Not all DAO frameworks are equal for cooperatives. Token-weighted plutocratic voting (one-dollar-one-vote) is the default in most systems. Iskander needs frameworks that support **one-person-one-vote, reputation-based governance, or minority protections**.

**Colony** (`github.com/JoinColony/colonyNetwork`, GPL-3.0) is the most cooperative-native framework. Voting power is **earned through contributions, not purchased** — reputation accrues in specific domains and naturally decays over time, requiring ongoing participation. Its lazy-consensus model means most decisions proceed without votes unless objected to, reducing governance fatigue. Colony lacks official Docker images but deploys on Arbitrum.

**Aragon OSx** (`github.com/aragon/osx`, AGPL-3.0) provides the most modular plugin architecture with a critical feature for cooperatives: **Addresslist Voting** — one-address-one-vote governance without token weighting. Additional plugins include token voting, optimistic governance (propose + veto), lock-to-vote, and vote-escrowed NFT governance. Aragon's `gov-app-template` provides a full-stack governance UI template.

**DAOhaus/Moloch v3 (Baal)** (`github.com/Moloch-Mystics/Baal`, MIT contracts) uniquely features **ragequit** — members who disagree with a proposal can burn their shares and withdraw their proportional treasury assets. This provides fundamental minority protection, making it inherently cooperative-friendly.

**OpenZeppelin Governor** (`github.com/OpenZeppelin/openzeppelin-contracts`, MIT, v5.6.0) is the most audited and extensible base. Its modular counting system allows custom implementations of quadratic or conviction voting. The `GovernorCountingSimple` contract provides For/Against/Abstain, while `TimelockController` manages treasury execution. **Snapshot** (`github.com/snapshot-labs`, MIT) handles gasless off-chain voting with 400+ strategies including quadratic, ranked-choice, and approval voting — self-hostable via snapshot-v1 + snapshot-hub.

| Framework | Cooperative Model | On/Off-Chain | Key Feature | License |
|-----------|------------------|-------------|-------------|---------|
| Colony | Reputation-weighted | On-chain | Earned reputation, lazy consensus | GPL-3.0 |
| Aragon OSx | One-address-one-vote | On-chain | Plugin architecture, addresslist voting | AGPL-3.0 |
| DAOhaus/Baal | Share-weighted + ragequit | On-chain | Minority exit protection | MIT |
| OZ Governor | Extensible (any model) | On-chain | Most audited, modular counting | MIT |
| Snapshot | Flexible (400+ strategies) | Off-chain | Gasless, quadratic voting | MIT |

---

## Layer 3: AI agents with local LLMs, MCP, and RAG

### OpenClaw is real and purpose-built for multi-channel AI

**OpenClaw** (`github.com/openclaw/openclaw`, MIT) is an actively maintained personal AI assistant platform with **5,000+ GitHub stars** and ongoing 2025–2026 commits. It supports **20+ communication channels** including WhatsApp, Telegram, Slack, Discord, Matrix, Signal, iMessage, IRC, Microsoft Teams, and WebChat. The architecture features a Gateway control plane (ws://127.0.0.1:18789) with Pi agent runtime in RPC mode. Multi-agent setup includes nine specialized agents: planner, ideator, critic, surveyor, coder, writer, reviewer, and scout with group routing.

Docker support is available through community orchestration tools: **SwarmClaw** (`github.com/swarmclawai/swarmclaw`) enables multi-agent orchestration across machines using OpenClaw gateways, while **OpenClaw Mission Control** (`github.com/abhi1693/openclaw-mission-control`) provides centralized operations. The **Awesome OpenClaw Skills** catalog lists 5,400+ skills, and **Awesome OpenClaw Agents** provides 199 production-ready agent templates.

For connecting OpenClaw to local Wikipedia, **AnythingLLM** (`github.com/Mintplex-Labs/anything-llm`, MIT) is the simplest path. Its Docker image `mintplexlabs/anythingllm` bundles RAG, AI agents, and a no-code agent builder with MCP compatibility and built-in vector database support. It connects to Ollama for local inference and supports Chroma, Qdrant, Weaviate, and other vector stores. With **57,700+ GitHub stars**, it is the most popular all-in-one local RAG solution. Alternatively, **LlamaIndex** (`run-llama/llama_index`, MIT) and **Haystack** (`deepset-ai/haystack`, Apache-2.0) provide more programmable RAG pipeline frameworks — Haystack's **Hayhooks** module can even expose pipelines as MCP servers.

### MCP servers provide standardized AI tool access

The **Model Context Protocol** (`github.com/modelcontextprotocol`, MIT) by Anthropic standardizes how AI applications access tools. The official reference servers repository (`modelcontextprotocol/servers`) includes servers for filesystem access, persistent memory (knowledge graph), Git operations, web fetching, PostgreSQL, SQLite, GitHub integration, and sequential thinking — all MIT-licensed.

Docker has partnered with Anthropic to containerize MCP servers under the `mcp/` namespace on Docker Hub, with a **Docker MCP Registry** (`github.com/docker/mcp-registry`) cataloging available container images. The Docker MCP Toolkit provides centralized management with container isolation for each server. The **awesome-mcp-servers** list (`github.com/wong2/awesome-mcp-servers`) curates hundreds of community servers. Notable ones include Docker operations via MCP (`QuantGeekDev/docker-mcp`, MIT), GraphRAG memory (`cognee-mcp`), and browser automation (`browser-use`).

### Local LLM serving via Ollama

**Ollama** (`github.com/ollama/ollama`, MIT) is the simplest local LLM server. The Docker image `ollama/ollama` exposes an OpenAI-compatible REST API on port 11434 and supports 100+ models. For agent workloads, the recommended models by hardware tier are:

- **8 GB VRAM** (RTX 4060): Qwen 3.5 9B (Q4_K_M) — fits in 6.6 GB, ~55 tokens/sec
- **16 GB VRAM** (RTX 4070 Ti): Mistral Small 3 24B or Qwen 3 14B
- **24 GB VRAM** (RTX 4090/5090): Qwen 3 32B for coding, Mistral Small 3 24B for general use — competitive with GPT-4
- **Apple Silicon** (M4 Pro/Max, 36–128 GB unified): Can run 70B+ models via MLX

**LocalAI** (`github.com/mudler/LocalAI`, MIT, `localai/localai`) provides a more comprehensive OpenAI API drop-in replacement with 35+ backends, built-in MCP support, and AI agent capabilities. **vLLM** (`vllm-project/vllm`, Apache-2.0, `vllm/vllm-openai`) offers maximum throughput for GPU-equipped production deployments with PagedAttention optimization.

---

## Layer 4: human-in-the-loop via Loomio and deliberation platforms

### Loomio provides the core deliberation engine

**Loomio** (`github.com/loomio/loomio`, AGPL-3.0) is the primary HITL component. The **loomio-deploy** repository (`github.com/loomio/loomio-deploy`, updated November 2025) provides a production Docker Compose stack with seven services: the Rails app (`loomio/loomio`), a background worker, PostgreSQL, Redis 5.0, a Haraka SMTP mail-in server, Nginx with Let's Encrypt auto-SSL, and a Hocuspocus WebSocket server for live collaboration.

Loomio's REST API (current "b1" version) enables full programmatic control — **critical for AI agent integration**:

- `POST /api/b1/discussions` creates discussion threads with title, description, and recipient targeting
- `POST /api/b1/polls` creates proposals with seven poll types: proposal, poll, count, score, ranked_choice, meeting, and dot_vote
- `GET /api/b1/polls/:id` reads vote outcomes including individual stances
- `POST /api/b1/memberships` manages group membership and invitations

Authentication uses per-user API keys, with bot accounts supported via a profile setting. **Outgoing webhooks** notify external systems (including Matrix, Slack, Discord, Mattermost) when events occur — new threads, new polls, poll closings. This means an AI agent can create a proposal via the API, and Loomio will notify the Matrix channel when voting completes.

### Polis and Decidim complement Loomio

**Polis** (`github.com/compdemocracy/polis`, AGPL-3.0) provides AI-powered consensus-finding at scale. Its Docker Compose stack includes a Node.js server, a **Clojure-based ML engine** (PCA + k-means clustering), PostgreSQL, and React clients. Participants submit short statements and vote agree/disagree/pass; the system automatically identifies opinion clusters and areas of broad agreement. It was notably used by Taiwan's vTaiwan process for national policy deliberation.

**Decidim** (`github.com/decidim/decidim`, AGPL-3.0) is the full-featured participatory democracy platform used by 400+ cities. Docker images are available at `ghcr.io/decidim/decidim:latest` with a dedicated Docker repository. It provides participatory budgeting, proposals with amendments, auditable voting, assemblies, surveys, and accountability tracking, all accessible via a **GraphQL API**.

---

## Layer 5: member interface through Matrix and governance dashboards

### Matrix/Element as the unified messaging layer

**Synapse** (`github.com/element-hq/synapse`, AGPL-3.0) is the production Matrix homeserver, available as `matrixdotorg/synapse:latest` on Docker Hub. **Element Web** (`element-hq/element-web`, AGPL-3.0, `vectorim/element-web:latest`) provides the rich web client with E2EE, voice/video via LiveKit, spaces, and threads. The **Element Docker Demo** repository (`element-hq/element-docker-demo`) provides a complete Matrix 2.0 stack via Docker Compose including Synapse, Element Web, Element Call, Matrix Authentication Service, LiveKit, PostgreSQL, and Nginx.

Matrix bridges from the **mautrix** family connect every major messaging platform, all Docker-ready at `dock.mau.dev/mautrix/$bridge:latest`:

- **mautrix-telegram**, **mautrix-whatsapp**, **mautrix-discord**, **mautrix-signal**, **mautrix-slack** (all AGPL-3.0)

For AI agent bridging, **Maubot** (`github.com/maubot/maubot`, AGPL-3.0, `dock.mau.dev/maubot/maubot:latest`) is the best option — a plugin-based bot system with a web management UI. Plugins receive messages, can call AI backends, and post responses back into Matrix rooms.

### Governance dashboards

**Grafana** (`github.com/grafana/grafana`, AGPL-3.0, `grafana/grafana:latest`) serves operational dashboards — treasury balances, participation metrics, on-chain activity — with 50+ panel types and 100+ data source plugins. **Metabase** (`github.com/metabase/metabase`, AGPL-3.0, `metabase/metabase:latest`) provides the member-facing analytics layer with a visual query builder accessible to non-technical cooperative members. For a custom governance portal, **Refine** (`github.com/refinedev/refine`, MIT, **29,000+ stars**) offers a headless React meta-framework with CRUD, authentication, access control, and real-time updates — with Dockerfile examples at `refinedev/dockerfiles`.

---

## Cross-cutting: orchestration, vector search, and existing cooperative AI projects

### Vector database recommendation for Wikipedia-scale embeddings

After evaluating six vector databases, **Qdrant** (`github.com/qdrant/qdrant`, Apache-2.0) is the top recommendation for Iskander. Written in Rust, it deploys with a single command (`docker run -p 6333:6333 qdrant/qdrant`), achieves **up to 97% RAM reduction** via quantization (making 50M+ Wikipedia vectors feasible on a single node), and delivers excellent single-node performance with SIMD acceleration and io_uring async I/O. The v1.17.x series (2026) is migrating to Gridstore for further performance gains.

**Weaviate** (`weaviate/weaviate`, BSD-3-Clause, `semitechnologies/weaviate`) is the strongest alternative with 20+ built-in ML model integrations, hybrid search (vector + BM25), and horizontal scaling. **pgvector** (`pgvector/pgvector`, PostgreSQL License, `pgvector/pgvector:pg18`) complements either as a simpler vector store for relational data, especially with **pgvectorscale** adding StreamingDiskANN for 28x lower p95 latency at 50M vectors.

### Docker Compose orchestration strategy

For Iskander's 15+ services, start with **Docker Compose + Traefik + Portainer**:

- **Traefik** (`github.com/traefik/traefik`, MIT, `traefik:v3.6.2`) provides automatic service discovery via Docker labels — no manual config updates when adding services. Built-in Let's Encrypt SSL, load balancing, and a web dashboard.
- **Portainer CE** (`github.com/portainer/portainer`, zlib, `portainer/portainer-ce`) adds a visual management UI for all containers, volumes, and networks.
- Migrate to **K3s** (`github.com/k3s-io/k3s`, Apache-2.0) when multi-node scaling is needed — lightweight Kubernetes in a single 512 MB binary.

### Existing projects at the intersection of AI + blockchain + governance

**Olas/Autonolas** (`github.com/valory-xyz/open-autonomy`, Apache-2.0) is the most directly relevant precedent. It provides a framework for building autonomous agent services that operate in a decentralized manner, with smart contracts as on-chain registries (agents minted as NFTs), OLAS token governance via veOLAS staking, and a "Governatooorr" AI governance delegate for DAOs. Docker images are available for local development.

The **ASI Alliance** (formed June 2024) merged Fetch.ai, SingularityNET, and Ocean Protocol into the largest decentralized AI entity. **Fetch.ai's uAgents** (`fetchai/uAgents`, Apache-2.0) provides lightweight Python agents that auto-register on blockchain. **SingularityNET's snet-daemon** (`singnet/snet-daemon`, Apache-2.0) acts as a sidecar proxy for decentralized AI service marketplace access.

The **Metagov** project (`github.com/metagov`) — a 501(c)(3) research collective — builds governance infrastructure including **PolicyKit** (governance procedures for social platforms), a **Metagov Gateway** (unified API connecting Loomio, Open Collective, SourceCred, Discourse), and **DAOstar** (DAO standards). Their Interop project funded 14 deliberative tools including Talk to the City, Pairwise, and Harmonica.

**Hylo** (`github.com/Hylozoic`, AGPL-3.0) demonstrates cooperative social coordination with nested/composable groups, cross-group collaboration, and a partnership with Holochain for peer-to-peer decentralization.

---

## Conclusion: a deployable cooperative AI stack exists today

The complete Iskander architecture requires approximately **18 Docker services** in a minimal configuration: Kubo (IPFS), AR.IO (Arweave), Walt.id (DID/VC), Kiwix-serve (Wikipedia browsing), Qdrant (vector search), Anvil or Nitro Testnode (blockchain), Ollama (LLM), OpenClaw (AI agents), AnythingLLM (RAG), MCP servers (tool access), Loomio (deliberation), Polis (consensus-finding), Synapse (Matrix homeserver), Element Web (client), Maubot (AI-to-human bridge), Grafana (dashboards), Traefik (routing), and Portainer (management).

Three architectural choices stand out as non-obvious. First, **Colony's reputation-based governance** — where voting power is earned through contribution rather than purchased — aligns most naturally with cooperative principles and should be evaluated ahead of the more common token-weighted models. Second, the combination of **Loomio's API + Matrix webhooks + Maubot** creates a complete AI-to-human governance loop: an AI agent creates a proposal via Loomio's REST API, Loomio notifies a Matrix room via webhook, members deliberate and vote, and the outcome is readable via the same API. Third, **Polis's ML-powered consensus identification** offers something no other tool provides — the ability to automatically surface areas of agreement across large groups, which could feed directly into AI agent decision-making.

The primary gap in existing tooling is a unified orchestrator that connects all layers. No existing project fully combines AI agents + blockchain governance + human deliberation in a single deployable stack. Iskander would be the first, building on Olas/Autonolas's agent-blockchain pattern and Metagov's governance-middleware approach. The infrastructure exists; the integration layer is what remains to be built.