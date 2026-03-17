# Acoustic Test Protocol v1

**License:** CERN-OHL-S v2
**Phase:** 7 — Thermal & Acoustic Validation
**Revision:** 1.0 | 2026-03-16

---

## 1. Objective

Verify that the Iskander Hearth Tier 2 node meets the following acoustic targets
during sustained Llama 3 inference:

| Deployment | Target | Measurement distance |
|------------|--------|---------------------|
| Living room | < 30 dBA | 2m |
| Shared office | < 35 dBA | 1m |
| Server closet | < 45 dBA | 0.5m |

The test is performed with Noctua NF-A12x25 PWM fans (P7-001) and GPU thermal
pads replaced (P7-003). A passing result at "shared office" is the **minimum
acceptance criterion** for a Tier 2 node.

---

## 2. Required Equipment

| Item | Specification | Notes |
|------|--------------|-------|
| SPL meter or calibrated app | Class 2 (±1.5 dB), A-weighted | NIOSH SLM app (iOS/Android) or Voltcraft SL-451 |
| Tape measure | ≥ 2m | For consistent measurement distance |
| Background noise monitor | Same SPL meter | Must measure and record ambient before test |
| Test workload | `ollama run llama3:8b` loop | See Section 4 |
| Thermal monitor | `nvidia-smi -l 1` | Confirm GPU at sustained load during test |

---

## 3. Test Environment Requirements

- Background noise (ambient) must be **≥ 10 dBA below** the target. For the 30 dBA target, ambient must be < 20 dBA. Test in early morning or after midnight in a quiet space.
- No other noise sources within 5m (HVAC off if possible, no traffic noise above 25 dBA).
- SPL meter at microphone height **1.2m** from floor, on a stand — do not hold by hand.
- Node on a hard surface (no carpet absorption artifacts). All panels closed.

---

## 4. Load Conditions

### 4a. Idle baseline
Node powered on, no active inference. Fan at minimum RPM. Record for 60 seconds.

### 4b. Sustained inference load
```bash
# Start Ollama inference loop (sustained CPU+GPU load)
while true; do
  echo "Summarize the cooperative economics literature in detail." \
    | ollama run llama3:8b
done &

# Monitor GPU temperature and fan RPM simultaneously
nvidia-smi --query-gpu=temperature.gpu,fan.speed,power.draw \
           --format=csv -l 2
```
Wait until GPU temperature stabilises (< 2°C change over 3 minutes). Record for **5 minutes** at stable load.

### 4c. Fan curve peak
```bash
# Force fans to maximum RPM for worst-case measurement
nvidia-smi --fan-speed 100 2>/dev/null || true
# For system fans: use fancontrol or BIOS manual curve
```
Record for 60 seconds. This establishes the upper acoustic bound.

### 4d. Post-throttle (P-state idle)
After stopping the inference loop, wait for `gpu_thermal_manager.sh` to lock the
GPU to 210 MHz P-state (≈ 5 minutes idle). Record for 60 seconds.

---

## 5. Measurement Procedure

1. Place SPL meter at the target distance from the **front panel** of the node.
   - Living room: 2m
   - Shared office: 1m
   - Server closet: 0.5m
2. Set SPL meter to: **A-weighting, Fast response, dBA**.
3. Record ambient (background) for 60 seconds before powering the node on.
4. Power on the node. Record **idle baseline** for 60 seconds.
5. Start inference load (Section 4b). Wait for thermal stabilisation.
6. Record **sustained inference** dBA reading every 10 seconds for 5 minutes.
   Enter each reading into `thermal_test_results_template.csv`.
7. Compute `Leq` (equivalent continuous sound level) over the 5-minute window:
   ```
   Leq = 10 × log10( (1/N) × Σ 10^(Li/10) )
   ```
   where Li is each 10-second A-weighted reading and N is the count.
8. Record **fan curve peak** (Section 4c) for 60 seconds.
9. Record **P-state idle** (Section 4d).
10. Power off node. Record ambient again (confirm it has not changed).

---

## 6. Pass / Fail Criteria

| Condition | Measurement | Pass threshold |
|-----------|-------------|---------------|
| Sustained inference Leq (living room) | 2m dBA | < 30 dBA |
| Sustained inference Leq (shared office) | 1m dBA | < 35 dBA |
| Sustained inference Leq (server closet) | 0.5m dBA | < 45 dBA |
| Idle (P-state locked) | 1m dBA | < 25 dBA |
| Fan peak | 1m dBA | Informational only |
| Ambient (before/after) | 1m dBA | Must be ≥ 10 dBA below target |

**Minimum acceptance criterion for Tier 2 deployment:** Sustained inference Leq < 35 dBA at 1m.

---

## 7. Troubleshooting High Noise Readings

| Symptom | Likely cause | Corrective action |
|---------|-------------|-------------------|
| > 40 dBA at 1m during inference | GPU fan at > 80% | Check GPU thermal pads (P7-003); re-apply if degraded |
| Buzzing / resonance at specific fan RPM | Fan resonance with chassis | Add foam gasket between fan and chassis (5mm open-cell foam) |
| > 35 dBA at idle | Minimum RPM set too high | Adjust fan curve in BIOS or with fancontrol; target ≤ 600 RPM idle |
| Failing at 2m but passing at 1m | Low-frequency content (< 200 Hz) | Check hard drive vibration (migrate to NVMe SSD if any spinning disk) |
| High noise after GPU thermal manager running | Power limit floor too high | Lower `HEARTH_GPU_FLOOR_W` by 10W and re-test |

---

## 8. Reporting

Record results in `thermal/thermal_test_results_template.csv`. Include:
- Node serial number
- Build date and builder cooperative
- All dBA readings per condition and distance
- GPU max temperature during sustained test
- Fan speeds (RPM) at each condition
- Pass/fail determination per deployment target

Completed acoustic test results should be attached to the node's Material Passport
(`supply_chain/passports/`) before shipping.
