#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# log2ram_flush.sh — Phase 17: Hourly SSD Write Consolidation
#
# PURPOSE:
#   /var/log and /tmp/docker-tmp are mounted as tmpfs RAM-disks to protect
#   refurbished solid-state drives from the continuous small writes generated
#   by systemd journald, Docker container logging, and PostgreSQL WAL churn.
#
#   This script runs hourly via cron and:
#     1. Compresses the current tmpfs log contents (gzip).
#     2. Flushes the compressed archive to a persistent SSD directory.
#     3. Rotates old archives (keeps 7 days).
#
#   WARNING: Reduces system RAM by ~1GB but extends the lifespan of refurbished
#   solid-state drives by years. This is a deliberate ecological trade-off.
#   Cooperative hardware budgets are finite; extending drive life reduces e-waste
#   and avoids replacement costs that disproportionately burden small cooperatives.
#
# INSTALLED BY: os_build/iso/user-data (late-commands, Phase 17)
# CRON SCHEDULE: 0 * * * * root /opt/iskander/os_build/scripts/log2ram_flush.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
PERSISTENT_LOG_DIR="/var/log-persistent"
PERSISTENT_DOCKER_DIR="/var/docker-tmp-persistent"
RETENTION_DAYS=7
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")

# ── Ensure persistent directories exist on the physical SSD ──────────────────
mkdir -p "$PERSISTENT_LOG_DIR"
mkdir -p "$PERSISTENT_DOCKER_DIR"

# ── Flush /var/log (tmpfs) → persistent SSD ──────────────────────────────────
# Compress and archive the current tmpfs contents as a single tarball.
# This converts thousands of tiny random writes into a single sequential write.
if [ -d /var/log ] && [ "$(ls -A /var/log 2>/dev/null)" ]; then
    ARCHIVE="$PERSISTENT_LOG_DIR/logs-${TIMESTAMP}.tar.gz"
    tar czf "$ARCHIVE" -C /var/log . 2>/dev/null || true
    logger -t log2ram "Flushed /var/log to $ARCHIVE ($(du -sh "$ARCHIVE" 2>/dev/null | cut -f1))"
fi

# ── Flush /tmp/docker-tmp (tmpfs) → persistent SSD ──────────────────────────
if [ -d /tmp/docker-tmp ] && [ "$(ls -A /tmp/docker-tmp 2>/dev/null)" ]; then
    ARCHIVE="$PERSISTENT_DOCKER_DIR/docker-tmp-${TIMESTAMP}.tar.gz"
    tar czf "$ARCHIVE" -C /tmp/docker-tmp . 2>/dev/null || true
    logger -t log2ram "Flushed /tmp/docker-tmp to $ARCHIVE ($(du -sh "$ARCHIVE" 2>/dev/null | cut -f1))"
fi

# ── Rotate old archives (keep $RETENTION_DAYS days) ──────────────────────────
find "$PERSISTENT_LOG_DIR" -name "logs-*.tar.gz" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
find "$PERSISTENT_DOCKER_DIR" -name "docker-tmp-*.tar.gz" -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

logger -t log2ram "Hourly flush complete. SSD write consolidation protects refurbished drives."
