# DisCO Labour Accounting Specification

**License:** CERN-OHL-S v2 / MIT (software)
**Phase:** 8 — Distributed Cooperative Manufacturing
**Reference:** DisCO.coop Governance Model v3 (disco.coop/governance)

---

## Overview

DisCO (Distributed Cooperative Organization) tracks three types of labour value.
This spec defines how Iskander Hearth build labour is recorded in the cooperative
ledger and how it maps to the ActivityPub-federated value-tracking system.

---

## 1. Value Types

### 1.1 Productive Value
Direct labour that produces a deliverable — hardware that ships, code that runs.

Examples:
- Assembling a node chassis
- Soldering the Solidarity HAT
- Running the QA test suite
- Flashing OS images
- Packaging and shipping

### 1.2 Reproductive Value
Labour that sustains the conditions for productive work.

Examples:
- Updating assembly guides after a design change
- Maintaining the component supply chain (sourcing, lead times)
- Managing the bill of materials
- Coordinating group purchasing orders

### 1.3 Care Value
Labour that sustains the community and its people.

Examples:
- Training a new builder to assemble nodes
- Providing support to someone debugging a failed QA test
- Facilitating governance meetings
- Welcoming new members to the federation

---

## 2. Labour Record Schema

Each labour record is a JSON object. Records are stored in the Iskander OS
cooperative ledger and federated via ActivityPub to peer nodes.

```json
{
  "record_id": "uuid-v4",
  "version": "1.0",
  "cooperative_id": "string — unique ID of the recording cooperative",
  "contributor_handle": "string — contributor's federation handle (@user@node)",
  "value_type": "productive | reproductive | care",
  "task_category": "string — see Section 3",
  "task_description": "string — human-readable description",
  "node_serial": "string | null — IH-T2-YYYYMMDD-NNN if productive build",
  "hours": "number — decimal hours (0.25 precision minimum)",
  "timestamp_start": "ISO 8601 datetime",
  "timestamp_end": "ISO 8601 datetime",
  "logged_at": "ISO 8601 datetime",
  "materials_cost_usd": "number | null — direct material cost if applicable",
  "notes": "string | null"
}
```

---

## 3. Task Categories

### Productive
| Category | Examples |
|----------|---------|
| `assembly.chassis` | Printing, cutting, assembling chassis panels |
| `assembly.hat` | PCB assembly, soldering Solidarity HAT |
| `assembly.wiring` | Internal wiring, JST connector crimping |
| `assembly.final` | Full node integration, cable management |
| `testing.qa` | Running qa_automated_test.sh, acoustic measurement |
| `flashing.os` | OS image verification and NVMe flashing |
| `shipping.pack` | Packaging, Material Passport, labelling |
| `shipping.dispatch` | Carrier drop-off, tracking entry |

### Reproductive
| Category | Examples |
|----------|---------|
| `docs.update` | Editing assembly guides, updating BOM |
| `supply_chain.sourcing` | Finding suppliers, negotiating group orders |
| `supply_chain.receiving` | Receiving, inspecting, and logging components |
| `infra.tools` | Maintaining micro-factory equipment (printer calibration, etc.) |

### Care
| Category | Examples |
|----------|---------|
| `training.builder` | Teaching a new builder how to assemble a node |
| `support.debug` | Helping a builder resolve a hardware or software problem |
| `governance.meeting` | Participating in cooperative governance sessions |
| `community.onboarding` | Welcoming and orienting new cooperative members |

---

## 4. Recording Labour (CLI)

The Iskander OS cooperative ledger provides a CLI for recording labour:

```bash
# Record 1.5 hours of node assembly
iskander-ledger log \
  --type productive \
  --category assembly.final \
  --hours 1.5 \
  --node-serial IH-T2-20260316-001 \
  --description "Full Tier 2 node assembly and wiring"

# Record 0.5 hours of documentation update
iskander-ledger log \
  --type reproductive \
  --category docs.update \
  --hours 0.5 \
  --description "Updated flash-and-ship procedure for new NVMe duplicator"

# Record 2 hours of builder training
iskander-ledger log \
  --type care \
  --category training.builder \
  --hours 2.0 \
  --description "Trained @newbuilder@coop2.example on Solidarity HAT assembly"
```

---

## 5. Cooperative Dividend Calculation

The COGS calculator agent uses labour records to produce two outputs:

### 5a. Node cost floor
Minimum price that covers all labour at the cooperative's internal wage rate
plus material costs. Ensures no node is sold at a loss.

```
cost_floor = Σ(hours × hourly_rate) + Σ(materials_cost) + overhead_factor
```

`overhead_factor` is set per cooperative (typically 1.15–1.30 to cover
infrastructure, equipment amortisation, and governance time).

### 5b. Cooperative dividend pool
At the end of each accounting period, surplus revenue above cost_floor is
distributed to contributors proportional to their logged care and reproductive
value (productive value is already compensated in the wage calculation).

```
dividend_pool = total_revenue - Σ(cost_floor) - reserve_fund
dividend_share_i = (care_hours_i + repro_hours_i) / Σ(care + repro hours)
dividend_i = dividend_pool × dividend_share_i
```

---

## 6. ActivityPub Federation

Labour records are published as ActivityPub `Note` objects with a custom
`iskander:LaborRecord` type extension. This allows:

- Sister nodes to aggregate labour statistics across the federation
- Transparent cooperative accounting viewable by all federation members
- Cross-cooperative dividend calculations for collaborative builds

```json
{
  "@context": ["https://www.w3.org/ns/activitystreams",
               "https://iskander-hearth.coop/ns/labor/v1"],
  "type": "Create",
  "object": {
    "type": "iskander:LaborRecord",
    "attributedTo": "https://coop1.example/users/alice",
    "content": "1.5h productive/assembly.final — Node IH-T2-20260316-001",
    "iskander:laborRecord": { ...full schema from Section 2... }
  }
}
```

Records are public by default. Contributors may set `to: ["as:unlisted"]` to
limit visibility to federation members only.

---

## 7. DisCO.coop Reference Implementation Compatibility

This schema is designed to map to the DisCO Governance Model v3 value tracking
primitives. The field mapping is:

| This spec | DisCO Model v3 |
|-----------|---------------|
| `value_type: productive` | Livelihood work |
| `value_type: reproductive` | Care work (infrastructure) |
| `value_type: care` | Care work (community) |
| `cooperative_id` | Member organisation ID |
| `contributor_handle` | Member ID |
| `hours` | Work units (converted at 1 unit = 1 hour) |

Validation against DisCO reference implementation: `qa_automated_test.sh`
includes a check that the ledger API endpoint is responsive. Full DisCO
protocol validation is performed during Phase 8 acceptance testing.
