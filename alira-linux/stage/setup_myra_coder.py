#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ALIRA Coder Setup Script
========================
ALIRA_coder/ ka Node.js project build karta hai.
Run karo: python setup_ALIRA_coder.py

Requirements:
  - Node.js 18+ (https://nodejs.org)
  - npm (Node ke saath aata hai)
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path


def find_executable(*names):
    """PATH mein executable dhoondo, Windows ke .cmd/.exe support ke saath."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def check_node():
    """Node.js check karo."""
    node_path = find_executable("node", "node.exe")
    if not node_path:
        return False

    try:
        result = subprocess.run([node_path, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            ver = result.stdout.strip()
            print(f"✅ Node.js found: {ver}")
            major = int(ver.lstrip('v').split('.')[0])
            if major < 18:
                print(f"⚠️  Warning: Node.js v18+ chahiye, mila: {ver}")
            return True
        return False
    except OSError:
        return False


def check_npm():
    """npm check karo."""
    npm_path = find_executable("npm", "npm.cmd", "npm.exe")
    if not npm_path:
        return False

    try:
        result = subprocess.run([npm_path, "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ npm found: {result.stdout.strip()}")
            return True
        return False
    except OSError:
        return False


def build_ALIRA_coder():
    """ALIRA_coder TypeScript project build karo."""
    coder_dir = Path(__file__).parent / "ALIRA_coder"
    if not coder_dir.exists():
        print(f"❌ ALIRA_coder/ folder nahi mila: {coder_dir}")
        return False

    print(f"\n📁 ALIRA_coder directory: {coder_dir}")

    npm_path = find_executable("npm", "npm.cmd", "npm.exe")
    if not npm_path:
        print("❌ npm executable not found in PATH")
        return False

    # npm install
    print("\n📦 Installing Node.js dependencies...")
    result = subprocess.run(
        [npm_path, "install"],
        cwd=str(coder_dir),
        capture_output=False,
    )
    if result.returncode != 0:
        print("❌ npm install failed!")
        return False
    print("✅ Dependencies installed")

    # npm run build (TypeScript compile)
    print("\n🔨 Building TypeScript...")
    result = subprocess.run(
        [npm_path, "run", "build"],
        cwd=str(coder_dir),
        capture_output=False,
    )
    if result.returncode != 0:
        print("❌ TypeScript build failed!")
        return False

    # Verify dist/run.js exists
    run_js = coder_dir / "dist" / "run.js"
    if run_js.exists():
        print(f"✅ Build successful: {run_js}")
        return True
    else:
        print(f"❌ dist/run.js nahi mila after build!")
        return False


def setup_ALIRA_coder_config(env_file: Path):
    """~/.ALIRA-coder/config.json setup karo with API keys from .env."""
    import re

    # Read .env
    keys = {}
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                keys[k.strip()] = v.strip()

    config_dir = Path.home() / ".ALIRA-coder"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    # Default config
    config = {
        "provider": "gemini",
        "model": "gemini-3.5-flash-lite",  # 2.5-flash free quota/retired => 3.5-flash-lite
        "ollamaUrl": "http://localhost:11434",
        "apiKeys": {
            "anthropic": keys.get("ANTHROPIC_API_KEY", ""),
            "gemini": keys.get("GEMINI_API_KEY", ""),
            "openrouter": keys.get("OPENROUTER_API_KEY", ""),
            "nvidia": keys.get("NVIDIA_API_KEY", ""),
        },
        "temperature": 0.1,
        "mode": "agent",
        "editApproval": "auto",
        "autoMode": "auto",
        "compactThreshold": 0.8,
        "subagents": {
            "enabled": False,
            "maxPerTurn": 2
        },
        "mcpServers": {}
    }

    # Agar Anthropic key hai aur Gemini nahi to Anthropic use karo
    if config["apiKeys"]["anthropic"] and not config["apiKeys"]["gemini"]:
        config["provider"] = "anthropic"
        config["model"] = "claude-sonnet-4-6"

    config_file.write_text(json.dumps(config, indent=2), encoding='utf-8')
    print(f"✅ ALIRA Coder config saved: {config_file}")
    print(f"   Provider: {config['provider']} | Model: {config['model']}")

    return config


def create_projects_dir():
    """Projects folder banao jahan websites save honge."""
    projects_dir = Path(__file__).parent / "Projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    gitkeep = projects_dir / ".gitkeep"
    if not gitkeep.exists():
        gitkeep.touch()
    print(f"✅ Projects directory ready: {projects_dir}")
    return str(projects_dir)


def main():
    print("=" * 60)
    print("  ALIRA CODER SETUP")
    print("  AI Website Builder Engine")
    print("=" * 60)

    # 1. Node.js check
    if not check_node():
        print("\n❌ Node.js nahi mila!")
        print("   Install karo: https://nodejs.org (LTS version)")
        print("   Phir yeh script dobara chalao.")
        sys.exit(1)

    if not check_npm():
        print("\n❌ npm nahi mila!")
        print("   Node.js ke saath npm automatically aata hai.")
        print("   Node.js reinstall karo: https://nodejs.org")
        sys.exit(1)

    # 2. Projects folder
    print("\n📁 Setting up Projects directory...")
    create_projects_dir()

    # 3. Build ALIRA_coder
    print("\n🔨 Building ALIRA Coder engine...")
    if not build_ALIRA_coder():
        print("\n❌ Build failed! Check errors above.")
        sys.exit(1)

    # 4. Config setup
    print("\n⚙️  Setting up ALIRA Coder config...")
    env_file = Path(__file__).parent / ".env"
    config = setup_ALIRA_coder_config(env_file)

    print("\n" + "=" * 60)
    print("  ✅ ALIRA CODER SETUP COMPLETE!")
    print("=" * 60)
    print(f"\n  Provider: {config['provider']}")
    print(f"  Model:    {config['model']}")
    print(f"\n  Ab ALIRA run karo: python TABBU.py")
    print(f"  Voice command: 'gaming website banao'")
    print(f"  Websites save honge: {Path(__file__).parent / 'Projects'}")
    print()


if __name__ == "__main__":
    main()
