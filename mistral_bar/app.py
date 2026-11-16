import argparse
import json
import queue
import socket
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

from . import __version__
from .config import load_config
from .mistral_client import MistralError, chat, extract_reply, extract_tool_calls
from .tools import directory_tree, execute_tool_call

TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and folders in a directory inside the working directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative or absolute path"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file inside the working directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative or absolute path"}},
                "required": ["path"],
            },
        },
    },
]

CHAT_SYSTEM = "You are Mistral Bar, a quick-launch AI assistant on Linux. Answer concisely and directly. Use Markdown-free plain text (the UI is a small popup window). Keep answers short unless detail is clearly needed."

CODE_SYSTEM_TEMPLATE = """You are Mistral Bar in code mode, an AI assistant with access to the user's local working directory: {working_dir}

Directory tree (depth-limited):
{tree}

You can use tools to explore further:
- list_dir(path): list a directory
- read_file(path): read a text file

Paths are resolved relative to the working directory; you cannot access files outside it. Answer concisely in plain text (the UI is a small popup window). When the user asks about code, inspect the relevant files first with tools instead of guessing."""

TOGGLE_PORT = 47631


class MistralBar:
    def __init__(self, cfg):
        self.cfg = cfg
        self.mode = "chat"
        self.messages = []
        self.events = queue.Queue()
        self.root = tk.Tk()
        self.root.title("Mistral Bar")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#1e1e2e")
        self.visible = True
        self._build_widgets()
        self.root.bind("<Escape>", lambda e: self.hide())
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self._center_bar()
        self.root.after(100, self._poll_events)

    def _build_widgets(self):
        self.status_lbl = tk.Label(
            self.root, text="[chat]", fg="#89b4fa", bg="#1e1e2e",
            font=("Sans", 10), padx=6,
        )
        self.status_lbl.pack(side="left")
        self.entry = tk.Entry(
            self.root, font=("Sans", 13), fg="#cdd6f4", bg="#1e1e2e",
            insertbackground="#cdd6f4", relief="flat", width=52, highlightthickness=0,
        )
        self.entry.pack(side="left", padx=(2, 8), pady=8)
        self.entry.bind("<Return>", self._on_submit)

        self.answer_frame = tk.Frame(self.root, bg="#181825")
        self.answer_text = tk.Text(
            self.answer_frame, font=("Sans", 11), fg="#cdd6f4", bg="#181825",
            wrap="word", relief="flat", height=12, width=56, padx=10, pady=8,
        )
        self.answer_text.pack(fill="both", expand=True)
        self.answer_text.configure(state="disabled")

    def _center_bar(self):
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        x = (self.root.winfo_screenwidth() - w) // 2
        self.root.geometry(f"+{x}+80")

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
        self.entry.focus_set()

    def _on_submit(self, _event):
        query = self.entry.get().strip()
        if not query:
            self.hide()
            return
        if query in ("/code", "/chat"):
            self.mode = "code" if query == "/code" else "chat"
            self.status_lbl.config(text=f"[{self.mode}]")
            self.entry.delete(0, "end")
            return
        if query == "/clear":
            self.messages = []
            self._set_answer("History cleared.")
            self.entry.delete(0, "end")
            return
        self.entry.delete(0, "end")
        self._set_answer("Thinking...")
        threading.Thread(target=self._run_query, args=(query,), daemon=True).start()

    def _set_answer(self, text):
        self.answer_frame.pack(side="top", fill="both", padx=6, pady=(0, 6))
        self.answer_text.configure(state="normal")
        self.answer_text.delete("1.0", "end")
        self.answer_text.insert("1.0", text)
        self.answer_text.configure(state="disabled")

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "answer":
                    self._set_answer(payload)
                elif kind == "error":
                    self._set_answer(f"Error: {payload}")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _run_query(self, query):
        try:
            answer = self._agent_loop(query)
            self.events.put(("answer", answer))
        except MistralError as e:
            self.events.put(("error", str(e)))

    def _agent_loop(self, query):
        system = CHAT_SYSTEM
        tools = None
        if self.mode == "code":
            tree = directory_tree(self.cfg["working_dir"])
            system = CODE_SYSTEM_TEMPLATE.format(
                working_dir=self.cfg["working_dir"], tree=tree
            )
            tools = TOOL_DEFS
        self.messages.append({"role": "system", "content": system})
        self.messages.append({"role": "user", "content": query})
        for _ in range(self.cfg["max_tool_iterations"]):
            response = chat(self.cfg["api_key"], self.cfg["model"], self.messages, tools)
            message = response["choices"][0]["message"]
            tool_calls = extract_tool_calls(message)
            if not tool_calls:
                reply = extract_reply(message) or "(empty response)"
                self.messages.append({"role": "assistant", "content": reply})
                self._trim_history()
                return reply
            self.messages.append(message)
            for call in tool_calls:
                result = execute_tool_call(call, self.cfg["working_dir"], self.cfg["max_file_bytes"])
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": call["function"]["name"],
                    "content": json.dumps(result),
                })
        return "Reached tool call limit; try a more specific question."

    def _trim_history(self):
        if len(self.messages) > self.cfg["history_limit"]:
            system = [m for m in self.messages if m["role"] == "system"]
            rest = [m for m in self.messages if m["role"] != "system"]
            self.messages = system + rest[-(self.cfg["history_limit"] - 1):]

    def run(self):
        self.root.mainloop()


def send_toggle():
    try:
        with socket.create_connection(("127.0.0.1", TOGGLE_PORT), timeout=1):
            return True
    except OSError:
        return False


def run_toggle_server(bar):
    def serve():
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(("127.0.0.1", TOGGLE_PORT))
            server.listen(5)
            while True:
                conn, _ = server.accept()
                conn.close()
                bar.root.after(0, bar.toggle)
        except OSError:
            pass
    threading.Thread(target=serve, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(prog="mistral-bar", description="Mistral AI quick-launch bar for Linux")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--toggle", action="store_true", help="Toggle an already-running instance (used by desktop shortcuts)")
    args = parser.parse_args()

    if args.toggle:
        sys.exit(0 if send_toggle() else 1)

    cfg = load_config()
    if not cfg["api_key"]:
        print("No API key found. Set MISTRAL_API_KEY or run `mistral-bar-config`.", file=sys.stderr)
        sys.exit(2)

    bar = MistralBar(cfg)
    run_toggle_server(bar)
    try:
        import keyboard
        keyboard.add_hotkey(cfg["hotkey"], lambda: bar.root.after(0, bar.toggle))
    except Exception:
        print(
            "Warning: global hotkey unavailable (Wayland or no permission). "
            "Bind `mistral-bar --toggle` to a shortcut in your desktop settings instead.",
            file=sys.stderr,
        )
    bar.run()
