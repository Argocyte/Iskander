#!/usr/bin/env bash
# Iskander cooperative node installer
# Usage: curl -sfL https://get.iskander.coop/install | sh -s -- [options]
#
# Options:
#   --coop-name NAME      Cooperative name (prompted if omitted)
#   --admin-email EMAIL   Founding admin email (prompted if omitted)
#   --domain DOMAIN       Public domain e.g. sunrise.coop (leave blank for Cloudflare tunnel)
#   --offline             Use locally-cached images; do not pull from registries
#   --skip-preflight      Skip hardware checks (not recommended)
#   --help                Show this help

set -euo pipefail

ISKANDER_VERSION="${ISKANDER_VERSION:-latest}"
REPO_URL="https://github.com/Argocyte/Iskander"
CHART_RELEASE_URL="https://github.com/Argocyte/Iskander/releases/latest/download"

RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}→${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}!${NC} $*"; }
die()     { echo -e "${RED}✗ ERROR:${NC} $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

COOP_NAME=""
ADMIN_EMAIL=""
DOMAIN=""
OFFLINE=false
SKIP_PREFLIGHT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --coop-name)    COOP_NAME="$2"; shift 2 ;;
        --admin-email)  ADMIN_EMAIL="$2"; shift 2 ;;
        --domain)       DOMAIN="$2"; shift 2 ;;
        --offline)      OFFLINE=true; shift ;;
        --skip-preflight) SKIP_PREFLIGHT=true; shift ;;
        --help)
            sed -n '2,12p' "$0" | sed 's/^# //'
            exit 0
            ;;
        *) die "Unknown option: $1" ;;
    esac
done

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

cat <<'BANNER'

  ██╗███████╗██╗  ██╗ █████╗ ███╗   ██╗██████╗ ███████╗██████╗
  ██║██╔════╝██║ ██╔╝██╔══██╗████╗  ██║██╔══██╗██╔════╝██╔══██╗
  ██║███████╗█████╔╝ ███████║██╔██╗ ██║██║  ██║█████╗  ██████╔╝
  ██║╚════██║██╔═██╗ ██╔══██║██║╚██╗██║██║  ██║██╔══╝  ██╔══██╗
  ██║███████║██║  ██╗██║  ██║██║ ╚████║██████╔╝███████╗██║  ██║
  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ╚══════╝╚═╝  ╚═╝

  Cooperative infrastructure — democratic governance, built-in.
  https://github.com/Argocyte/Iskander

BANNER

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------

preflight() {
    info "Running preflight checks..."

    # OS detection
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="${ID:-unknown}"
        OS_VERSION="${VERSION_ID:-unknown}"
    else
        die "Cannot detect OS. Supported: Debian 12+, Ubuntu 22.04+, Fedora 39+, Arch Linux"
    fi

    case "$OS_ID" in
        debian)
            [[ "${OS_VERSION}" -ge 12 ]] 2>/dev/null || \
                warn "Debian < 12 not tested. Proceeding, but you may encounter issues."
            ;;
        ubuntu)
            [[ "${OS_VERSION}" == 22.04 || "${OS_VERSION}" > "22" ]] || \
                warn "Ubuntu < 22.04 not tested."
            ;;
        fedora)
            [[ "${OS_VERSION}" -ge 39 ]] 2>/dev/null || \
                warn "Fedora < 39 not tested."
            ;;
        arch) : ;;  # Rolling release, always latest
        *)
            warn "OS '${OS_ID}' is not officially supported. Proceeding anyway."
            ;;
    esac
    success "OS: ${PRETTY_NAME:-$OS_ID $OS_VERSION}"

    # Architecture
    ARCH="$(uname -m)"
    case "$ARCH" in
        x86_64)  ARCH_K3S="amd64" ;;
        aarch64) ARCH_K3S="arm64" ;;
        *) die "Unsupported architecture: $ARCH. Supported: x86_64, aarch64" ;;
    esac
    success "Architecture: $ARCH"

    # RAM
    TOTAL_RAM_KB="$(grep MemTotal /proc/meminfo | awk '{print $2}')"
    TOTAL_RAM_GB=$(( TOTAL_RAM_KB / 1024 / 1024 ))
    if [[ $TOTAL_RAM_GB -lt 8 ]]; then
        die "Insufficient RAM: ${TOTAL_RAM_GB} GB detected, 8 GB minimum required."
    elif [[ $TOTAL_RAM_GB -lt 16 ]]; then
        warn "RAM: ${TOTAL_RAM_GB} GB — meets minimum but 16 GB is recommended for comfortable operation."
    else
        success "RAM: ${TOTAL_RAM_GB} GB"
    fi

    # Disk (check / and any mounted data paths)
    DISK_AVAIL_GB=$(df -BG / | awk 'NR==2 {gsub("G",""); print $4}')
    if [[ $DISK_AVAIL_GB -lt 30 ]]; then
        die "Insufficient disk space: ${DISK_AVAIL_GB} GB available, 30 GB minimum required."
    fi
    success "Disk: ${DISK_AVAIL_GB} GB available"

    # Root or sudo
    if [[ $EUID -ne 0 ]]; then
        if ! sudo -n true 2>/dev/null; then
            die "This installer requires root or passwordless sudo. Run as root or configure sudo."
        fi
        SUDO="sudo"
    else
        SUDO=""
    fi
}

