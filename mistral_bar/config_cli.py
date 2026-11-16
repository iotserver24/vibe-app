#!/usr/bin/env python3
import json
import sys

from mistral_bar.config import CONFIG_FILE, DEFAULTS, load_config, save_config


def main():
    cfg = load_config()
    if len(sys.argv) >= 3 and sys.argv[1] == "set":
        key, value = sys.argv[2], sys.argv[3]
        if key not in DEFAULTS:
            print(f"Unknown key: {key}. Valid keys: {', '.join(DEFAULTS)}")
            sys.exit(1)
        cfg[key] = value
        save_config(cfg)
        print(f"Set {key}.")
        return
    print(f"Config file: {CONFIG_FILE}")
    print(f"API key: {'(set via env)' if cfg['api_key'].startswith('sk-') else '(from env or config, hidden)' if cfg['api_key'] else '(not set)'}")
    print(json.dumps({k: v for k, v in cfg.items() if k != "api_key"}, indent=2))
    print("Change values with: mistral-bar-config set <key> <value>")


if __name__ == "__main__":
    main()
