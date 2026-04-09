# Contributing to Iskander

Iskander is lunarpunk cooperative infrastructure. Contributions are welcome from anyone who shares the vision of putting web3 in the hands of cooperatives.

## How to Contribute

### Reporting Issues

- Use [GitHub Issues](https://github.com/Argocyte/Iskander/issues) for bugs, feature requests, and questions
- Search existing issues before creating a new one
- Use the issue templates where available

### Code Contributions

1. Fork the repository
2. Create a feature branch from `main` (`git checkout -b feature/your-feature`)
3. Make your changes
4. Ensure your code follows existing patterns in the codebase
5. Commit with clear messages explaining *why*, not just *what*
6. Push to your fork and open a Pull Request

### Documentation

Documentation improvements are always welcome. The docs are organised as:

```
docs/
├── overview.md          # Non-technical introduction
├── white-paper.md       # Vision and rationale
├── roadmap.md           # Phased implementation plan
├── plan.md              # Detailed technical plan
├── reference/           # ICA principles, cooperative identity docs
└── archive/             # Historical design specifications
```

### Areas Where Help Is Needed

- **Helm charts** for K3s deployment of each service
- **Ansible playbooks** for the `curl|sh` installer
- **Loomio API integration** for the Clerk agent's loomio-bridge skill
- **Mattermost plugin** for Loomio decision notifications
- **MACI circuit compilation** (Circom/snarkjs) for ZK voting
- **Testing** on ARM64 (Raspberry Pi 4/5) and various Linux distributions
- **Translations** of the overview and white paper

## Development Setup

```bash
# Clone the repository
git clone https://github.com/Argocyte/Iskander.git
cd Iskander

# The project uses K3s for orchestration
# See docs/plan.md for the full service stack
```

## Code of Conduct

This project follows cooperative principles. We expect all contributors to:

- Treat others with respect and dignity
- Welcome diverse perspectives and experiences
- Accept constructive criticism gracefully
- Focus on what is best for the cooperative movement

Behaviour that is harassing, discriminatory, or otherwise harmful will not be tolerated.

## License

By contributing, you agree that your contributions will be licensed under the AGPL-3.0-only license (software) or CERN-OHL-S v2 (hardware).
