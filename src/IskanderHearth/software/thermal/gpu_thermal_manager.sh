#!/usr/bin/env bash
# =============================================================================
# gpu_thermal_manager.sh — GPU Thermal Throttle Manager
# =============================================================================
# License  : CERN-OHL-S v2 / MIT (software)
# Phase    : 7 — Thermal & Acoustic Validation
# Managed by: systemd unit gpu-thermal-manager.service (inline below)
#
# PURPOSE:
#   Keeps RTX 3060 junction temperature below 83°C during sustained Llama 3
#   inference while minimising acoustic output. Polls nvidia-smi every 5 seconds.
#   When the LLM inference queue is empty for > 5 minutes, locks the GPU to
#   its lowest P-state (Pstate 8, 210 MHz core) to eliminate fan noise entirely.
#
# THERMAL POLICY (per hearth_roadmap_v2.md Phase 7):
#   GPU temp > 80°C  → reduce current power limit by 10W
#   GPU temp > 85°C  → clamp power limit to FLOOR (100W minimum)
#   GPU temp < 70°C for ≥ 60s → restore configured maximum power limit
#   LLM queue idle > 5 min → lock to minimum P-state (210,210 MHz)
#
# SAFETY:
#   Power limit is never set below POWER_FLOOR_W (100W). Hard floor prevents
#   the GPU from entering an unstable power state under sustained load.
#   All transitions are logged to the systemd journal via logger(1).
#
# CONFIGURATION (override via environment variables):
#   HEARTH_GPU_MAX_W        Default power limit (W). Auto-detected at startup.
#   HEARTH_GPU_FLOOR_W      Minimum enforced power limit (W). Default: 100.
#   HEARTH_GPU_STEP_W       Power reduction step per throttle event (W). Default: 10.
#   HEARTH_TEMP_THROTTLE    Temperature threshold triggering step reduction. Default: 80.
#   HEARTH_TEMP_CLAMP       Temperature threshold triggering floor clamp. Default: 85.
#   HEARTH_TEMP_COOL        Temperature below which cool-down timer runs. Default: 70.
#   HEARTH_COOL_HOLD_SEC    Seconds below COOL temp before restoring PL. Default: 60.
#   HEARTH_IDLE_HOLD_SEC    Seconds queue idle before P-state lock. Default: 300.
#   HEARTH_POLL_SEC         Poll interval (seconds). Default: 5.
#   HEARTH_OLLAMA_URL       Ollama API base URL. Default: http://127.0.0.1:11434
#
# USAGE:
#   # Run directly (test):
#   bash gpu_thermal_manager.sh
#
#   # Install as systemd service:
#   sudo cp gpu_thermal_manager.sh /opt/iskander/software/thermal/
#   sudo chmod +x /opt/iskander/software/thermal/gpu_thermal_manager.sh
#   sudo cp gpu_thermal_manager.service /etc/systemd/system/
#   sudo systemctl daemon-reload && sudo systemctl enable --now gpu-thermal-manager.service
# =============================================================================

set -euo pipefail

# ── Constants & configuration ─────────────────────────────────────────────────

readonly SCRIPT_NAME="hearth.gpu_thermal"
readonly LOG_TAG="${SCRIPT_NAME}"

POWER_FLOOR_W="${HEARTH_GPU_FLOOR_W:-100}"
POWER_STEP_W="${HEARTH_GPU_STEP_W:-10}"
TEMP_THROTTLE="${HEARTH_TEMP_THROTTLE:-80}"
TEMP_CLAMP="${HEARTH_TEMP_CLAMP:-85}"
TEMP_COOL="${HEARTH_TEMP_COOL:-70}"
COOL_HOLD_SEC="${HEARTH_COOL_HOLD_SEC:-60}"
IDLE_HOLD_SEC="${HEARTH_IDLE_HOLD_SEC:-300}"
POLL_SEC="${HEARTH_POLL_SEC:-5}"
OLLAMA_URL="${HEARTH_OLLAMA_URL:-http://127.0.0.1:11434}"

# ── Logging ───────────────────────────────────────────────────────────────────

log_info()  { logger -t "${LOG_TAG}" -p daemon.info    -- "$*"; }
log_warn()  { logger -t "${LOG_TAG}" -p daemon.warning -- "$*"; }
log_crit()  { logger -t "${LOG_TAG}" -p daemon.crit    -- "$*"; }

# ── Dependency checks ─────────────────────────────────────────────────────────

check_deps() {
    local missing=()
    for cmd in nvidia-smi curl; do
        command -v "${cmd}" >/dev/null 2>&1 || missing+=("${cmd}")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_crit "Missing dependencies: ${missing[*]}. GPU thermal management is inactive."
        exit 1
    fi

    # Verify a GPU is present
    if ! nvidia-smi --query-gpu=name --format=csv,noheader >/dev/null 2>&1; then
        log_crit "No NVIDIA GPU detected by nvidia-smi. Exiting."
        exit 1
    fi
}

