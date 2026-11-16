#!/usr/bin/env bash
set -euo pipefail

rm -f "$HOME/.local/bin/mistral-bar" "$HOME/.local/bin/mistral-bar-config"
rm -f "$HOME/.local/share/applications/mistral-bar.desktop"
rm -f "$HOME/.config/autostart/mistral-bar.desktop"
rm -rf "$HOME/.local/share/mistral-bar"
echo "Mistral Bar uninstalled (config kept at ~/.config/mistral-bar)."
