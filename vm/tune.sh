#!/usr/bin/env bash
# Make the Ubuntu VM lighter for running Queneth. Safe and reversible.
#   vm/tune.sh          apply (asks for your password once, for the system part)
#   vm/tune.sh --undo   put everything back
#
# What it changes:
#   Desktop (no password):  animations off; the file indexer (localsearch) off,
#                           so it stops re-scanning node_modules and builds.
#   System (password):      swap used only when memory is really short;
#                           printing (CUPS), mobile-modem (ModemManager) and
#                           network discovery (Avahi) services off — a VM
#                           doesn't need them.
# Security updates (unattended-upgrades) are left on on purpose.
set -euo pipefail

SERVICES=(cups.service cups-browsed.service cups.socket cups.path ModemManager.service
          avahi-daemon.service avahi-daemon.socket)
SYSCTL=/etc/sysctl.d/99-queneth.conf
MINER=org.freedesktop.Tracker3.Miner.Files

if [[ "${1:-}" == "--undo" ]]; then
  echo "Restoring the desktop settings…"
  gsettings reset org.gnome.desktop.interface enable-animations || true
  for k in index-recursive-directories index-single-directories enable-monitors crawling-interval; do
    gsettings reset "$MINER" "$k" || true
  done
  gsettings reset org.gnome.desktop.search-providers disable-external || true
  systemctl --user unmask localsearch-3.service 2>/dev/null || true
  systemctl --user start localsearch-3.service 2>/dev/null || true
  echo "Restoring the system settings (your password may be asked)…"
  sudo rm -f "$SYSCTL"
  sudo sysctl -q vm.swappiness=60 vm.vfs_cache_pressure=100
  for s in "${SERVICES[@]}"; do sudo systemctl unmask "$s" 2>/dev/null || true; done
  sudo systemctl enable --now cups.service cups-browsed.service ModemManager.service avahi-daemon.service 2>/dev/null || true
  echo "Done: everything is back to Ubuntu's defaults."
  exit 0
fi

echo "Desktop: animations and file indexing off…"
gsettings set org.gnome.desktop.interface enable-animations false
gsettings set "$MINER" index-recursive-directories "[]"
gsettings set "$MINER" index-single-directories "[]"
gsettings set "$MINER" enable-monitors false
gsettings set "$MINER" crawling-interval -2
gsettings set org.gnome.desktop.search-providers disable-external true
systemctl --user stop localsearch-3.service 2>/dev/null || true
systemctl --user mask localsearch-3.service >/dev/null 2>&1 || true

echo "System: swap and unused services (your password may be asked)…"
printf 'vm.swappiness=10\nvm.vfs_cache_pressure=50\n' | sudo tee "$SYSCTL" >/dev/null
sudo sysctl -q -p "$SYSCTL"
for s in "${SERVICES[@]}"; do
  sudo systemctl disable --now "$s" >/dev/null 2>&1 || true
done

echo
echo "Done. Swappiness is now $(cat /proc/sys/vm/swappiness)."
still="$(for s in cups ModemManager avahi-daemon; do systemctl is-active --quiet "$s" && printf '%s ' "$s"; done)"
echo "Printing, modem and network-discovery services: ${still:+still running: $still}${still:-off}"
echo "Undo any time with: vm/tune.sh --undo"
