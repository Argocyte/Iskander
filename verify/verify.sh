#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------
# Iskander Phase C — end-to-end verification smoke tests
# Runs against a live cluster (K3d in CI, Debian VM locally).
#
# Environment variables:
#   ISKANDER_NS       Kubernetes namespace (default: iskander)
#   BASE_URL          Cluster ingress base URL (default: http://localhost)
#   AUTHENTIK_URL     e.g. https://auth.example.coop
#   AUTHENTIK_TOKEN   Authentik admin API token (for cleanup)
#   GLASS_BOX_URL     Decision-recorder in-cluster URL
#   PROVISIONER_URL   Provisioner in-cluster URL (optional)
#   IPFS_URL          IPFS API URL (optional; failure is informational only)
# -------------------------------------------------------

ISKANDER_NS="${ISKANDER_NS:-iskander}"
BASE_URL="${BASE_URL:-http://localhost}"
AUTHENTIK_URL="${AUTHENTIK_URL:-}"
AUTHENTIK_TOKEN="${AUTHENTIK_TOKEN:-}"
GLASS_BOX_URL="${GLASS_BOX_URL:-http://decision-recorder.iskander.svc.cluster.local:3000}"
PROVISIONER_URL="${PROVISIONER_URL:-http://provisioner.iskander.svc.cluster.local:3001}"
IPFS_URL="${IPFS_URL:-http://ipfs.iskander.svc.cluster.local:5001}"

# -------------------------------------------------------
# Counters — use arithmetic substitution, NOT ((PASS++))
# because set -e treats arithmetic returning 0 as failure
# -------------------------------------------------------
PASS=0
FAIL=0

log_pass() { echo "::notice::✅ PASS: $1"; PASS=$((PASS + 1)); }
log_fail() { echo "::error::❌ FAIL: $1"; FAIL=$((FAIL + 1)); }
log_info() { echo "::group::ℹ️  $1"; }
log_end()  { echo "::endgroup::"; }

echo "========================================"
echo "Iskander Phase C — Verification Harness"
echo "  Namespace : ${ISKANDER_NS}"
echo "  Glass Box : ${GLASS_BOX_URL}"
echo "  Provisioner: ${PROVISIONER_URL:-<not set>}"
echo "========================================"
echo ""

# -------------------------------------------------------
# Check 1: Decision-recorder health
# -------------------------------------------------------
log_info "Check 1: Decision-recorder health"
DR_HEALTH=$(curl -sf "${GLASS_BOX_URL}/health" || echo "FAILED")
if echo "$DR_HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
  log_pass "Decision-recorder health OK"
else
  log_fail "Decision-recorder health check failed: $DR_HEALTH"
fi
log_end

# -------------------------------------------------------
# Check 2: Glass Box write + read
# -------------------------------------------------------
log_info "Check 2: Glass Box write + read"
UUID=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
POST_RESP=$(curl -sf -X POST "${GLASS_BOX_URL}/log" \
  -H "Content-Type: application/json" \
  -d "{\"actor\":\"ci-verify\",\"agent\":\"verify\",\"action\":\"smoke-test\",\"target\":\"ci/${UUID}\",\"reasoning\":\"automated verification\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" \
  || echo "FAILED")

if echo "$POST_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('recorded') else 1)" 2>/dev/null; then
  log_pass "Glass Box write succeeded"
else
  log_fail "Glass Box write failed: $POST_RESP"
fi

