import argparse
import json
import queue
import socket
import sys
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import __version__
from .config import load_config, save_config
from .markdown import render_markdown
from .mistral_client import MistralError, chat, extract_reply, extract_tool_calls
from .storage import load_conversations, new_conversation, save_conversations
from .tools import TOOL_DEFS, directory_tree, execute_tool_call

CHAT_SYSTEM = "You are Mistral, an AI assistant inside a desktop app on the user's Linux machine. Answer helpfully and use Markdown formatting (code blocks with ``` fences, bold, lists, headings) when it improves clarity."

CODE_SYSTEM_TEMPLATE = """You are Mistral in code mode, an AI coding assistant with access to the user's local working directory: {working_dir}

Directory tree (depth-limited):
{tree}

You can use tools to explore further:
- list_dir(path): list a directory
- read_file(path): read a text file

Paths resolve relative to the working directory; you cannot access files outside it. Use Markdown with ``` code fences when showing code. When the user asks about code, inspect the relevant files with tools instead of guessing."""

TOGGLE_PORT = 47631

COLORS = {
    "bg": "#1e1e2e",
    "sidebar": "#181825",
    "chat": "#1e1e2e",
    "input": "#181825",
    "fg": "#cdd6f4",
    "muted": "#6c7086",
    "accent": "#89b4fa",
    "user_bubble": "#313244",
    "code_bg": "#11111b",
}


