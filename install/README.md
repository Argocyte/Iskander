# Iskander Installer

One command to provision a cooperative node:

```bash
curl -sfL https://get.iskander.coop/install | sh -s -- \
  --coop-name "Sunrise Workers" \
  --admin-email "founder@sunrise.coop" \
  --domain "sunrise.coop"
```

Domain is optional. Without it, a Cloudflare tunnel provides external access automatically.

## What happens

1. **Preflight**: checks OS, RAM (≥8 GB), disk (≥30 GB), architecture (amd64/arm64)
2. **Dependencies**: installs K3s, Helm, Ansible (in a venv at `/opt/iskander-venv`)
3. **Secrets**: generates all cooperative secrets with `openssl rand`; writes to `/opt/iskander/generated-values.yaml`
4. **Deploy**: runs `helm install/upgrade` with a 15-minute timeout; waits for all pods
5. **First-boot**: creates the founding admin account in Authentik; sends password setup email

The installer is idempotent — running it again upgrades the existing deployment.

## After installation

1. Check your email for the password setup link
2. Log in at your cooperative's URL
3. Add your Anthropic API key in the admin settings (for the Clerk agent)
4. Store your generated values file in Vaultwarden — it contains all cooperative secrets

## Manual installation

For air-gapped environments or advanced configuration, see [docs/install-manual.md](../docs/install-manual.md).

## Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 8 GB | 16 GB |
| Disk | 30 GB | 64 GB SSD |
| OS | Debian 12 / Ubuntu 22.04 / Fedora 39 / Arch | Debian 12 |
| Architecture | amd64 / arm64 | — |
| Root or passwordless sudo | Required | — |
