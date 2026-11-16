# Mistral Bar

A lightweight native Linux app for Mistral AI. Instead of opening the website, press a
global hotkey (default `Ctrl+Alt+Space`) and a small floating bar appears — type your
question, hit Enter, and the answer shows up right there.

In **code mode** the assistant can access a local folder of your choice: it sees the
directory tree and can list folders and read text files inside the working directory.

## Features

- Spotlight-style quick bar centered at the top of the screen
- Global hotkey `Ctrl+Alt+Space` (X11); Wayland fallback via desktop shortcut binding
- `Esc` hides the bar; typing nothing and pressing Enter hides it too
- Conversation memory per session
- Modes:
  - `/chat` — normal fast chat mode (default)
  - `/code` — code mode with local folder access (list_dir / read_file tools)
  - `/clear` — clear conversation history
- Sandboxed file access: code mode can only touch files under the configured working
  directory; binary files and junk folders (`.git`, `node_modules`, …) are skipped

## Install

```bash
git clone https://github.com/iotserver24/vibe-app.git
cd vibe-app
./install.sh
```

The script installs a private venv, drops `mistral-bar` and `mistral-bar-config` into
`~/.local/bin`, and adds the app to autostart so it runs on every login.

## Configure

Get an API key from [console.mistral.com](https://console.mistral.com), then:

```bash
mistral-bar-config set api_key <YOUR_KEY>
mistral-bar-config set working_dir ~/projects/my-app   # folder used in /code mode
mistral-bar-config set model mistral-small-latest
```

Alternatively export `MISTRAL_API_KEY` in your shell profile. The config file lives at
`~/.config/mistral-bar/config.json`.

## Use

1. Press `Ctrl+Alt+Space` (or run `mistral-bar &` once if it is not running).
2. Type a question and press Enter.
3. Type `/code` to switch to code mode, then ask things like
   "what does app.py do?" or "find where the config is loaded".
4. Press `Esc` to hide the bar; it keeps running in the background.

### Wayland users

Global hotkeys need root or are unsupported on Wayland. Bind the command
`mistral-bar --toggle` to a custom shortcut in your desktop settings
(GNOME: Settings → Keyboard → Custom Shortcuts).

## Uninstall

```bash
rm -f ~/.local/bin/mistral-bar ~/.local/bin/mistral-bar-config \
      ~/.local/share/applications/mistral-bar.desktop \
      ~/.config/autostart/mistral-bar.desktop
rm -rf ~/.local/share/mistral-bar
```

## Tech

Python 3 + Tkinter (stdlib UI, no Electron), `requests` for the Mistral Chat Completions
API with function calling, and `keyboard` for the X11 global hotkey.
