# Bills of Materials

Each tier has a paired CSV (machine-readable BOM) and Markdown explainer (human-readable rationale).

## CSV Column Reference

| Column | Description |
|---|---|
| `component_id` | Unique ID (e.g. `T1-001`). Prefix: T1=Seed, T2=Commons, T3=Federation |
| `category` | Compute / Memory / Storage / GPU / Networking / Power / Security / Sensors / Cooling / Chassis |
| `component_name` | Human-readable name |
| `specs` | Key technical specifications |
| `refurbished_priority` | `HIGH` = prefer used; `MEDIUM` = used acceptable; `NEW_ONLY` = safety/reliability requires new |
| `qty` | Quantity per node build |
| `estimated_cost_usd` | Approximate USD cost at time of last revision (refurbished pricing where applicable) |
| `source_class` | `ITAD` = IT Asset Disposition reseller; `Consumer` = retail; `OEM` = direct/distributor; `DIY` = self-fabricated |
| `notes` | Repair, sourcing, sustainability, or compatibility notes |

## Sourcing Guidance

- **ITAD suppliers** (recommended for refurbished): Newegg Refurbished, ServerMonkey, IT Creations, BackMarket Business, local e-waste brokers
- **Verify seller grades:** Ask for "Grade A" or "Certified Refurbished" with 90-day minimum warranty
- **Conflict minerals:** All GPUs contain tantalum, tin, tungsten, gold (3TG). Log origin in the Material Passport (`supply_chain/material_passport_template.csv`)
- **Energy labels:** Prefer PSUs with 80 PLUS Gold or Platinum certification
