#!/usr/bin/env bash
# setup_wifi_ap.sh — Fallback Ad-Hoc Wi-Fi Access Point (Dappnode-style)
#
# On first boot, if no active Ethernet connection is detected, this script
# configures NetworkManager to broadcast a Wi-Fi AP named "Iskander_Hearth_Setup".
# Members scan the QR code on the physical monitor to join the AP and reach
# the First-Boot Constitutional Dialogue at http://10.42.0.1:8501.
#
# Once a real network (ethernet or configured Wi-Fi) is available, the AP
# is automatically torn down by the iskander-network-watch.service.
#
# Idempotent: safe to re-run; existing AP connection is removed and recreated.
set -euo pipefail

AP_SSID="Iskander_Hearth_Setup"
AP_PASSWORD="solidarity"          # Changed during First-Boot Dialogue
AP_IP="10.42.0.1"
AP_CON_NAME="iskander-ap"
AP_INTERFACE=""                   # Auto-detected below

# ── Detect Wi-Fi interface ─────────────────────────────────────────────────────
AP_INTERFACE=$(nmcli -t -f DEVICE,TYPE device status \
  | grep ":wifi$" \
  | head -n1 \
  | cut -d: -f1 || true)

if [[ -z "${AP_INTERFACE}" ]]; then
    echo "[wifi-ap] No Wi-Fi interface found — skipping AP setup."
    exit 0
fi

echo "[wifi-ap] Wi-Fi interface: ${AP_INTERFACE}"

# ── Check for active Ethernet ──────────────────────────────────────────────────
ETH_ACTIVE=$(nmcli -t -f TYPE,STATE connection show --active \
  | grep "^ethernet:activated" || true)

if [[ -n "${ETH_ACTIVE}" ]]; then
    echo "[wifi-ap] Ethernet is active — AP not needed. Skipping."
    exit 0
fi

echo "[wifi-ap] No Ethernet detected — starting fallback AP '${AP_SSID}'..."

# ── Install dependencies ───────────────────────────────────────────────────────
apt-get install -y --no-install-recommends network-manager dnsmasq-base

# ── Remove stale AP connection if present ─────────────────────────────────────
nmcli connection delete "${AP_CON_NAME}" 2>/dev/null || true

# ── Create the AP via NetworkManager ──────────────────────────────────────────
nmcli connection add \
    type wifi \
    ifname "${AP_INTERFACE}" \
    con-name "${AP_CON_NAME}" \
    autoconnect yes \
    ssid "${AP_SSID}" \
    -- \
    wifi.mode ap \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "${AP_PASSWORD}" \
    ipv4.method shared \
    ipv4.addresses "${AP_IP}/24"

nmcli connection up "${AP_CON_NAME}"

echo "[wifi-ap] AP '${AP_SSID}' broadcasting on ${AP_INTERFACE} at ${AP_IP}"
echo "[wifi-ap] First-Boot UI: http://${AP_IP}:8501"

# ── Write a watch service that tears down the AP once real network arrives ──────
cat > /etc/systemd/system/iskander-network-watch.service <<EOF
[Unit]
Description=Iskander — Tear down setup AP once real network is available
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/opt/iskander/os_build/scripts/teardown_wifi_ap.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# ── Companion teardown script ──────────────────────────────────────────────────
cat > /opt/iskander/os_build/scripts/teardown_wifi_ap.sh <<'TEARDOWN'
#!/usr/bin/env bash
# Tears down the setup AP once Ethernet or a saved Wi-Fi profile is connected.
set -euo pipefail
AP_CON_NAME="iskander-ap"
ETH_ACTIVE=$(nmcli -t -f TYPE,STATE connection show --active | grep "^ethernet:activated" || true)
if [[ -n "${ETH_ACTIVE}" ]]; then
    echo "[wifi-ap] Ethernet online — removing setup AP."
    nmcli connection down  "${AP_CON_NAME}" 2>/dev/null || true
    nmcli connection delete "${AP_CON_NAME}" 2>/dev/null || true
fi
TEARDOWN

chmod +x /opt/iskander/os_build/scripts/teardown_wifi_ap.sh
systemctl enable iskander-network-watch.service

echo "[wifi-ap] Network watch service enabled."