class MistralApp:
    def __init__(self, cfg):
        self.cfg = cfg
        self.conversations = load_conversations()
        self.current_id = None
        self.events = queue.Queue()
        self.busy = False

        self.root = tk.Tk()
        self.root.title("Mistral")
        self.root.geometry("1000x680")
        self.root.minsize(700, 480)
        self.root.configure(bg=COLORS["bg"])
        self.visible = True

        self._build_ui()
        self._bind_keys()

        if self.conversations:
            self._select_conversation(self.conversations[0]["id"])
        else:
            self._new_chat()

        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.root.after(100, self._poll_events)

    def _bind_keys(self):
        self.root.bind("<Escape>", lambda e: self.hide())
        self.root.bind("<Control-n>", lambda e: self._new_chat())
        input_only = self.input_widget
        input_only.bind("<Return>", self._on_send)
        input_only.bind("<Shift-Return>", lambda e: None)

    def _build_ui(self):
        sidebar = tk.Frame(self.root, bg=COLORS["sidebar"], width=230)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        title = tk.Label(sidebar, text="  Mistral", fg=COLORS["fg"], bg=COLORS["sidebar"],
                         font=("Sans", 15, "bold"), anchor="w")
        title.pack(fill="x", pady=(14, 8))

        new_btn = tk.Button(sidebar, text="＋  New chat", command=self._new_chat,
                           bg=COLORS["accent"], fg="#1e1e2e", relief="flat",
                           font=("Sans", 11, "bold"), pady=4, cursor="hand2")
        new_btn.pack(fill="x", padx=10, pady=(0, 10))

        self.chat_list = tk.Listbox(sidebar, bg=COLORS["sidebar"], fg=COLORS["fg"],
                                   relief="flat", borderwidth=0, highlightthickness=0,
                                   selectbackground=COLORS["user_bubble"],
                                   font=("Sans", 11), activestyle="none")
        self.chat_list.pack(fill="both", expand=True, padx=6)
        self.chat_list.bind("<<ListboxSelect>>", self._on_select)

        self.mode_lbl = tk.Label(sidebar, text="mode: chat", fg=COLORS["muted"],
                                 bg=COLORS["sidebar"], font=("Sans", 10), anchor="w")
        self.mode_lbl.pack(fill="x", padx=12, pady=(6, 0))
        mode_btn = tk.Button(sidebar, text="Toggle /chat  /code", command=self._toggle_mode,
                            bg=COLORS["sidebar"], fg=COLORS["accent"], relief="flat",
                            font=("Sans", 10), anchor="w", cursor="hand2")
        mode_btn.pack(fill="x", padx=8)

        settings_btn = tk.Button(sidebar, text="⚙  Settings", command=self._open_settings,
                                 bg=COLORS["sidebar"], fg=COLORS["fg"], relief="flat",
                                 font=("Sans", 11), anchor="w", cursor="hand2")
        settings_btn.pack(fill="x", padx=8, pady=(10, 14))

        main = tk.Frame(self.root, bg=COLORS["chat"])
        main.pack(side="right", fill="both", expand=True)

        self.chat_view = tk.Text(main, bg=COLORS["chat"], fg=COLORS["fg"],
                                 relief="flat", wrap="word", state="disabled",
                                 padx=18, pady=14, font=("Sans", 12), spacing1=4, spacing3=4)
        chat_scroll = ttk.Scrollbar(main, command=self.chat_view.yview)
        self.chat_view.configure(yscrollcommand=chat_scroll.set)
        chat_scroll.pack(side="right", fill="y")
        self.chat_view.pack(fill="both", expand=True)
        self._configure_tags()

        input_frame = tk.Frame(main, bg=COLORS["input"])
        input_frame.pack(fill="x", padx=14, pady=12)
        self.input_widget = tk.Text(input_frame, bg=COLORS["input"], fg=COLORS["fg"],
                                   relief="flat", font=("Sans", 12), height=4,
                                   insertbackground=COLORS["fg"], padx=10, pady=8,
                                   highlightthickness=1,
                                   highlightbackground=COLORS["user_bubble"])
        self.input_widget.pack(side="left", fill="both", expand=True, pady=(0, 0))
        send_btn = tk.Button(input_frame, text="Send ⏎", command=self._on_send_click,
                             bg=COLORS["accent"], fg="#1e1e2e", relief="flat",
                             font=("Sans", 11, "bold"), padx=16, cursor="hand2")
        send_btn.pack(side="right", fill="y", padx=(10, 0))

    def _configure_tags(self):
        t = self.chat_view
        t.tag_configure("user_label", foreground=COLORS["accent"], font=("Sans", 10, "bold"))
        t.tag_configure("ai_label", foreground="#a6e3a1", font=("Sans", 10, "bold"))
        t.tag_configure("user_msg", foreground=COLORS["fg"], lmargin1=10, lmargin2=10)
        t.tag_configure("bold", font=("Sans", 12, "bold"))
        t.tag_configure("code", font=("Monospace", 11), foreground="#f9e2af")
        t.tag_configure("codeblock", font=("Monospace", 11), background=COLORS["code_bg"],
                        foreground="#cdd6f4", lmargin1=10, lmargin2=10)
        t.tag_configure("heading", font=("Sans", 14, "bold"), foreground=COLORS["accent"])
        t.tag_configure("bullet", foreground=COLORS["accent"])

    @property
    def current(self):
        for c in self.conversations:
            if c["id"] == self.current_id:
                return c
        return None

    def _refresh_sidebar(self):
        self.chat_list.delete(0, "end")
        for c in self.conversations:
            self.chat_list.insert("end", f"  {c['title']}")
        if self.current:
            for i, c in enumerate(self.conversations):
                if c["id"] == self.current_id:
                    self.chat_list.selection_clear(0, "end")
                    self.chat_list.selection_set(i)
                    self.chat_list.see(i)
                    break
        mode = self.current["mode"] if self.current else "chat"
        self.mode_lbl.config(text=f"mode: {mode}")

    def _new_chat(self):
        conv = new_conversation()
        self.conversations.insert(0, conv)
        self.current_id = conv["id"]
        save_conversations(self.conversations)
        self._refresh_sidebar()
        self._render_chat()
        self.input_widget.focus_set()

    def _on_select(self, _event):
        sel = self.chat_list.curselection()
        if sel:
            self._select_conversation(self.conversations[sel[0]]["id"])

    def _select_conversation(self, conv_id):
        self.current_id = conv_id
        self._refresh_sidebar()
        self._render_chat()

    def _toggle_mode(self):
        if self.current:
            self.current["mode"] = "chat" if self.current["mode"] == "code" else "code"
            save_conversations(self.conversations)
            self._refresh_sidebar()

    def _render_chat(self):
        t = self.chat_view
        t.configure(state="normal")
        t.delete("1.0", "end")
        conv = self.current
        if not conv or not conv["messages"]:
            t.insert("end", "\n  Start chatting — ask anything.\n\n"
                             "  In /code mode the assistant can read files in your\n"
                             "  working directory (set it in Settings).\n", ("muted",))
        else:
            for m in conv["messages"]:
                if m["role"] == "user":
                    t.insert("end", "\nYou\n", ("user_label",))
                    t.insert("end", m["content"] + "\n", ("user_msg",))
                elif m["role"] == "assistant":
                    t.insert("end", "\nMistral\n", ("ai_label",))
                    render_markdown(t, m["content"])
        t.tag_configure("muted", foreground=COLORS["muted"])
        t.configure(state="disabled")
        t.see("end")

    def _on_send_click(self):
        self._send()

    def _on_send(self, _event):
        self._send()
        return "break"

    def _send(self):
        if self.busy:
            return
        query = self.input_widget.get("1.0", "end").strip()
        if not query:
            return
        self.input_widget.delete("1.0", "end")
        conv = self.current
        conv["messages"].append({"role": "user", "content": query})
        if conv["title"] == "New chat":
            conv["title"] = query[:42] + ("…" if len(query) > 42 else "")
        save_conversations(self.conversations)
        self._refresh_sidebar()
        self._render_chat()
        self.busy = True
        threading.Thread(target=self._run_query, args=(conv["id"], query), daemon=True).start()

    def _run_query(self, conv_id, query):
        try:
            answer = self._agent_loop(conv_id, query)
            self.events.put(("answer", conv_id, answer))
        except MistralError as e:
            self.events.put(("error", conv_id, str(e)))

    def _agent_loop(self, conv_id, query):
        conv = next((c for c in self.conversations if c["id"] == conv_id), None)
        if not conv:
            return "(conversation missing)"
        system = CHAT_SYSTEM
        tools = None
        if conv["mode"] == "code":
            tree = directory_tree(self.cfg["working_dir"])
            system = CODE_SYSTEM_TEMPLATE.format(
                working_dir=self.cfg["working_dir"], tree=tree
            )
            tools = TOOL_DEFS
        messages = [{"role": "system", "content": system}] + conv["messages"][:-1] + [
            {"role": "user", "content": query}
        ]
        for _ in range(self.cfg["max_tool_iterations"]):
            response = chat(self.cfg["api_key"], self.cfg["model"], messages, tools)
            message = response["choices"][0]["message"]
            tool_calls = extract_tool_calls(message)
            if not tool_calls:
                return extract_reply(message) or "(empty response)"
            messages.append(message)
            for call in tool_calls:
                result = execute_tool_call(call, self.cfg["working_dir"], self.cfg["max_file_bytes"])
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": call["function"]["name"],
                    "content": json.dumps(result),
                })
        return "Reached tool call limit; try a more specific question."

    def _poll_events(self):
        try:
            while True:
                kind, conv_id, payload = self.events.get_nowait()
                conv = next((c for c in self.conversations if c["id"] == conv_id), None)
                if not conv:
                    continue
                if kind == "answer":
                    conv["messages"].append({"role": "assistant", "content": payload})
                elif kind == "error":
                    conv["messages"].append(
                        {"role": "assistant", "content": f"⚠️ {payload}"})
                save_conversations(self.conversations)
                self.busy = False
                if self.current_id == conv_id:
                    self._render_chat()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.configure(bg=COLORS["bg"])
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        fields = [
            ("Model", "model"),
            ("Working directory (/code mode)", "working_dir"),
            ("Hotkey (X11 only)", "hotkey"),
        ]
        entries = {}

        def add_row(label, key, value, show=None):
            tk.Label(win, text=label, fg=COLORS["fg"], bg=COLORS["bg"],
                     font=("Sans", 11)).pack(anchor="w", padx=16, pady=(10, 2))
            e = tk.Entry(win, fg=COLORS["fg"], bg=COLORS["input"], relief="flat",
                         insertbackground=COLORS["fg"], font=("Sans", 11), width=44,
                         show=show)
            e.insert(0, value)
            e.pack(padx=16, fill="x")
            entries[key] = e

        tk.Label(win, text="API key", fg=COLORS["fg"], bg=COLORS["bg"],
                 font=("Sans", 11)).pack(anchor="w", padx=16, pady=(12, 2))
        api_entry = tk.Entry(win, fg=COLORS["fg"], bg=COLORS["input"], relief="flat",
                             insertbackground=COLORS["fg"], font=("Sans", 11),
                             width=44, show="•")
        api_entry.insert(0, self.cfg["api_key"])
        api_entry.pack(padx=16, fill="x")

        for label, key in fields:
            add_row(label, key, self.cfg[key])

        def browse():
            path = filedialog.askdirectory(initialdir=self.cfg["working_dir"])
            if path:
                entries["working_dir"].delete(0, "end")
                entries["working_dir"].insert(0, path)

        tk.Button(win, text="Browse…", command=browse, bg=COLORS["user_bubble"],
                  fg=COLORS["fg"], relief="flat", cursor="hand2").pack(padx=16, pady=4)

        def save():
            self.cfg["api_key"] = api_entry.get().strip()
            for key, e in entries.items():
                self.cfg[key] = e.get().strip()
            save_config(self.cfg)
            win.destroy()
            messagebox.showinfo("Settings", "Saved. Restart mistral-bar to apply the hotkey.")

        tk.Button(win, text="Save", command=save, bg=COLORS["accent"], fg="#1e1e2e",
                  relief="flat", font=("Sans", 11, "bold"), padx=20, pady=3,
                  cursor="hand2").pack(pady=14)

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def hide(self):
        self.visible = False
        self.root.withdraw()

    def show(self):
        self.visible = True
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))
        self.input_widget.focus_set()

    def run(self):
        self.root.mainloop()


