# -*- coding: utf-8 -*-
"""
PyPI Auto-Publisher for ALIRA AI Assistant
==========================================

Build and publish to PyPI automatically using stored credentials.

Usage:
    python publish_to_pypi.py              # Full build + publish
    python publish_to_pypi.py --dry-run    # Test without publishing
    python publish_to_pypi.py --build-only # Just build, don't publish
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment vTABBUbles from .env
BASE_DIR = Path(__file__).parent.parent.absolute()
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

def check_requirements():
    """Ensure build tools are installed."""
    required_packages = ["build", "twine", "wheel", "setuptools"]

    print("  Checking required packages...")
    for pkg in required_packages:
        try:
            __import__(pkg.replace("-", "_"))
            print(f"   ✓ {pkg}")
        except ImportError:
            print(f"   ✗ {pkg} not found. Installing...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg],
                capture_output=True
            )

def build_distribution():
    """Build wheel and source distribution."""
    print("\n" + "=" * 62)
    print("  Building Distribution Packages")
    print("=" * 62)

    os.chdir(BASE_DIR)

    # Clean old builds
    print("\n  Cleaning old builds...")
    for d in ["build", "dist", "*.egg-info"]:
        subprocess.run(
            f'if exist "{d}" rmdir /S /Q "{d}"' if sys.platform == "win32" else f"rm -rf {d}",
            shell=True,
            capture_output=True
        )

    # --wheel only: the wheel ships compiled .pyc (see setup.py's
    # build_py_compiled). The sdist (`python -m build` without --wheel)
    # still contains plain .py source per MANIFEST.in, so it must never
    # be built/uploaded here or PyPI would serve readable source anyway.
    print("  Building wheel only (compiled .pyc, no source) with setuptools...")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        capture_output=False
    )

    if result.returncode != 0:
        print("\n  ❌ Build failed!")
        return False

    print("\n  ✅ Build successful!")

    # Check what was built
    dist_dir = BASE_DIR / "dist"
    if dist_dir.exists():
        files = list(dist_dir.glob("*"))
        print(f"\n  Generated files in {dist_dir}:")
        for f in files:
            size_mb = f.stat().st_size / 1_000_000
            print(f"    • {f.name} ({size_mb:.2f} MB)")
        return True

    return False

def publish_to_pypi(dry_run=False):
    """Publish to PyPI using twine."""
    print("\n" + "=" * 62)
    print("  Publishing to PyPI")
    print("=" * 62)

    # Get credentials from environment (.env takes priority)
    username = os.getenv("username") or os.getenv("USERNAME") or "__token__"
    # Force token authentication if username is the Windows computer name
    if username.upper() == "Ali" or not username.startswith("__"):
        username = "__token__"

    password = os.getenv("password")

    if not password:
        print("\n  ❌ PyPI token not found in .env!")
        print("     Set 'password = <your-pypi-token>' in .env")
        return False

    if username != "__token__":
        print(f"\n  ⚠️  Using username: {username}")
    else:
        print("\n  Using PyPI token authentication")

    os.chdir(BASE_DIR)
    dist_dir = BASE_DIR / "dist"

    # Wheels only - never upload the .tar.gz sdist, it still contains
    # plain .py source (see build_distribution()'s --wheel comment).
    dist_files = list(dist_dir.glob("*.whl"))
    stray_sdists = list(dist_dir.glob("*.tar.gz"))
    if stray_sdists:
        print(f"\n  ⚠️  Ignoring sdist(s) in {dist_dir} (would leak source): "
              + ", ".join(f.name for f in stray_sdists))

    if not dist_files:
        print(f"\n  ❌ No wheel files found in {dist_dir}!")
        return False

    print(f"\n  Files to upload:")
    for f in dist_files:
        print(f"    • {f.name}")

    cmd = [
        sys.executable, "-m", "twine", "upload",
        f"--username={username}",
        f"--password={password}",
        "--non-interactive",
        "--skip-existing",  # Skip if version already exists
    ]

    if dry_run:
        print("\n  🔍 Running in DRY-RUN mode (no actual upload)...")
        cmd.append("--repository-url=https://test.pypi.org/legacy/")
        print("     Uploading to test.pypi.org instead of pypi.org")
    else:
        print("\n  🚀 Publishing to PyPI...")

    # Add actual files, not directory
    cmd.extend([str(f) for f in dist_files])

    # Mask password in output
    masked_cmd = [
        c.replace(password, "***HIDDEN***") if password in c else c
        for c in cmd
    ]
    print(f"\n  Command: {' '.join(masked_cmd)}\n")

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n  ✅ Published successfully!")
        if not dry_run:
            print(f"     Package: ALIRA-ai-assistant")
            print(f"     URL: https://pypi.org/project/ALIRA-ai-assistant/")
        return True
    else:
        print("\n  ❌ Publishing failed!")
        return False

def main():
    """Main execution."""
    print("\n" + "=" * 62)
    print("  ALIRA AI Assistant — PyPI Publisher")
    print("=" * 62)

    # Parse arguments
    dry_run = "--dry-run" in sys.argv
    build_only = "--build-only" in sys.argv

    if dry_run:
        print("  Mode: DRY-RUN (test upload to test.pypi.org)")
    elif build_only:
        print("  Mode: BUILD ONLY (no publishing)")
    else:
        print("  Mode: FULL (build + publish to pypi.org)")

    # Step 1: Check requirements
    check_requirements()

    # Step 2: Build distributions
    if not build_distribution():
        print("\n  Aborting due to build failure.")
        return 1

    # Step 3: Publish (if not build-only)
    if not build_only:
        if not publish_to_pypi(dry_run=dry_run):
            print("\n  Publishing failed, but build artifacts are ready in ./dist/")
            return 1

    print("\n" + "=" * 62)
    print("  ✅ ALL DONE!")
    print("=" * 62)
    return 0

if __name__ == "__main__":
    sys.exit(main())
