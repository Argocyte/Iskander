# Hearth Builder Self-Assessment

**License:** CERN-OHL-S v2
**Purpose:** A voluntary checklist for new builders to assess their readiness.
            This is NOT a gatekeeping mechanism. You do not submit this to anyone.
            It exists so you can be honest with yourself about what you need to learn
            before shipping a node to someone who will depend on it.

---

## How to use this

Read each section. Answer honestly. If you mark something NO, it is an invitation
to learn — not a reason to stop. The Hearth Builder Network exists to help you fill gaps.

---

## Section 1 — Electronics

| Question | YES | NO | Notes |
|----------|-----|----|-------|
| I can use a multimeter to test voltage, continuity, and resistance | ☐ | ☐ | |
| I can solder through-hole components reliably (no cold joints) | ☐ | ☐ | |
| I can solder SMD components at SOIC-8 size or larger | ☐ | ☐ | Required for ATECC608B |
| I understand the ESD risk to CMOS ICs and use anti-static precautions | ☐ | ☐ | |
| I can read a basic wiring diagram and identify short circuits before powering up | ☐ | ☐ | |
| I have verified kill switch continuity before connecting to a live system | ☐ | ☐ | |

**If NO to any:** Practice on a spare PCB or breakout board. The Solidarity HAT
is low-cost (< $32) but the ATECC608B is sensitive to ESD. Build confidence first.

---

## Section 2 — Linux System Administration

| Question | YES | NO | Notes |
|----------|-----|----|-------|
| I can navigate a Linux filesystem and read log files | ☐ | ☐ | |
| I can start, stop, and diagnose systemd services | ☐ | ☐ | `systemctl`, `journalctl` |
| I can diagnose a failed service using `journalctl -u <service>` | ☐ | ☐ | |
| I can run a Python script from the command line and interpret error output | ☐ | ☐ | |
| I have successfully flashed an OS image to a USB or NVMe before | ☐ | ☐ | |
| I understand what `sudo` does and use it carefully | ☐ | ☐ | |

**If NO to Linux basics:** Work through a Linux fundamentals tutorial first.
The QA test script and daemon setup require comfortable shell use.

---

## Section 3 — 3D Printing

| Question | YES | NO | Notes |
|----------|-----|----|-------|
| I can produce a dimensionally accurate part in PETG (< ±0.3mm on critical holes) | ☐ | ☐ | |
| I understand print orientation and its effect on layer adhesion strength | ☐ | ☐ | |
| I can export an STL from OpenSCAD and load it into a slicer | ☐ | ☐ | |
| I know how to adjust perimeter count and infill for structural parts | ☐ | ☐ | |

**If NO:** Print the calibration cube and fan duct first. Verify the 30mm button
holes in `hitl_button_bracket_v1.scad` accept a Sanwa OBSA-30 before full chassis print.

---

## Section 4 — Cooperative & Legal

| Question | YES | NO | Notes |
|----------|-----|----|-------|
| I have read the CERN-OHL-S v2 license and understand my rights and obligations | ☐ | ☐ | Required |
| I understand that I must disclose the source location on distributed hardware | ☐ | ☐ | Required |
| I understand that I cannot make this hardware proprietary or add additional restrictions | ☐ | ☐ | Required |
| I have completed or plan to complete the CERN-OHL-S manufacturing checklist | ☐ | ☐ | Required for distribution |
| I intend to log my labour in the DisCO ledger (or equivalent) | ☐ | ☐ | Strongly recommended |

**The legal items above are not optional.** Distributing hardware without
source disclosure violates CERN-OHL-S v2 and harms the entire open hardware commons.

---

## Section 5 — Community Readiness

| Question | YES | NO | Notes |
|----------|-----|----|-------|
| I am willing to answer questions from people I ship nodes to | ☐ | ☐ | |
| I am willing to repair or replace a faulty node I shipped | ☐ | ☐ | |
| I have documented any modifications I made to the design | ☐ | ☐ | |
| I am connected to at least one other Hearth Builder for mutual support | ☐ | ☐ | |

---

## Your honest assessment

After completing the checklist:

**I am ready to build and ship nodes to others:**
```
[ ] YES — I have all skills, my micro-factory is set up, and I understand my obligations.
[ ] NOT YET — I need to develop: _______________________________________________
```

**What I need to learn next (write it down):**
```
_____________________________________________________________________________
_____________________________________________________________________________
```

**Who I will ask for help (a specific person or channel):**
```
_____________________________________________________________________________
```

---

Remember: no one is checking this. You are the only safeguard between a
defective node and someone who trusts it. That is not a burden — it is
the honour of being a maker in a cooperative network.
