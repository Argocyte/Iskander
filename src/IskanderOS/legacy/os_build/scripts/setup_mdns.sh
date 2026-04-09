#!/usr/bin/env bash
# setup_mdns.sh — Broadcast the Iskander node as iskander.local via avahi-daemon
# Run once during late-commands in the Cloud-Init autoinstall.
# Idempotent: safe to re-run.
set -euo pipefail

HOSTNAME="iskander"
SERVICE_FILE="/etc/avahi/services/iskander.service"

echo "[mdns] Installing avahi-daemon..."
apt-get install -y --no-install-recommends avahi-daemon avahi-utils libnss-mdns

# ── Set the system hostname ────────────────────────────────────────────────────
echo "[mdns] Setting hostname to ${HOSTNAME}..."
hostnamectl set-hostname "${HOSTNAME}"
echo "127.0.1.1  ${HOSTNAME}.local ${HOSTNAME}" >> /etc/hosts

# ── Configure avahi to advertise Iskander services ────────────────────────────
echo "[mdns] Writing avahi service definition..."
cat > "${SERVICE_FILE}" <<'EOF'
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">Iskander Sovereign Node (%h)</name>

  <!-- Streamlit UI — First-Boot Dialogue & Dashboard -->
  <service>
    <type>_http._tcp</type>
    <port>8501</port>
    <txt-record>path=/</txt-record>
    <txt-record>description=Iskander Cooperative Dashboard</txt-record>
  </service>

  <!-- FastAPI backend -->
  <service>
    <type>_http._tcp</type>
    <port>8000</port>
    <txt-record>path=/docs</txt-record>
    <txt-record>description=Iskander API</txt-record>
  </service>

  <!-- ActivityPub federation endpoint -->
  <service>
    <type>_activitypub._tcp</type>
    <port>8000</port>
    <txt-record>path=/federation</txt-record>
  </service>
</service-group>
EOF

# ── Enable and start avahi ─────────────────────────────────────────────────────
echo "[mdns] Enabling avahi-daemon..."
systemctl enable avahi-daemon
systemctl restart avahi-daemon

echo "[mdns] Done. Node is reachable at http://iskander.local:8501"
