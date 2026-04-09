PROJECT ISKANDER — ISO BUILD INSTRUCTIONS
=========================================

Prerequisites (Ubuntu/Debian build host):
  sudo apt-get install -y xorriso genisoimage

Step 1 — Download Ubuntu 24.04 Server ISO:
  wget https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso

Step 2 — Build the Iskander ISO:
  chmod +x build_iso.sh
  ./build_iso.sh ubuntu-24.04-live-server-amd64.iso

Step 3 — Flash to USB (choose one):
  BalenaEtcher : https://etcher.balena.io
  Rufus        : https://rufus.ie  (Windows)
  dd           : sudo dd if=iskander-os.iso of=/dev/sdX bs=4M status=progress

Step 4 — Boot the target server from USB.
  Installation is fully automatic (~15-20 min).
  The machine will reboot and be reachable at:

    http://iskander.local:8501   (on the same LAN)

  If no Ethernet is present, the node broadcasts Wi-Fi:
    SSID     : Iskander_Hearth_Setup
    Password : solidarity

Default credentials:
  Username : coop
  Password : solidarity   ← CHANGE via First-Boot Constitutional Dialogue

Files in this directory:
  user-data   — Cloud-Init Subiquity autoinstall config
  meta-data   — Cloud-Init instance identity
  build_iso.sh — xorriso injection script
