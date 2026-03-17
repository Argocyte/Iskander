#!/usr/bin/env bash
# =============================================================================
# qa_automated_test.sh — Iskander Hearth Node Automated QA Test
# =============================================================================
# License  : CERN-OHL-S v2 / MIT (software)
# Phase    : 8 — Distributed Cooperative Manufacturing
#
# Run on a freshly assembled and flashed Iskander Hearth node to verify
# all hardware and software subsystems before shipping.
#
# USAGE:
#   sudo bash qa_automated_test.sh [--skip-gpu] [--skip-acoustic]
#
# OPTIONS:
#   --skip-gpu       Skip gpu-burn test (useful if no GPU in this tier)
#   --skip-acoustic  Skip acoustic prompt (non-interactive / CI use)
#
# OUTPUT:
#   Prints PASS/FAIL for each check.
#   Writes results to /var/log/iskander/qa_results_<serial>_<date>.log
#   Exits with 0 if all required checks pass, 1 if any required check fails.
#
# REQUIRED: Run as root (needed for nvidia-smi power settings, i2c access, etc.)
# =============================================================================

set -uo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────

readonly SCRIPT_VERSION="1.0"
readonly LOG_DIR="/var/log/iskander"
readonly I2C_BUS="${HEARTH_I2C_BUS:-1}"
readonly OLLAMA_URL="${HEARTH_OLLAMA_URL:-http://127.0.0.1:11434}"
readonly ACTIVITYPUB_URL="${HEARTH_ACTIVITYPUB_URL:-http://127.0.0.1:8080}"
readonly LANGGRAPH_URL="${HEARTH_LANGGRAPH_URL:-http://127.0.0.1:8123}"

SKIP_GPU=0
SKIP_ACOUSTIC=0
for arg in "$@"; do
    [[ "${arg}" == "--skip-gpu" ]]      && SKIP_GPU=1
    [[ "${arg}" == "--skip-acoustic" ]] && SKIP_ACOUSTIC=1
done

# ── Counters ──────────────────────────────────────────────────────────────────

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0
declare -a FAILURES=()

# ── Logging & reporting ───────────────────────────────────────────────────────

mkdir -p "${LOG_DIR}"
NODE_DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/qa_results_${NODE_DATE}.log"
exec > >(tee -a "${LOG_FILE}") 2>&1

log_check() {
    local status="$1"  # PASS / FAIL / WARN / SKIP
    local name="$2"
    local detail="${3:-}"
    local color_reset='\033[0m'
    local color
    case "${status}" in
        PASS) color='\033[0;32m' ;;
        FAIL) color='\033[0;31m' ;;
        WARN) color='\033[0;33m' ;;
        SKIP) color='\033[0;36m' ;;
        *)    color='' ;;
    esac
    printf "${color}[%-4s]${color_reset} %-55s %s\n" "${status}" "${name}" "${detail}"
}

pass() { PASS_COUNT=$(( PASS_COUNT + 1 )); log_check "PASS" "$1" "${2:-}"; }
fail() { FAIL_COUNT=$(( FAIL_COUNT + 1 )); FAILURES+=("$1"); log_check "FAIL" "$1" "${2:-}"; }
warn() { WARN_COUNT=$(( WARN_COUNT + 1 )); log_check "WARN" "$1" "${2:-}"; }
skip() { log_check "SKIP" "$1" "${2:-}"; }

# ── Helper: check systemd service ─────────────────────────────────────────────

check_service() {
    local svc="$1"
    if systemctl is-active --quiet "${svc}"; then
        pass "Service: ${svc}" "active (running)"
    else
        fail "Service: ${svc}" "$(systemctl is-active "${svc}" 2>/dev/null || echo 'not-found')"
    fi
}

# ── Helper: HTTP health check ─────────────────────────────────────────────────

check_http() {
    local name="$1"
    local url="$2"
    if curl -sf --max-time 5 "${url}" >/dev/null 2>&1; then
        pass "HTTP: ${name}" "${url}"
    else
        fail "HTTP: ${name}" "no response from ${url}"
    fi
}