def send_toggle():
    try:
        with socket.create_connection(("127.0.0.1", TOGGLE_PORT), timeout=1):
            return True
    except OSError:
        return False


def run_toggle_server(app):
    def serve():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("127.0.0.1", TOGGLE_PORT))
            server.listen(5)
            while True:
                conn, _ = server.accept()
                conn.close()
                app.root.after(0, app.toggle)
        except OSError:
            pass
    threading.Thread(target=serve, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(prog="mistral-bar", description="Mistral desktop app for Linux")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--toggle", action="store_true", help="Show/hide a running instance (bind this to a desktop shortcut)")
    args = parser.parse_args()

    if args.toggle:
        sys.exit(0 if send_toggle() else 1)

    cfg = load_config()
    if not cfg["api_key"]:
        print("No API key found. Set MISTRAL_API_KEY or use Settings in the app "
              "(or: mistral-bar-config set api_key <KEY>).", file=sys.stderr)
        sys.exit(2)

    app = MistralApp(cfg)
    run_toggle_server(app)
    hotkey_bound = False
    try:
        import keyboard
        keyboard.add_hotkey(cfg["hotkey"], lambda: app.root.after(0, app.toggle))
        hotkey_bound = True
    except Exception:
        pass
    if not hotkey_bound:
        print(
            "Note: global hotkey could not be registered (common on Wayland, or no root).\n"
            "Bind this command to a custom shortcut in your desktop settings instead:\n"
            "    mistral-bar --toggle\n"
            "On first run, the app window opens normally; the shortcut just shows/hides it.",
            file=sys.stderr,
        )
    app.run()


def main_with_logging():
    try:
        main()
    except Exception:
        from pathlib import Path

        log = Path.home() / ".local/share/mistral-bar/error.log"
        try:
            log.parent.mkdir(parents=True, exist_ok=True)
            with open(log, "a", encoding="utf-8") as f:
                f.write(traceback.format_exc() + "\n")
        except OSError:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox

            r = tk.Tk(); r.withdraw()
            messagebox.showerror("Mistral — startup error", traceback.format_exc()[-1500:])
            r.destroy()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main_with_logging()