# ── nvidia-smi query helpers ──────────────────────────────────────────────────

get_gpu_temp_c() {
    nvidia-smi \
        --query-gpu=temperature.gpu \
        --format=csv,noheader,nounits \
        2>/dev/null | head -1 | tr -d '[:space:]'
}

get_gpu_power_limit_w() {
    # Returns the currently enforced power limit (integer watts)
    nvidia-smi \
        --query-gpu=power.limit \
        --format=csv,noheader,nounits \
        2>/dev/null | head -1 | tr -d '[:space:]' | cut -d. -f1
}

get_gpu_power_limit_max_w() {
    # Returns the card's maximum allowed power limit
    nvidia-smi \
        --query-gpu=power.max_limit \
        --format=csv,noheader,nounits \
        2>/dev/null | head -1 | tr -d '[:space:]' | cut -d. -f1
}

set_gpu_power_limit() {
    local target_w="$1"
    local current_w
    current_w=$(get_gpu_power_limit_w)

    # Clamp to floor
    if (( target_w < POWER_FLOOR_W )); then
        target_w="${POWER_FLOOR_W}"
    fi

    # Only act if actually changing
    if (( target_w != current_w )); then
        if nvidia-smi --power-limit="${target_w}" >/dev/null 2>&1; then
            log_warn "Power limit: ${current_w}W → ${target_w}W"
        else
            log_warn "Failed to set power limit to ${target_w}W (driver rejected value)."
        fi
    fi
}

lock_to_min_pstate() {
    # Lock GPU clock to 210,210 MHz (minimum P-state) to eliminate fan noise
    # at idle. nvidia-smi -lgc sets a locked graphics clock range [min,max].
    if nvidia-smi --lock-gpu-clocks=210,210 >/dev/null 2>&1; then
        log_info "P-state locked to 210 MHz (idle power state)."
    else
        log_warn "Failed to lock GPU clocks to 210 MHz (some driver versions require persistence mode)."
    fi
}

unlock_pstate() {
    # Remove the clock lock and restore normal GPU boost behaviour
    if nvidia-smi --reset-gpu-clocks >/dev/null 2>&1; then
        log_info "GPU clock lock removed — normal boost behaviour restored."
    else
        log_warn "Failed to reset GPU clocks."
    fi
}

# ── Ollama queue check ────────────────────────────────────────────────────────

is_ollama_queue_empty() {
    # Returns 0 (true) if no models are currently loaded / running inference.
    # Ollama /api/ps returns running models; empty "models" array = idle.
    local response
    response=$(curl -sf --max-time 2 "${OLLAMA_URL}/api/ps" 2>/dev/null) || {
        # If Ollama is unreachable, treat as idle (no active inference)
        return 0
    }
    local model_count
    model_count=$(printf '%s' "${response}" | grep -o '"models":\s*\[' | wc -l)
    # Check if the models array is empty: "models":[]
    if printf '%s' "${response}" | grep -q '"models":\s*\[\s*\]'; then
        return 0  # queue empty
    else
        return 1  # inference active
    fi
}

# ── State machine ─────────────────────────────────────────────────────────────
# Tracks: current power limit, cool-down timer, idle timer, P-state lock

declare -i CURRENT_PL_W=0
declare -i MAX_PL_W=0
declare -i COOL_START_TS=0
declare -i IDLE_START_TS=0
declare -i PSTATE_LOCKED=0  # 0=normal, 1=locked to min

# ── Main loop ─────────────────────────────────────────────────────────────────