# ── Helper: i2c device present ────────────────────────────────────────────────

check_i2c() {
    local name="$1"
    local addr_hex="$2"  # e.g. "0x40"
    local addr_dec
    addr_dec=$(( addr_hex ))
    if i2cdetect -y "${I2C_BUS}" 2>/dev/null | grep -qE "$(printf '%02x' "${addr_dec}")"; then
        pass "I2C device: ${name}" "found at ${addr_hex} on bus ${I2C_BUS}"
    else
        fail "I2C device: ${name}" "not found at ${addr_hex} on bus ${I2C_BUS}"
    fi
}

# =============================================================================
# TEST SECTIONS
# =============================================================================

echo "============================================================"
echo " Iskander Hearth QA Automated Test v${SCRIPT_VERSION}"
echo " Date: $(date)"
echo " Host: $(hostname)"
echo " Log:  ${LOG_FILE}"
echo "============================================================"
echo ""

# ── 1. OS Environment ─────────────────────────────────────────────────────────

echo "── 1. OS Environment ────────────────────────────────────────"

if [[ "$(id -u)" -eq 0 ]]; then
    pass "Running as root"
else
    fail "Running as root" "must run with sudo"
fi

KERNEL=$(uname -r)
pass "Kernel version" "${KERNEL}"

if command -v systemctl >/dev/null; then
    pass "systemd present"
else
    fail "systemd present" "systemctl not found"
fi

# ── 2. Hardware detection ─────────────────────────────────────────────────────

echo ""
echo "── 2. Hardware Detection ────────────────────────────────────"

# CPU
CPU_MODEL=$(grep -m1 "model name" /proc/cpuinfo 2>/dev/null | cut -d: -f2 | xargs || echo "unknown")
pass "CPU detected" "${CPU_MODEL}"

# RAM
RAM_GB=$(awk '/MemTotal/{printf "%.0f", $2/1024/1024}' /proc/meminfo)
if (( RAM_GB >= 16 )); then
    pass "RAM ≥ 16GB" "${RAM_GB}GB detected"
else
    warn "RAM < 16GB" "${RAM_GB}GB (minimum for Llama 3:8b is 16GB)"
fi

# NVMe
if nvme list 2>/dev/null | grep -q "nvme"; then
    NVME=$(nvme list 2>/dev/null | grep nvme | head -1 | awk '{print $1}')
    SMART_STATUS=$(nvme smart-log "${NVME}" 2>/dev/null | grep "critical_warning" | awk '{print $3}' || echo "err")
    if [[ "${SMART_STATUS}" == "0x0" || "${SMART_STATUS}" == "0" ]]; then
        pass "NVMe SMART" "${NVME} — no critical warnings"
    else
        fail "NVMe SMART" "${NVME} — critical_warning: ${SMART_STATUS}"
    fi
else
    warn "NVMe detection" "nvme-cli not installed or no NVMe found"
fi

# GPU
if command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | grep -q .; then
    GPU_MODEL=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 | xargs)
    GPU_DRIVER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -1 | xargs)
    pass "GPU detected" "${GPU_MODEL} (driver ${GPU_DRIVER})"
else
    if [[ "${SKIP_GPU}" -eq 1 ]]; then
        skip "GPU detection" "--skip-gpu flag set"
    else
        fail "GPU detection" "nvidia-smi not found or no NVIDIA GPU"
    fi
fi

# ── 3. Solidarity HAT (I2C) ───────────────────────────────────────────────────

echo ""
echo "── 3. Solidarity HAT ────────────────────────────────────────"

if command -v i2cdetect >/dev/null; then
    check_i2c "INA3221 (power monitor)"  "0x40"
    check_i2c "ATECC608B (secure element)" "0x60"
else
    fail "i2c-tools installed" "i2cdetect not found; run: apt install i2c-tools"
fi

# Check provisioning record
if [[ -f "/etc/iskander/atecc_provisioning.json" ]]; then
    pass "ATECC608B provisioning record" "/etc/iskander/atecc_provisioning.json"
else
    fail "ATECC608B provisioning record" "not found — run atecc_provision.py"