if [[ $SKIP_PREFLIGHT != true ]]; then
    preflight
fi

# ---------------------------------------------------------------------------
# Interactive prompts (only when not passed as flags)
# ---------------------------------------------------------------------------

prompt() {
    local var_name="$1" prompt_text="$2" default="$3"
    if [[ -n "${!var_name}" ]]; then return; fi
    if [[ -n "$default" ]]; then
        read -rp "  ${prompt_text} [${default}]: " value
        eval "$var_name=\"${value:-$default}\""
    else
        while true; do
            read -rp "  ${prompt_text}: " value
            [[ -n "$value" ]] && break
            warn "This field is required."
        done
        eval "$var_name=\"$value\""
    fi
}

echo ""
echo "Let's set up your cooperative."
echo ""
prompt COOP_NAME  "Cooperative name" ""
prompt ADMIN_EMAIL "Founding admin email" ""
prompt DOMAIN "Public domain (leave blank to use Cloudflare tunnel)" ""

if [[ -z "$DOMAIN" ]]; then
    warn "No domain provided. Cloudflare tunnel will be used for external access."
    warn "You can add a custom domain later by editing values.yaml and re-running install."
fi

echo ""
info "Installing: ${COOP_NAME}"
info "Admin: ${ADMIN_EMAIL}"
info "Domain: ${DOMAIN:-'(Cloudflare tunnel)'}"
echo ""

# ---------------------------------------------------------------------------
# Install system dependencies
# ---------------------------------------------------------------------------

install_deps() {
    info "Installing system dependencies..."
    case "$OS_ID" in
        debian|ubuntu)
            $SUDO apt-get update -qq
            $SUDO apt-get install -y -q curl git python3 python3-pip python3-venv openssl jq
            ;;
        fedora)
            $SUDO dnf install -y -q curl git python3 python3-pip openssl jq
            ;;
        arch)
            $SUDO pacman -Sy --noconfirm curl git python python-pip openssl jq
            ;;
    esac
    success "System dependencies installed"
}

# ---------------------------------------------------------------------------
# Install K3s
# ---------------------------------------------------------------------------

install_k3s() {
    if command -v k3s &>/dev/null; then
        success "K3s already installed: $(k3s --version | head -1)"
        return
    fi

    info "Installing K3s..."
    if [[ $OFFLINE == true ]]; then
        die "--offline mode: K3s must be pre-installed. See docs/install-offline.md"
    fi

    curl -sfL https://get.k3s.io | $SUDO sh -s - \
        --write-kubeconfig-mode 644 \
        --disable traefik \
        --disable local-storage 2>&1 | tail -5

    # Wait for K3s to be ready
    info "Waiting for K3s to be ready..."
    local retries=30
    until $SUDO k3s kubectl get nodes &>/dev/null; do
        retries=$((retries - 1))
        [[ $retries -eq 0 ]] && die "K3s did not become ready after 5 minutes"
        sleep 10
    done

    # Install Traefik (we need it for ingress; K3s built-in version is pinned)
    info "Installing Traefik ingress controller..."
    $SUDO k3s kubectl apply -f https://raw.githubusercontent.com/traefik/traefik/v3.0/docs/content/reference/dynamic-configuration/kubernetes-crd-rbac.yml 2>/dev/null || true

    success "K3s ready"
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
}

# ---------------------------------------------------------------------------
# Install Helm
# ---------------------------------------------------------------------------

