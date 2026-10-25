# -*- coding: utf-8 -*-
"""
ALIRA WebForge CLI runner.
Usage:
    python -m website_builder.main "create a dark gaming website"
"""
import argparse
import json
from .webforge_manager import WebForgeManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ALIRA WebForge from the command line.")
    parser.add_argument("command", nargs="+", help="Text command for WebForge")
    args = parser.parse_args()

    text = " ".join(args.command)
    manager = WebForgeManager()
    result = manager.handle_command(text)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
