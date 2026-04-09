# Security Policy

## Reporting Vulnerabilities

If you discover a security vulnerability in Iskander, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, email: **security@argocyte.com**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)

We will acknowledge receipt within 48 hours and provide an initial assessment within 7 days.

## Supported Versions

| Version | Supported |
|---------|-----------|
| main branch | Yes |
| feature branches | Best effort |

## Security Model

Iskander is designed for deployment on the open internet. The security architecture includes:

### Network Layer
- **Cloudflare Tunnel** (default): Zero open ports, outbound-only connections
- **Headscale mesh**: Encrypted WireGuard tunnels for inter-cooperative federation
- **K3s network policies**: Internal service isolation

### Application Layer
- **Authentik SSO**: Single identity provider for all services
- **Vaultwarden**: Encrypted credential storage for cooperative secrets
- **TLS everywhere**: All inter-service communication encrypted

### Cryptographic Layer
- **MACI ZK voting**: Individual votes are never disclosed
- **Soulbound Tokens**: Non-transferable membership credentials
- **IPFS content addressing**: Tamper-evident decision records

### Operational Layer
- **Beszel monitoring**: Service health and anomaly detection
- **Backrest/Restic**: Encrypted backups with point-in-time recovery
- **Non-root containers**: Minimal privilege execution

## Threat Model

Iskander assumes:
- The server operator is trusted but should not be able to alter decision records
- Individual member votes must be private even from administrators
- External attackers should not be able to determine cooperative membership or activities
- Inter-cooperative federation traffic must be encrypted end-to-end

See [docs/plan.md](docs/plan.md) for the full security architecture.
