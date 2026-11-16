import re

INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`)")


def _add_inline(widget, text):
    for part in INLINE_RE.split(text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            widget.insert("end", part[2:-2], ("bold",))
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            widget.insert("end", part[1:-1], ("code",))
        elif part:
            widget.insert("end", part)


def render_markdown(widget, md):
    parts = re.split(r"```[a-zA-Z0-9_-]*\n?(.*?)```", md, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if i % 2 == 1:
            widget.insert("end", part)
            if not part.endswith("\n"):
                widget.insert("end", "\n")
            widget.tag_add("codeblock", "end-1c linestart", "end-1c")
            widget.insert("end", "\n")
            continue
        for line in part.split("\n"):
            stripped = line.strip()
            if not stripped:
                widget.insert("end", "\n")
            elif stripped.startswith("#"):
                widget.insert("end", stripped.lstrip("#").strip() + "\n", ("heading",))
            elif stripped.startswith(("- ", "* ", "• ")):
                widget.insert("end", "  • ", ("bullet",))
                _add_inline(widget, stripped[2:])
                widget.insert("end", "\n")
            elif re.match(r"^\d+\. ", stripped):
                widget.insert("end", "  " + stripped + "\n")
            else:
                _add_inline(widget, line)
                widget.insert("end", "\n")
