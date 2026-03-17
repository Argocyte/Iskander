#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# build_iso.sh — Project Iskander Custom Ubuntu ISO Builder
#
# Injects the Cloud-Init autoinstall user-data into a standard Ubuntu 24.04
# Server ISO, producing a plug-and-play iskander-os.iso.
#
# Requirements (Ubuntu/Debian host):
#   sudo apt-get install -y xorriso isolinux
#
# Usage:
#   ./build_iso.sh [/path/to/ubuntu-24.04-live-server-amd64.iso]
#
# Output:
#   ./iskander-os.iso  — flash to USB with BalenaEtcher or Rufus
#
# Architecture:
#   Ubuntu 24.04 uses Subiquity autoinstall. The installer looks for
#   autoinstall config in a CIDATA volume (ISO 9660, label "CIDATA")
#   containing user-data and meta-data files.
#   We splice a second El Torito boot entry for CIDATA alongside the
#   existing Ubuntu boot entry using xorriso.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UBUNTU_ISO="${1:-ubuntu-24.04-live-server-amd64.iso}"
OUTPUT_ISO="${SCRIPT_DIR}/iskander-os.iso"
CIDATA_DIR="${SCRIPT_DIR}/cidata_tmp"
CIDATA_ISO="${SCRIPT_DIR}/cidata.iso"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

info()  { echo -e "${GREEN}[build]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ── Preflight checks ──────────────────────────────────────────────────────────
command -v xorriso  &>/dev/null || error "xorriso not found. Run: sudo apt-get install xorriso"
command -v mkisofs  &>/dev/null || \
  command -v genisoimage &>/dev/null || \
  error "mkisofs/genisoimage not found. Run: sudo apt-get install genisoimage"

MKISOFS=$(command -v mkisofs 2>/dev/null || command -v genisoimage)

[[ -f "${UBUNTU_ISO}" ]] || error "Ubuntu ISO not found: ${UBUNTU_ISO}
  Download from: https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso"

[[ -f "${SCRIPT_DIR}/user-data" ]] || error "user-data not found at ${SCRIPT_DIR}/user-data"
[[ -f "${SCRIPT_DIR}/meta-data" ]] || error "meta-data not found at ${SCRIPT_DIR}/meta-data"

info "Ubuntu ISO  : ${UBUNTU_ISO}"
info "Output ISO  : ${OUTPUT_ISO}"

# ── Step 1: Build a CIDATA ISO (Cloud-Init datasource) ───────────────────────
info "Building CIDATA volume..."
rm -rf "${CIDATA_DIR}"
mkdir -p "${CIDATA_DIR}"
cp "${SCRIPT_DIR}/user-data" "${CIDATA_DIR}/user-data"
cp "${SCRIPT_DIR}/meta-data" "${CIDATA_DIR}/meta-data"

"${MKISOFS}" \
    -output "${CIDATA_ISO}" \
    -volid  "CIDATA" \
    -joliet \
    -rock   \
    "${CIDATA_DIR}"

info "CIDATA ISO  : ${CIDATA_ISO}"

# ── Step 2: Extract MBR and EFI boot artefacts from the Ubuntu ISO ────────────
info "Extracting boot artefacts from Ubuntu ISO..."
MBR_IMG="${SCRIPT_DIR}/ubuntu_mbr.img"
EFI_IMG="${SCRIPT_DIR}/ubuntu_efi.img"

# Extract the protective MBR (first 512 bytes)
dd if="${UBUNTU_ISO}" bs=1 count=432 of="${MBR_IMG}" 2>/dev/null

# Extract the EFI system partition image
# Ubuntu 24.04 stores EFI partition at a known offset — use xorriso to find it
EFI_OFFSET=$(xorriso -indev "${UBUNTU_ISO}" -report_el_torito cmd 2>/dev/null \
    | grep -i "efi" \
    | grep -oP "(?<=disk_path=)[^ ]+" \
    | head -1 || echo "")

if [[ -n "${EFI_OFFSET}" ]]; then
    xorriso -osirrox on -indev "${UBUNTU_ISO}" \
        -extract "${EFI_OFFSET}" "${EFI_IMG}" -- 2>/dev/null || true
fi

# ── Step 3: Inject CIDATA into the Ubuntu ISO ─────────────────────────────────
info "Injecting autoinstall config into Ubuntu ISO..."
info "This may take a few minutes..."

# xorriso command:
#   - Start from the Ubuntu source ISO
#   - Add the CIDATA directory as a new path on the ISO
#   - Preserve all original boot catalogue entries
#   - Append CIDATA ISO as an additional El Torito image (no-emul boot)
xorriso \
    -indev  "${UBUNTU_ISO}" \
    -outdev "${OUTPUT_ISO}" \
    -map    "${CIDATA_DIR}/user-data" /user-data \
    -map    "${CIDATA_DIR}/meta-data" /meta-data \
    -map    "${CIDATA_ISO}"           /cidata.iso \
    -boot_image any replay \
    -append_partition 2 0xef "${CIDATA_ISO}" \
    -changes_pending no \
    2>&1 | grep -v "^xorriso" || true   # suppress xorriso version banner

# ── Step 4: Restore hybrid MBR for USB booting ────────────────────────────────
if [[ -f "${MBR_IMG}" ]]; then
    info "Restoring hybrid MBR for USB boot compatibility..."
    dd if="${MBR_IMG}" of="${OUTPUT_ISO}" bs=1 count=432 conv=notrunc 2>/dev/null
fi

# ── Step 5: Verify output ─────────────────────────────────────────────────────
if [[ -f "${OUTPUT_ISO}" ]]; then
    SIZE=$(du -sh "${OUTPUT_ISO}" | cut -f1)
    info "Build complete!"
    echo
    echo -e "  ${GREEN}Output:${NC} ${OUTPUT_ISO} (${SIZE})"
    echo
    echo "  Flash to USB with:"
    echo "    BalenaEtcher  — https://etcher.balena.io (GUI, all platforms)"
    echo "    Rufus         — https://rufus.ie (Windows)"
    echo "    Linux dd      — sudo dd if=${OUTPUT_ISO} of=/dev/sdX bs=4M status=progress"
    echo
    warn "Default credentials: user=coop / password=solidarity"
    warn "CHANGE THE PASSWORD after first boot via the Constitutional Dialogue."
else
    error "Output ISO not created — check xorriso output above."
fi

# ── Cleanup ───────────────────────────────────────────────────────────────────
rm -rf "${CIDATA_DIR}" "${CIDATA_ISO}" "${MBR_IMG}" "${EFI_IMG}" 2>/dev/null || true
info "Temporary files cleaned up."