main() {
    check_deps

    # Read and store the card's maximum power limit at startup (the configured TDP)
    MAX_PL_W=$(get_gpu_power_limit_max_w)
    CURRENT_PL_W=$(get_gpu_power_limit_w)

    # Honour HEARTH_GPU_MAX_W override (e.g., user set a lower TDP via nvidia-smi beforehand)
    if [[ -n "${HEARTH_GPU_MAX_W:-}" ]]; then
        MAX_PL_W="${HEARTH_GPU_MAX_W}"
    fi

    log_info "GPU Thermal Manager started. Max PL: ${MAX_PL_W}W | Floor: ${POWER_FLOOR_W}W | Step: ${POWER_STEP_W}W"
    log_info "Thresholds — Throttle: ${TEMP_THROTTLE}°C | Clamp: ${TEMP_CLAMP}°C | Cool: ${TEMP_COOL}°C (${COOL_HOLD_SEC}s)"
    log_info "Idle P-state lock after: ${IDLE_HOLD_SEC}s | Poll: ${POLL_SEC}s"

    COOL_START_TS=0
    IDLE_START_TS=$(date +%s)

    while true; do
        local temp_c
        temp_c=$(get_gpu_temp_c)
        CURRENT_PL_W=$(get_gpu_power_limit_w)
        local now
        now=$(date +%s)

        # ── Validate temperature reading ─────────────────────────────────────
        if ! [[ "${temp_c}" =~ ^[0-9]+$ ]]; then
            log_warn "Could not read GPU temperature (got '${temp_c}'). Skipping cycle."
            sleep "${POLL_SEC}"
            continue
        fi

        # ── Thermal throttle policy ───────────────────────────────────────────

        if (( temp_c > TEMP_CLAMP )); then
            # Critical: clamp to floor immediately
            if (( CURRENT_PL_W > POWER_FLOOR_W )); then
                log_warn "CRITICAL: GPU ${temp_c}°C > ${TEMP_CLAMP}°C threshold. Clamping to floor ${POWER_FLOOR_W}W."
                set_gpu_power_limit "${POWER_FLOOR_W}"
            fi
            COOL_START_TS=0  # Reset cool-down; we're still hot

        elif (( temp_c > TEMP_THROTTLE )); then
            # Warm: reduce by one step
            local new_pl=$(( CURRENT_PL_W - POWER_STEP_W ))
            log_warn "THROTTLE: GPU ${temp_c}°C > ${TEMP_THROTTLE}°C. Reducing PL: ${CURRENT_PL_W}W → ${new_pl}W"
            set_gpu_power_limit "${new_pl}"
            COOL_START_TS=0  # Not cool yet

        elif (( temp_c < TEMP_COOL )); then
            # Cool: start or continue cool-down hold timer
            if (( COOL_START_TS == 0 )); then
                COOL_START_TS="${now}"
                log_info "Cool-down timer started: GPU ${temp_c}°C < ${TEMP_COOL}°C. Waiting ${COOL_HOLD_SEC}s."
            else
                local cool_elapsed=$(( now - COOL_START_TS ))
                if (( cool_elapsed >= COOL_HOLD_SEC )); then
                    # Restore max PL if we throttled
                    if (( CURRENT_PL_W < MAX_PL_W )); then
                        log_info "Cool-down complete (${cool_elapsed}s). Restoring max PL: ${CURRENT_PL_W}W → ${MAX_PL_W}W"
                        set_gpu_power_limit "${MAX_PL_W}"
                    fi
                    COOL_START_TS=0
                fi
            fi
        else
            # Between TEMP_COOL and TEMP_THROTTLE: steady state, reset cool timer
            COOL_START_TS=0
        fi

        # ── Idle P-state policy ───────────────────────────────────────────────
        if is_ollama_queue_empty; then
            if (( IDLE_START_TS == 0 )); then
                IDLE_START_TS="${now}"
                log_info "Ollama queue empty — idle timer started."
            else
                local idle_elapsed=$(( now - IDLE_START_TS ))
                if (( idle_elapsed >= IDLE_HOLD_SEC && PSTATE_LOCKED == 0 )); then
                    log_info "LLM queue idle ${idle_elapsed}s ≥ ${IDLE_HOLD_SEC}s — locking to min P-state."
                    lock_to_min_pstate
                    PSTATE_LOCKED=1
                fi
            fi
        else
            # Active inference — ensure P-state is unlocked
            if (( PSTATE_LOCKED == 1 )); then
                log_info "Inference resumed — unlocking GPU P-state."
                unlock_pstate
                PSTATE_LOCKED=0
            fi
            IDLE_START_TS=0
        fi

        # ── systemd watchdog keepalive ────────────────────────────────────────
        # Notify watchdog if running under systemd (sd_notify)
        if [[ -n "${NOTIFY_SOCKET:-}" ]]; then
            printf 'WATCHDOG=1\nSTATUS=GPU:%d°C PL:%dW/%dW %s\n' \
                "${temp_c}" "${CURRENT_PL_W}" "${MAX_PL_W}" \
                "$(( PSTATE_LOCKED ? 'IDLE_LOCKED' : 'ACTIVE' ))" \
                > "${NOTIFY_SOCKET}" 2>/dev/null || true
        fi

        sleep "${POLL_SEC}"
    done
}

# ── Cleanup on exit ───────────────────────────────────────────────────────────

cleanup() {
    log_info "GPU Thermal Manager shutting down. Restoring max PL and unlocking clocks."
    set_gpu_power_limit "${MAX_PL_W:-200}" || true
    unlock_pstate || true
}
trap cleanup EXIT SIGTERM SIGINT

main "$@"
