#!/usr/bin/env python3
"""
welcome_screen.py — Iskander Physical Monitor Welcome Screen

Displays on the server's physical console (tty1) at boot:
  - Project Iskander ASCII banner
  - QR code pointing to http://iskander.local:8501
  - QR code for the fallback Wi-Fi AP (Iskander_Hearth_Setup) if active
  - Node IP addresses
  - Service status summary

Install as /etc/issue or run via getty@tty1.service override.
Requires: python3-qrcode (apt) or `pip install qrcode[terminal]`
"""

import socket
import subprocess
import sys


def _run(cmd: list[str], fallback: str = "") -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return fallback


def _get_ips() -> list[tuple[str, str]]:
    """Return [(interface, ip)] for all non-loopback IPv4 addresses."""
    results = []
    try:
        lines = _run(["ip", "-4", "-o", "addr", "show"]).splitlines()
        for line in lines:
            parts = line.split()
            if len(parts) >= 4:
                iface = parts[1]
                ip    = parts[3].split("/")[0]
                if not ip.startswith("127."):
                    results.append((iface, ip))
    except Exception:
        pass
    return results


def _ap_active() -> tuple[bool, str]:
    """Returns (is_active, ap_ip) for the Iskander_Hearth_Setup AP."""
    con = _run(["nmcli", "-t", "-f", "NAME,STATE", "connection", "show", "--active"])
    if "iskander-ap" in con:
        return True, "10.42.0.1"
    return False, ""


def _print_qr(url: str, label: str) -> None:
    """Print a QR code to the terminal using the qrcode library."""
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=1,
            border=1,
        )
        qr.add_data(url)
        qr.make(fit=True)
        print(f"\n  ┌─ {label} ─{'─' * max(0, 50 - len(label))}┐")
        # Print QR using terminal blocks
        qr.print_ascii(invert=True)
        print(f"  └─ {url} {'─' * max(0, 50 - len(url))}┘\n")
    except ImportError:
        # Fallback: print URL only — qrcode not installed
        print(f"\n  [{label}]")
        print(f"  URL: {url}\n")


def _service_status(name: str) -> str:
    state = _run(["systemctl", "is-active", name], fallback="unknown")
    return "✓" if state == "active" else "✗"


BANNER = r"""
  ██╗███████╗██╗  ██╗ █████╗ ███╗  ██╗██████╗ ███████╗██████╗
  ██║██╔════╝██║ ██╔╝██╔══██╗████╗ ██║██╔══██╗██╔════╝██╔══██╗
  ██║███████╗█████╔╝ ███████║██╔██╗██║██║  ██║█████╗  ██████╔╝
  ██║╚════██║██╔═██╗ ██╔══██║██║╚████║██║  ██║██╔══╝  ██╔══██╗
  ██║███████║██║  ██╗██║  ██║██║ ╚███║██████╔╝███████╗██║  ██║
  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚══╝╚═════╝ ╚══════╝╚═╝  ╚═╝
       Sovereign Cooperative Node  |  Solidarity Stack v0.1
"""


def main() -> None:
    print("\033[2J\033[H", end="")  # Clear screen
    print(BANNER)

    # ── Node addresses ─────────────────────────────────────────────────────────
    hostname = socket.gethostname()
    ips      = _get_ips()

    print(f"  Hostname : {hostname}.local")
    for iface, ip in ips:
        print(f"  {iface:<10}: {ip}")
    print()

    # ── Service status ─────────────────────────────────────────────────────────
    services = [
        ("docker",       "Docker"),
        ("iskander",     "Iskander Stack"),
        ("avahi-daemon", "mDNS (avahi)"),
    ]
    print("  Services:")
    for svc, label in services:
        print(f"    {_service_status(svc)} {label}")
    print()

    # ── Primary QR — Streamlit UI ──────────────────────────────────────────────
    primary_url = "http://iskander.local:8501"
    _print_qr(primary_url, "Open Cooperative Dashboard")

    # ── Fallback Wi-Fi AP QR ───────────────────────────────────────────────────
    ap_active, ap_ip = _ap_active()
    if ap_active:
        # Wi-Fi QR format: WIFI:T:WPA;S:<ssid>;P:<password>;;
        wifi_qr = "WIFI:T:WPA;S:Iskander_Hearth_Setup;P:solidarity;;"
        _print_qr(wifi_qr, "Join Setup Wi-Fi  (Iskander_Hearth_Setup / solidarity)")
        print(f"  After joining, open: http://{ap_ip}:8501\n")

    print("  " + "─" * 60)
    print("  No command-line setup required.")
    print("  Scan the QR code above with any smartphone to begin.\n")


if __name__ == "__main__":
    main()
