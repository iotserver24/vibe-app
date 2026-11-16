#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.local/share/mistral-bar/venv"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/.config/autostart"

mkdir -p "$BIN_DIR" "$APP_DIR" "$VENV_DIR"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$REPO_DIR/requirements.txt"

cat > "$BIN_DIR/mistral-bar" <<EOF
#!/bin/bash
export PYTHONPATH="$REPO_DIR:\$PYTHONPATH"
exec "$VENV_DIR/bin/python3" -m mistral_bar.app "\$@"
EOF
chmod +x "$BIN_DIR/mistral-bar"

cat > "$BIN_DIR/mistral-bar-config" <<EOF
#!/bin/bash
export PYTHONPATH="$REPO_DIR:\$PYTHONPATH"
exec "$VENV_DIR/bin/python3" -m mistral_bar.config_cli "\$@"
EOF
chmod +x "$BIN_DIR/mistral-bar-config"

cat > "$APP_DIR/mistral-bar.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Mistral Bar
Comment=Quick-launch AI bar for Mistral
Exec=$BIN_DIR/mistral-bar
Icon=utilities-terminal
Terminal=false
Categories=Utility;
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

cat > "$AUTOSTART_DIR/mistral-bar.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Mistral Bar
Exec=$BIN_DIR/mistral-bar
Icon=utilities-terminal
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "Installed:"
echo "  $BIN_DIR/mistral-bar         (main app, auto-starts on login)"
echo "  $BIN_DIR/mistral-bar-config  (configuration)"
echo ""
echo "Next steps:"
echo "  1. Get an API key from https://console.mistral.ai, then set it in the"
echo "     app's Settings dialog (or: mistral-bar-config set api_key <YOUR_KEY>)"
echo "  2. Log out and back in (or run 'mistral-bar &' now) to start the app."
echo "  3. RECOMMENDED shortcut setup (works on Wayland and X11):"
echo "     - GNOME: Settings -> Keyboard -> Custom Shortcuts -> Add"
echo "       Command: $HOME/.local/bin/mistral-bar --toggle   Key: Ctrl+Alt+Space"
echo "     - KDE: System Settings -> Shortcuts -> Custom -> Add Command"
echo "       Command: $HOME/.local/bin/mistral-bar --toggle   Key: Ctrl+Alt+Space"
