# Verification Harness

`verify/verify.sh` runs 7 smoke checks against a live Iskander cluster. It covers the Glass Box audit trail, member provisioning, the S3 governance endpoints, and IPFS. The script is designed to run both in CI (GitHub Actions with K3d) and manually against a Debian VM.

---

## Running locally against a VM

Set environment variables pointing at the cluster, then run the script.

```bash
export GLASS_BOX_URL="http://<decision-recorder-ip>:3000"
export PROVISIONER_URL="http://<provisioner-ip>:3001"
export AUTHENTIK_URL="https://auth.yourdomain.coop"
export AUTHENTIK_TOKEN="<admin-api-token>"
export IPFS_URL="http://<ipfs-ip>:5001"

bash verify/verify.sh
```

Each check prints either `✅ PASS: ...` or `❌ FAIL: ...`. The script exits with code 1 if any check fails, so it is safe to use in scripts or pipelines.

`AUTHENTIK_URL` and `AUTHENTIK_TOKEN` are required only for the member provisioning smoke test (Check 4). If either is unset, that check is skipped automatically. All other checks still run.

---

## Running in CI (GitHub Actions)

The workflow at `.github/workflows/verify.yml` triggers on pushes to `main` and on manual dispatch (`workflow_dispatch`). Feature branch PRs only run the `unit-tests` job — smoke tests are reserved for `main` to avoid burning CI minutes on every PR.

### Required GitHub Secrets

Configure these secrets in the repository settings before the smoke-tests job can succeed:

| Secret | Purpose |
|--------|---------|
| `CI_PG_SUPERUSER_PASSWORD` | PostgreSQL superuser password |
| `CI_PG_PASSWORD` | Shared PostgreSQL user password |
| `CI_DR_PG_PASSWORD` | Decision-recorder DB role password |
| `CI_PROV_PG_PASSWORD` | Provisioner DB role password |
| `CI_ANTHROPIC_API_KEY` | OpenClaw LLM access |
| `CI_AUTHENTIK_TOKEN` | Authentik admin API (provisioner smoke test) |

`AUTHENTIK_URL` is intentionally left empty in CI. No real Authentik instance runs inside K3d, so the member provisioning smoke test is automatically skipped. The provisioner health check (Check 3) still runs.

---

## What each check verifies

**Check 1 — Decision-recorder health**
Sends `GET /health` to the decision-recorder service and asserts the response is `{"status":"ok"}`.

**Check 2 — Glass Box write**
Posts a log entry to `POST /log` and asserts the response contains `{"recorded": true}`.

**Check 3 — Glass Box read**
Reads back recent entries from `GET /log` and asserts the `action` field matches `smoke-test`. This guards against silent schema drift where writes succeed but reads return malformed data.

**Check 4 — Provisioner health**
Sends `GET /health` to the provisioner service and asserts `{"status":"ok"}`. Skipped if `PROVISIONER_URL` is unset.

**Check 5 — Member provisioning**
Creates a test account with a UUID-derived username via `POST /members`, verifies `authentik_exists=true` on the status endpoint, then deletes the test user via the Authentik admin API. Skipped if `PROVISIONER_URL`, `AUTHENTIK_URL`, or `AUTHENTIK_TOKEN` are unset.

**Check 6 — Decisions endpoint**
Sends `GET /decisions` and asserts the response contains a `total` field.

**Check 7 — Tensions endpoint**
Sends `GET /tensions` and asserts the response contains a `tensions` list.

**Check 8 — IPFS availability**
Posts to `POST /api/v0/id` on the IPFS Kubo API. This is a soft check: whether the node is reachable or not, the check counts as a pass. Pinning is best-effort and IPFS availability is not a hard dependency for cluster operation.

---

## Interpreting results

The script prints a summary line at the end:

```
Verification complete: N passed, M failed
```

Any non-zero value for M causes the script to exit with code 1.

The CI workflow always uploads `verify-output.log` as a build artifact, even on failure. This log is available in the GitHub Actions run for audit purposes.

---

## Adding new checks

New checks follow the `log_pass` / `log_fail` pattern used throughout the script. Call `log_pass "description"` on success and `log_fail "description"` on failure. Increment the counters using arithmetic substitution:

```bash
PASS=$((PASS + 1))
FAIL=$((FAIL + 1))
```

Do not use `((PASS++))`. The script runs with `set -e`, which treats an arithmetic expression that evaluates to 0 as a failure exit. When `PASS` is 0, `((PASS++))` evaluates to 0 and silently aborts the script before the summary prints.

---

## Phase C completion criteria

- [ ] All 7 checks pass against the Debian VM deployment
- [ ] `unit-tests` CI job passes on every PR
- [ ] `smoke-tests` CI job passes on `main` after PR #59 (provisioner) and PR #60 (meeting prep) are merged
