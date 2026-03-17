# Supply Chain Ethics & Material Passports

This directory operationalises Iskander Hearth's circular economy and ethical sourcing commitments.

## Files

| File | Description |
|---|---|
| [`material_passport_template.csv`](./material_passport_template.csv) | Ledger template — one row per component per node build |
| [`procurement_guidelines.md`](./procurement_guidelines.md) | How to source, vet, and configure hardware ethically |

---

## What Is a Material Passport?

A Material Passport is a public, per-component record of:
- **Where a part came from** (manufacturer, country, ITAD supplier)
- **Whether it was refurbished** (e-waste diverted in kg)
- **Its estimated embodied carbon** (kg CO₂e from manufacture)
- **Conflict mineral disclosure status** (3TG minerals: tantalum, tin, tungsten, gold)
- **Its expected end-of-life path** (resale, recycle, landfill avoided)

Cooperatives fill one CSV row per component when they build or procure a node.
The completed CSV becomes a public record — ideally committed to the cooperative's
Iskander OS instance and/or this repository's `supply_chain/passports/` directory.

## Why This Matters

Every GPU contains conflict minerals. Every server PSU contains tin solder sourced from
somewhere. Pretending otherwise is greenwashing. The Material Passport does not pretend
the supply chain is clean — it makes the cooperative's actual supply chain **visible and
improvable over time**.

A cooperative that honestly logs "conflict minerals: unverified" in year one and
"certified RMI-compliant supplier" in year three has made real, trackable progress.
That is the goal.