fi

# Kill switch GPIO state (expect LOW/0 when not pressed)
for gpio_num in 4 17 27; do
    GPIO_VAL=$(gpioget gpiochip0 "${gpio_num}" 2>/dev/null || echo "err")
    if [[ "${GPIO_VAL}" == "0" ]]; then
        pass "GPIO${gpio_num} kill switch (at rest = LOW)" "value: ${GPIO_VAL}"
    elif [[ "${GPIO_VAL}" == "err" ]]; then
        warn "GPIO${gpio_num} kill switch" "gpioget failed — check libgpiod"
    else
        warn "GPIO${gpio_num} kill switch" "HIGH at rest — switch may be in KILL position"
    fi
done

# INA3221 voltage reading
INA_OUT=$(python3 /opt/iskander/firmware/solidarity_hat/ina3221_poller.py 2>/dev/null | grep "CH2" || echo "")
if echo "${INA_OUT}" | grep -q "V"; then
    pass "INA3221 voltage read" "$(echo "${INA_OUT}" | head -1 | xargs)"
else
    fail "INA3221 voltage read" "no output from ina3221_poller.py"
fi

# ── 4. Systemd Services ───────────────────────────────────────────────────────

echo ""
echo "── 4. Systemd Services ──────────────────────────────────────"

check_service "hearth-sovereignty.service"
check_service "hearth-permacomputing.service"
check_service "hearth-buttons.service"
check_service "hearth-leds.service"
check_service "gpu-thermal-manager.service"
check_service "cpu_thermal_manager.service"

# Sovereignty lock must NOT be present at QA time
if [[ ! -f "/run/iskander/sovereignty.lock" ]]; then
    pass "Sovereignty lock absent" "no lock file (hardware verified)"
else
    fail "Sovereignty lock absent" "/run/iskander/sovereignty.lock EXISTS — hardware problem"
fi

# ── 5. Network Services ───────────────────────────────────────────────────────

echo ""
echo "── 5. Network Services ──────────────────────────────────────"

check_http "Ollama API"       "${OLLAMA_URL}/api/tags"
check_http "ActivityPub router" "${ACTIVITYPUB_URL}/health"
check_http "LangGraph orchestrator" "${LANGGRAPH_URL}/health"

# Network interface
if ip link show | grep -q "state UP"; then
    IFACE=$(ip link show | grep "state UP" | head -1 | awk '{print $2}' | tr -d ':')
    pass "Network interface UP" "${IFACE}"
else
    fail "Network interface UP" "no active network interface"
fi

# ── 6. LLM Inference Smoke Test ──────────────────────────────────────────────

echo ""
echo "── 6. LLM Inference Smoke Test ──────────────────────────────"

if command -v ollama >/dev/null; then
    echo "   Running brief Llama 3 inference (30s timeout)..."
    INFER_OUT=$(timeout 120 ollama run llama3:8b "Reply with only the word: OK" 2>&1 || echo "TIMEOUT_OR_ERROR")
    if echo "${INFER_OUT}" | grep -qi "ok\|okay\|sure\|yes"; then
        pass "Ollama Llama 3:8b inference" "completed"
    elif echo "${INFER_OUT}" | grep -q "TIMEOUT_OR_ERROR"; then
        fail "Ollama Llama 3:8b inference" "timed out or errored — check GPU memory"
    else
        warn "Ollama Llama 3:8b inference" "completed but unexpected output: $(echo "${INFER_OUT}" | head -1)"
    fi

    # GPU in use during inference
    if [[ "${SKIP_GPU}" -eq 0 ]]; then
        GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | xargs)
        if (( GPU_MEM > 100 )); then
            pass "GPU memory used during inference" "${GPU_MEM} MiB"
        else
            warn "GPU memory used during inference" "${GPU_MEM} MiB — CPU inference? Check CUDA"
        fi
    fi
else
    fail "Ollama CLI installed" "ollama not in PATH"
fi

# ── 7. GPU Thermal (if not skipped) ──────────────────────────────────────────