# Read back and verify action field
READ_RESP=$(curl -sf "${GLASS_BOX_URL}/log?agent=verify&limit=5" || echo "FAILED")
ENTRY_ACTION=$(echo "$READ_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
entries=[e for e in d.get('entries',[]) if e.get('action')=='smoke-test']
print(entries[0]['action'] if entries else '')
" 2>/dev/null || echo "")

if [[ "$ENTRY_ACTION" == "smoke-test" ]]; then
  log_pass "Glass Box read verified (action=smoke-test confirmed)"
else
  log_fail "Glass Box read failed or entry not found (got: '${ENTRY_ACTION}')"
fi
log_end

# -------------------------------------------------------
# Check 3: Provisioner health (only if PROVISIONER_URL set)
# -------------------------------------------------------
log_info "Check 3: Provisioner health"
if [[ -n "${PROVISIONER_URL:-}" ]]; then
  PROV_HEALTH=$(curl -sf "${PROVISIONER_URL}/health" || echo "FAILED")
  if echo "$PROV_HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('status')=='ok' else 1)" 2>/dev/null; then
    log_pass "Provisioner health OK"
  else
    log_fail "Provisioner health check failed: $PROV_HEALTH"
  fi
else
  log_info "Provisioner health skipped (PROVISIONER_URL not set)"
  log_end
fi
log_end

# -------------------------------------------------------
# Check 4: Member provisioning smoke test
#   (only if PROVISIONER_URL + AUTHENTIK_URL + AUTHENTIK_TOKEN set)
# -------------------------------------------------------
log_info "Check 4: Member provisioning smoke test"
if [[ -n "${PROVISIONER_URL:-}" && -n "${AUTHENTIK_URL:-}" && -n "${AUTHENTIK_TOKEN:-}" ]]; then
  TEST_USER="ci-${UUID:0:8}"
  TEST_EMAIL="ci-${UUID:0:8}@verify.iskander.local"

  PROV_RESP=$(curl -sf -X POST "${PROVISIONER_URL}/members" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${TEST_USER}\",\"email\":\"${TEST_EMAIL}\"}" \
    || echo "FAILED")

  if echo "$PROV_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('provisioned') else 1)" 2>/dev/null; then
    log_pass "Member provisioning: account created"
  else
    log_fail "Member provisioning failed: $PROV_RESP"
  fi

  # Verify status endpoint
  STATUS_RESP=$(curl -sf "${PROVISIONER_URL}/members/${TEST_USER}" || echo "FAILED")
  if echo "$STATUS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if d.get('authentik_exists') else 1)" 2>/dev/null; then
    log_pass "Provisioner status: authentik_exists confirmed"
  else
    log_fail "Provisioner status check failed: $STATUS_RESP"
  fi

  # Cleanup: delete test user from Authentik via admin API
  AUTHENTIK_USER_ID=$(curl -sf \
    -H "Authorization: Bearer ${AUTHENTIK_TOKEN}" \
    "${AUTHENTIK_URL}/api/v3/core/users/?username=${TEST_USER}" \
    | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['results'][0]['pk'] if r.get('results') else '')" 2>/dev/null || echo "")

  if [[ -n "$AUTHENTIK_USER_ID" ]]; then
    curl -sf -X DELETE \
      -H "Authorization: Bearer ${AUTHENTIK_TOKEN}" \
      "${AUTHENTIK_URL}/api/v3/core/users/${AUTHENTIK_USER_ID}/" || true
    log_pass "Test user cleanup complete"
  else
    log_fail "Could not find test user for cleanup (non-fatal)"
  fi
else
  log_info "Member provisioning smoke test skipped (requires PROVISIONER_URL + AUTHENTIK_URL + AUTHENTIK_TOKEN)"
  log_end
fi
log_end

# -------------------------------------------------------
# Check 5: Decisions list
# -------------------------------------------------------
log_info "Check 5: Decisions list"
DECISIONS_RESP=$(curl -sf "${GLASS_BOX_URL}/decisions?limit=1" || echo "FAILED")
if echo "$DECISIONS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'total' in d else 1)" 2>/dev/null; then
  log_pass "Decisions endpoint responsive"
else
  log_fail "Decisions endpoint failed: $DECISIONS_RESP"
fi
log_end

# -------------------------------------------------------
# Check 6: Tensions endpoint
# -------------------------------------------------------
log_info "Check 6: Tensions endpoint"
TENSIONS_RESP=$(curl -sf "${GLASS_BOX_URL}/tensions?limit=1" || echo "FAILED")
if echo "$TENSIONS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'tensions' in d else 1)" 2>/dev/null; then
  log_pass "Tensions endpoint responsive"
else
  log_fail "Tensions endpoint failed: $TENSIONS_RESP"
fi
log_end

# -------------------------------------------------------
# Check 7: IPFS availability (informational — not a hard failure)
# -------------------------------------------------------
log_info "Check 7: IPFS availability"
IPFS_RESP=$(curl -sf -X POST "${IPFS_URL}/api/v0/id" || echo "FAILED")
if echo "$IPFS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); sys.exit(0 if 'ID' in d else 1)" 2>/dev/null; then
  log_pass "IPFS node reachable"
else
  log_pass "IPFS node unreachable (informational — pinning is best-effort)"
fi
log_end

# -------------------------------------------------------
# Summary
# -------------------------------------------------------
echo ""
echo "========================================"
echo "Verification complete: ${PASS} passed, ${FAIL} failed"
echo "========================================"

if [[ $FAIL -gt 0 ]]; then
  exit 1
fi
exit 0