install_helm() {
    if command -v helm &>/dev/null; then
        success "Helm already installed: $(helm version --short)"
        return
    fi

    info "Installing Helm..."
    curl -sfL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | $SUDO bash -s -- --no-sudo 2>&1 | tail -3
    success "Helm installed"
}

# ---------------------------------------------------------------------------
# Install Ansible
# ---------------------------------------------------------------------------

install_ansible() {
    if command -v ansible-playbook &>/dev/null; then
        success "Ansible already installed: $(ansible --version | head -1)"
        return
    fi

    info "Installing Ansible..."
    python3 -m venv /opt/iskander-venv
    /opt/iskander-venv/bin/pip install -q ansible kubernetes
    ln -sf /opt/iskander-venv/bin/ansible-playbook /usr/local/bin/ansible-playbook
    ln -sf /opt/iskander-venv/bin/ansible /usr/local/bin/ansible
    success "Ansible installed"
}

# ---------------------------------------------------------------------------
# Download Iskander playbook
# ---------------------------------------------------------------------------

INSTALL_DIR="/opt/iskander"

download_playbook() {
    info "Downloading Iskander installer..."
    if [[ $OFFLINE == true ]]; then
        [[ -d "$INSTALL_DIR" ]] || die "--offline mode: $INSTALL_DIR must exist. See docs/install-offline.md"
        success "Using existing offline installer at $INSTALL_DIR"
        return
    fi

    $SUDO mkdir -p "$INSTALL_DIR"
    # In production this would download from a release; for now clone the install/ directory
    if command -v git &>/dev/null && [[ ! -d "$INSTALL_DIR/.git" ]]; then
        $SUDO git clone --depth 1 "$REPO_URL" "$INSTALL_DIR/src" 2>&1 | tail -3
        $SUDO cp -r "$INSTALL_DIR/src/install/." "$INSTALL_DIR/"
    fi
    success "Iskander installer ready at $INSTALL_DIR"
}

# ---------------------------------------------------------------------------
# Run Ansible playbook
# ---------------------------------------------------------------------------

run_playbook() {
    info "Running Ansible playbook (this will take 5-10 minutes)..."
    export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

    ansible-playbook "$INSTALL_DIR/playbook.yml" \
        --extra-vars "coop_name='${COOP_NAME}'" \
        --extra-vars "admin_email='${ADMIN_EMAIL}'" \
        --extra-vars "domain='${DOMAIN}'" \
        --extra-vars "offline_mode=${OFFLINE}" \
        --extra-vars "kubeconfig=${KUBECONFIG}" \
        -v 2>&1 | tee /var/log/iskander-install.log | \
        grep -E "^(PLAY|TASK|ok:|changed:|failed:|fatal:)" || true

    if grep -q "^fatal:" /var/log/iskander-install.log; then
        die "Installation failed. See /var/log/iskander-install.log for details."
    fi
}

# ---------------------------------------------------------------------------
# Post-install
# ---------------------------------------------------------------------------

print_success() {
    local url
    if [[ -n "$DOMAIN" ]]; then
        url="https://${DOMAIN}"
    else
        # Get the Cloudflare tunnel URL from the cloudflared service
        url=$(kubectl -n iskander get svc cloudflared -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null || echo "your-server-ip")
        url="https://${url}"
    fi

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ${COOP_NAME} is ready!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Access your cooperative at: ${CYAN}${url}${NC}"
    echo ""
    echo -e "  Your admin account:  ${CYAN}${ADMIN_EMAIL}${NC}"
    echo -e "  Check your email for the password setup link."
    echo ""
    echo -e "  Services available:"
    echo -e "    ${CYAN}${url}/chat${NC}        — Mattermost (team chat)"
    echo -e "    ${CYAN}${url}/governance${NC}   — Loomio (proposals and votes)"
    echo -e "    ${CYAN}${url}/files${NC}        — Nextcloud (documents and calendar)"
    echo -e "    ${CYAN}${url}/vault${NC}        — Vaultwarden (shared credentials)"
    echo ""
    echo -e "  Your AI Clerk is ready in Mattermost — type @clerk to get started."
    echo ""
    echo -e "  Install log: /var/log/iskander-install.log"
    echo ""
    echo -e "${CYAN}  Welcome to your cooperative.${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

install_deps
install_k3s
install_helm
install_ansible
download_playbook
run_playbook
print_success
