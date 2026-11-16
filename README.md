# Mistral Bar

A native Linux desktop app for Mistral AI — like the ChatGPT/Claude desktop apps, but
lightweight (Python + Tkinter, no Electron). Chat in a full window with saved
conversations, and in **code mode** the assistant can read your local files.

## Features

- Full chat window: sidebar with conversation history (persisted between sessions),
  Markdown rendering with code blocks, bold, headings and lists
- Multi-line input: Enter sends, Shift+Enter adds a newline, `Ctrl+N` new chat
- **Code mode** (per conversation): the assistant gets a directory tree of your working
  directory and can list folders and read text files via Mistral function calling
- Sandboxed file access: only files under the configured working directory; binary
  files and junk folders (`.git`, `node_modules`, …) are skipped
- Settings dialog (API key, model, working directory, hotkey) — no terminal needed
- Show/hide the whole app with a desktop shortcut (`mistral-bar --toggle`)
- Auto-starts on login

## Install

```bash
git clone https://github.com/iotserver24/vibe-app.git
cd vibe-app
git checkout vibe/mistral-bar-f418eb
./install.sh
```

## Configure

Get an API key from [console.mistral.ai](https://console.mistral.ai), then either:

- open the app → **Settings** → paste the API key, or
- run `mistral-bar-config set api_key <YOUR_KEY>`

Set the folder used by code mode:

```bash
mistral-bar-config set working_dir /mnt/main-ssd/home-data/codes
```

## Set the shortcut (recommended)

Bind `mistral-bar --toggle` to `Ctrl+Alt+Space` in your desktop settings — this works
on both Wayland and X11 and needs no extra permissions:

- **GNOME**: Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts → Add
  - Command: `/home/you/.local/bin/mistral-bar --toggle`
  - Shortcut: `Ctrl+Alt+Space`
- **KDE**: System Settings → Shortcuts → Add New → Command or Script
  - Command: `/home/you/.local/bin/mistral-bar --toggle`
  - Trigger: `Ctrl+Alt+Space`

The app also tries to register the hotkey itself on X11, but that needs root or can
conflict with the desktop, so the custom shortcut is the reliable path.

## Use

1. Launch **Mistral** from your app menu (or `mistral-bar &`).
2. Type your question, press Enter.
3. Click **Toggle /chat /code** (or type `/code` in a chat) to let the assistant read
   files in your working directory, then ask things like "what does app.py do?".
4. Conversations are saved automatically and listed in the sidebar.

## Uninstall

```bash
./uninstall.sh
```

## Tech

Python 3 + Tkinter (stdlib UI), `requests` against the Mistral Chat Completions API with
function calling, conversations stored in `~/.local/share/mistral-bar/conversations.json`.
