import json
import os
from pathlib import Path

IGNORED_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build", ".mypy_cache"}
TEXT_SUFFIXES = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".sh", ".bash", ".zsh", ".html", ".css", ".scss",
    ".c", ".h", ".cpp", ".hpp", ".rs", ".go", ".java", ".kt", ".rb", ".php",
    ".sql", ".xml", ".csv", ".log", ".env", ".conf",
}


def _resolve(working_dir, path):
    root = Path(working_dir).resolve()
    target = (root / path).resolve() if not os.path.isabs(path) else Path(path)
    try:
        target.relative_to(root)
    except ValueError:
        raise PermissionError(f"Access denied: {path} is outside the working directory")
    return target


def list_dir(working_dir, path="."):
    target = _resolve(working_dir, path)
    if not target.is_dir():
        return {"error": f"Not a directory: {path}"}
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name in IGNORED_DIRS and child.is_dir():
            continue
        entries.append(("[dir] " if child.is_dir() else "      ") + child.name)
    return {"path": str(target), "entries": entries[:500]}


def read_file(working_dir, path, max_bytes):
    target = _resolve(working_dir, path)
    if not target.is_file():
        return {"error": f"Not a file: {path}"}
    if target.suffix.lower() not in TEXT_SUFFIXES:
        return {"error": f"Refusing to read binary/unknown file type: {path}"}
    data = target.read_bytes()[:max_bytes]
    return {"path": str(target), "content": data.decode("utf-8", errors="replace")}


def directory_tree(working_dir, max_depth=3):
    root = Path(working_dir).resolve()
    lines = [str(root)]
    count = 0

    def walk(directory, depth, prefix):
        nonlocal count
        if depth > max_depth or count > 400:
            return
        children = sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for child in children:
            if count > 400:
                lines.append(prefix + "...")
                return
            if child.name in IGNORED_DIRS and child.is_dir():
                continue
            count += 1
            is_last = child == children[-1]
            connector = "`-- " if is_last else "|-- "
            lines.append(prefix + connector + child.name)
            if child.is_dir():
                walk(child, depth + 1, prefix + ("    " if is_last else "|   "))

    walk(root, 1, "")
    return "\n".join(lines)


def execute_tool_call(tool, working_dir, max_bytes=60000):
    name = tool.get("function", {}).get("name")
    try:
        args = json.loads(tool["function"].get("arguments") or "{}")
    except (KeyError, json.JSONDecodeError):
        return {"error": "Invalid tool arguments"}
    try:
        if name == "list_dir":
            return list_dir(working_dir, args.get("path", "."))
        if name == "read_file":
            return read_file(working_dir, args.get("path", ""), max_bytes)
    except PermissionError as e:
        return {"error": str(e)}
    except OSError as e:
        return {"error": str(e)}
    return {"error": f"Unknown tool: {name}"}
