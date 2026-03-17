# CERN-OHL-S v2 Manufacturing Compliance Checklist

**License:** CERN-OHL-S v2
**Reference:** CERN-OHL-S v2 Sections 3, 4, 5 (manufacturing and distribution obligations)
**Complete before every batch of distributed nodes.**

> This checklist operationalises the legal requirements of CERN-OHL-S v2 for a
> Maker-Coop or FabLab producing and distributing Iskander Hearth hardware.
> It is not legal advice. For a novel distribution context (commercial resale,
> export to restricted jurisdictions, institutional procurement), consult a
> qualified lawyer familiar with open hardware licensing.

---

## Section A — Source Availability

| # | Requirement | How to satisfy | Verified |
|---|-------------|---------------|---------|
| A1 | The full source (all design files, BOMs, firmware, documentation) must be available to recipients | Include repository URL on packaging. Commit all changes before shipping. | ☐ |
| A2 | Source must be available for at least as long as the hardware is distributed | Host on durable public infrastructure (GitHub + IPFS mirror). | ☐ |
| A3 | The source location notice on the Solidarity HAT PCB `B.SilkS` layer must be present on fabricated boards | Verify in KiCad PCB file before submitting to fab. | ☐ |
| A4 | Any modified design files must be available under CERN-OHL-S v2 before distribution of modified hardware | Push modified files to a publicly accessible repository before shipping. | ☐ |

---

## Section B — License Propagation

| # | Requirement | How to satisfy | Verified |
|---|-------------|---------------|---------|
| B1 | Every distributed node must be accompanied by a copy or clear reference to the CERN-OHL-S v2 license text | Include printed license summary card in box. URL: https://ohwr.org/cern_ohl_s_v2.txt | ☐ |
| B2 | No additional restrictions may be placed on recipients beyond CERN-OHL-S v2 | Review any sales agreement, warranty, or support terms for conflicting clauses. | ☐ |
| B3 | If you sublicense or resell, the sub-licensee has the same rights as you | Confirm this in any reseller agreement. | ☐ |

---

## Section C — Modifications and Derivatives

| # | Requirement | How to satisfy | Verified |
|---|-------------|---------------|---------|
| C1 | All modifications to source files must be documented | Maintain a `CHANGES.md` in your fork with: date, what changed, why. | ☐ |
| C2 | Modified hardware must clearly state it has been modified from the original | Affix "Modified from Iskander Hearth [version]" to the chassis or documentation. | ☐ |
| C3 | Derivative designs must be released under CERN-OHL-S v2 | Confirm license file in your fork's repository. | ☐ |
| C4 | You may not use trademarks to imply endorsement by the original project | Do not claim your build is "official" or "endorsed" by Iskander Hearth project. | ☐ |

---

## Section D — Patent Non-Assertion

| # | Requirement | How to satisfy | Verified |
|---|-------------|---------------|---------|
| D1 | By distributing under CERN-OHL-S v2, you grant a patent licence for the covered design | Review whether your organisation holds any patents that read on this design. If so, document the grant. | ☐ |
| D2 | You may not initiate patent litigation against recipients for their use of the design | Confirm with your organisation's legal counsel if applicable. | ☐ |

---

## Section E — Physical Marking Requirements

| # | Requirement | On which component | How to satisfy | Verified |
|---|-------------|-------------------|---------------|---------|
| E1 | Source location notice | Solidarity HAT PCB (B.SilkS) | Present in KiCad file: "Source: [repository URL] CERN-OHL-S v2" | ☐ |
| E2 | License reference | Packaging / setup card | Include CERN-OHL-S v2 URL on setup card | ☐ |
| E3 | OSHWA UID (when certification obtained) | Solidarity HAT PCB (B.SilkS) | Add UID after OSHWA application approval | ☐ |
| E4 | Build attribution | Material Passport | Include builder cooperative ID, build date, node serial | ☐ |
| E5 | Modification disclosure (if modified) | External label or documentation | "Modified from Iskander Hearth v1.0 by [Coop name] — Changes: [link]" | ☐ |

---

## Section F — Documentation Completeness

| # | Document | Present | Version |
|---|----------|---------|--------|
| F1 | `boms/solidarity_hat_bom.csv` | ☐ | |
| F2 | `assembly_guides/installing_solidarity_hat.md` | ☐ | |
| F3 | `supply_chain/passports/solidarity_hat_passport.csv` | ☐ | |
| F4 | `pcb/solidarity_hat/kicad/` (all KiCad source files) | ☐ | |
| F5 | `pcb/solidarity_hat/gerbers/` (fabrication outputs) | ☐ | |
| F6 | `firmware/solidarity_hat/` (all daemon source files) | ☐ | |
| F7 | `enclosures/hearth_chassis_v2.scad` | ☐ | |
| F8 | This checklist, completed and signed | ☐ | |

---

## Section G — OSHWA Certification (recommended, not required by CERN-OHL-S)

The Open Source Hardware Association (OSHWA) certification is a voluntary
declaration that this hardware meets the Open Source Hardware Definition.
It is not required by CERN-OHL-S v2 but is strongly recommended for:
- Building trust with buyers and partner coops
- Appearing in the OSHWA certification directory
- Demonstrating compliance to institutional buyers

**Steps to obtain OSHWA UID for Solidarity HAT v1:**
1. Verify all CERN-OHL-S v2 sections above are satisfied.
2. Create an account at certification.oshwa.org.
3. Complete the certification form: hardware type, license, source URL, documentation.
4. Submit. Review typically takes 2–4 weeks.
5. Add the UID to `B.SilkS` layer of the KiCad PCB file.
6. Update `boms/solidarity_hat_bom.csv` field `oshwa_uid`.

---

## Signoff

| Field | Value |
|-------|-------|
| Builder cooperative | |
| Checklist completed by | |
| Date | |
| Batch serial range | |
| Repository commit hash | |
| Known deviations (if any) | |

A completed, signed copy of this checklist must be retained by the builder
cooperative for a minimum of 7 years, or the anticipated service life of
the distributed hardware, whichever is longer.