if [[ "${SKIP_GPU}" -eq 0 ]]; then
    echo ""
    echo "── 7. GPU Thermal (5-min gpu-burn) ──────────────────────────"

    if command -v gpu_burn >/dev/null 2>&1 || [[ -x "/opt/gpu-burn/gpu_burn" ]]; then
        GPU_BURN_BIN=$(command -v gpu_burn 2>/dev/null || echo "/opt/gpu-burn/gpu_burn")
        echo "   Running gpu-burn for 5 minutes..."
        "${GPU_BURN_BIN}" 300 &
        GPU_BURN_PID=$!

        MAX_TEMP=0
        for i in $(seq 1 60); do
            sleep 5
            TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | xargs)
            [[ "${TEMP}" =~ ^[0-9]+$ ]] && (( TEMP > MAX_TEMP )) && MAX_TEMP="${TEMP}"
        done

        wait "${GPU_BURN_PID}" 2>/dev/null || true

        if (( MAX_TEMP < 83 )); then
            pass "GPU temp under 5-min gpu-burn" "${MAX_TEMP}°C < 83°C"
        else
            fail "GPU temp under 5-min gpu-burn" "${MAX_TEMP}°C ≥ 83°C — check cooling"
        fi
    else
        warn "gpu-burn not installed" "skipping GPU burn test — install from github.com/wilicc/gpu-burn"
    fi
fi

# ── 8. Acoustic Prompt (unless skipped) ──────────────────────────────────────

if [[ "${SKIP_ACOUSTIC}" -eq 0 ]]; then
    echo ""
    echo "── 8. Acoustic Measurement Prompt ───────────────────────────"
    echo "   ACTION REQUIRED: Measure noise at 1m from front panel"
    echo "   during active Ollama inference."
    echo ""
    read -r -p "   Enter measured dBA reading at 1m (or 'skip'): " ACOUSTIC_READING
    if [[ "${ACOUSTIC_READING}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
        if (( $(echo "${ACOUSTIC_READING} < 35" | bc -l) )); then
            pass "Acoustic: < 35 dBA at 1m" "${ACOUSTIC_READING} dBA"
        else
            fail "Acoustic: < 35 dBA at 1m" "${ACOUSTIC_READING} dBA ≥ 35 dBA"
        fi
    else
        skip "Acoustic measurement" "${ACOUSTIC_READING}"
    fi
fi

# ── 9. Physical Inspection Prompts ───────────────────────────────────────────

echo ""
echo "── 9. Physical Inspection ───────────────────────────────────"

if [[ "${SKIP_ACOUSTIC}" -eq 0 ]]; then
    for check in \
        "Chassis closed, no loose cables visible from exterior" \
        "QR repair code stickers affixed to all 3 interior locations" \
        "Solidarity HAT secured with M3 screws" \
        "NeoPixel diffuser installed and flush" \
        "CERN-OHL-S v2 license card included in box" \
        "Material Passport completed and included" \
    ; do
        read -r -p "   PASS? ${check} [y/n]: " RESP
        if [[ "${RESP}" =~ ^[Yy]$ ]]; then
            pass "Physical: ${check}"
        else
            fail "Physical: ${check}"
        fi
    done
else
    skip "Physical inspection prompts" "--skip-acoustic (non-interactive) mode"
fi

# =============================================================================
# SUMMARY
# =============================================================================

echo ""
echo "============================================================"
echo " QA Test Summary"
echo "============================================================"
printf " PASS: %d\n" "${PASS_COUNT}"
printf " FAIL: %d\n" "${FAIL_COUNT}"
printf " WARN: %d\n" "${WARN_COUNT}"
echo ""

if [[ "${FAIL_COUNT}" -gt 0 ]]; then
    echo " FAILED CHECKS:"
    for f in "${FAILURES[@]}"; do
        echo "   - ${f}"
    done
    echo ""
    echo " STATUS: *** FAIL — DO NOT SHIP THIS NODE ***"
    echo " Log: ${LOG_FILE}"
    exit 1
else
    echo " STATUS: PASS — Node is ready to ship."
    echo " Log: ${LOG_FILE}"
    exit 0
fi
