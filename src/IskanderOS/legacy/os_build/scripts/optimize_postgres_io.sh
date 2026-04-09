#!/usr/bin/env bash
# optimize_postgres_io.sh — Phase 16: PostgreSQL I/O Tuning for SSD Longevity
#
# Appends Iskander-tuned postgresql.conf settings that reduce write
# amplification on commodity NVMe/SATA SSDs. Idempotent: will not append
# settings twice (checks for the ISKANDER_TUNED marker).
#
# Context:
#   - The Iskander ledger is append-only for most tables (audit logs,
#     federation inbox, agent actions). A 1-second commit delay is acceptable.
#   - Financial tables (pending_transactions, zk_vote_tallies) must NOT use
#     async commit. They override synchronous_commit per session in application
#     code (future work — stub note below).
#   - IPFS block store, Docker overlay2, and Postgres WAL all write to the
#     same SSD. Without tuning, ~3× write amplification is common.
#
# Target: Ubuntu 22.04 / 24.04 LTS, PostgreSQL 16 (pgvector image).
# Run as root after postgres service is up:
#   sudo bash /opt/iskander/os_build/scripts/optimize_postgres_io.sh
#
# Safe to run on restart: idempotent marker prevents double-application.

set -euo pipefail

MARKER="# ISKANDER_TUNED"
PG_VERSION="${PG_VERSION:-16}"
PG_CONF="/etc/postgresql/${PG_VERSION}/main/postgresql.conf"

# Fallback: Docker-based Postgres writes config to a data volume.
if [[ ! -f "$PG_CONF" ]]; then
    PG_CONF="/var/lib/postgresql/data/postgresql.conf"
fi

if [[ ! -f "$PG_CONF" ]]; then
    echo "ERROR: Could not find postgresql.conf. Set PG_VERSION or run inside the postgres container." >&2
    exit 1
fi

if grep -q "$MARKER" "$PG_CONF"; then
    echo "PostgreSQL is already tuned (marker found). Nothing to do."
    exit 0
fi

echo "Applying Iskander I/O optimisations to: $PG_CONF"

cat >> "$PG_CONF" <<'EOF'

# ════════════════════════════════════════════════════════════════════════
# ISKANDER_TUNED — Phase 16: SSD Longevity & Write Amplification Reduction
# Applied by: os_build/scripts/optimize_postgres_io.sh
# Rationale: Most Iskander tables are append-only audit/event logs where
#   a crash that loses <1 s of writes is acceptable. Financial tables
#   (pending_transactions, zk_vote_tallies) override synchronous_commit
#   to ON at the application session level.
# ════════════════════════════════════════════════════════════════════════

# ── WAL / Commit Delay ───────────────────────────────────────────────────
# Group commits over a 10 ms window to amortise fsync calls.
# Zero cost when the node is lightly loaded (commit fires immediately).
commit_delay         = 10000    # microseconds (10 ms); default: 0
commit_siblings      = 5        # only delay if ≥5 other transactions waiting

# Reduce WAL background writer wakeup frequency.
# Default 200 ms → 500 ms. WAL pages are still flushed on commit.
wal_writer_delay     = 500ms    # default: 200ms

# ── Async commit for non-financial workloads ─────────────────────────────
# Sets the DEFAULT for all sessions. Application code (treasury, governance)
# overrides this to ON for sessions that touch financial tables.
# STUB: per-table override not yet implemented — tracked as Phase 16 tech debt.
synchronous_commit   = off      # default: on

# ── Shared buffers & background writer ───────────────────────────────────
# 256 MB shared_buffers on a 2–4 GB node; increase to 25% of RAM if more.
shared_buffers       = 256MB    # default: 128MB

# Spread background writer writes over time to avoid bursts.
bgwriter_delay       = 500ms    # default: 200ms
bgwriter_lru_maxpages = 50      # default: 100

# ── Checkpoint tuning ────────────────────────────────────────────────────
# Spread checkpoints over 90% of the checkpoint interval to smooth I/O.
checkpoint_completion_target = 0.9   # default: 0.9 (already good)
max_wal_size         = 512MB    # default: 1GB; lower = more frequent checkpoints
                                 # but fewer WAL files on disk simultaneously

# ── Random page cost (SSD hint) ──────────────────────────────────────────
# Tell the query planner that random reads are cheap (SSD ≈ sequential).
random_page_cost     = 1.1      # default: 4.0 (HDD assumption)
effective_io_concurrency = 200  # default: 1; SSD can handle parallel reads

# ─────────────────────────────────────────────────────────────────────────
EOF

echo "Settings appended. Reloading PostgreSQL..."

# Reload config without restarting (no connection disruption).
if command -v pg_ctlcluster &>/dev/null; then
    pg_ctlcluster "${PG_VERSION}" main reload
elif command -v systemctl &>/dev/null && systemctl is-active --quiet "postgresql@${PG_VERSION}-main"; then
    systemctl reload "postgresql@${PG_VERSION}-main"
else
    # Inside Docker: send SIGHUP to the postmaster.
    pkill -HUP postgres 2>/dev/null || echo "WARN: Could not reload postgres — restart the container."
fi

echo "Done. Verify with: psql -U iskander -c \"SHOW synchronous_commit;\""
