"""Check for and apply fast-forward updates from the Brahma Sol GitHub repository."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional


REMOTE = "https://github.com/titechprabhasolutions/Brahma-sol.git"
BRANCH = "main"
GITHUB_API_RELEASES = "https://api.github.com/repos/titechprabhasolutions/Brahma-sol/releases/latest"
CURRENT_VERSION = "2.4.1"


def _parse_version(v_str: str) -> tuple[int, ...]:
    """Parse a version string like 'v2.4.1' or '2.4.0' into a comparable tuple."""
    nums = re.findall(r"\d+", v_str or "")
    return tuple(int(n) for n in nums) if nums else (0, 0, 0)


def check_github_release(current_ver: str = CURRENT_VERSION) -> Optional[Dict[str, Any]]:
    """
    Query the official GitHub Releases API for newer Brahma Sol releases.
    Returns release info dictionary if a newer version is found, or None.
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_RELEASES,
            headers={
                "User-Agent": f"BrahmaSol-App/{current_ver}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))

        latest_tag = data.get("tag_name", "")
        if not latest_tag:
            return None

        latest_tuple = _parse_version(latest_tag)
        current_tuple = _parse_version(current_ver)

        if latest_tuple > current_tuple:
            # Extract download URL from assets if present
            download_url = data.get("html_url", "")
            assets = data.get("assets", [])
            for asset in assets:
                name = asset.get("name", "").lower()
                if name.endswith(".exe") or "installer" in name or "setup" in name:
                    download_url = asset.get("browser_download_url", download_url)
                    break

            return {
                "tag": latest_tag,
                "name": data.get("name", latest_tag),
                "published_at": data.get("published_at"),
                "body": data.get("body", ""),
                "html_url": data.get("html_url"),
                "download_url": download_url,
            }
    except Exception:
        pass
    return None


def _run_git(base_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=base_dir,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def update_from_github(base_dir: Path) -> bool:
    """Update a clean Git checkout and return whether the app should restart."""
    if os.environ.get("BRAHMA_SKIP_UPDATE") == "1":
        return False

    if not (base_dir / ".git").exists():
        return False

    status = _run_git(base_dir, "status", "--porcelain")
    if status.returncode != 0 or status.stdout.strip():
        return False

    remote = _run_git(base_dir, "remote", "get-url", "origin")
    if remote.returncode != 0 or not remote.stdout.strip():
        _run_git(base_dir, "remote", "add", "origin", REMOTE)
    elif "Brahma-sol" not in remote.stdout:
        _run_git(base_dir, "remote", "set-url", "origin", REMOTE)

    fetch = _run_git(base_dir, "fetch", "origin", BRANCH, "--quiet")
    if fetch.returncode != 0:
        return False

    local = _run_git(base_dir, "rev-parse", "HEAD")
    upstream = _run_git(base_dir, "rev-parse", f"origin/{BRANCH}")
    if local.returncode != 0 or upstream.returncode != 0:
        return False
    if local.stdout.strip() == upstream.stdout.strip():
        return False

    ancestor = _run_git(base_dir, "merge-base", "--is-ancestor", "HEAD", f"origin/{BRANCH}")
    if ancestor.returncode != 0:
        return False

    pull = _run_git(base_dir, "pull", "--ff-only", "origin", BRANCH)
    if pull.returncode != 0:
        return False
    return True


def restart_application(base_dir: Path) -> None:
    """Replace the current process with the updated application."""
    if getattr(sys, "frozen", False):
        # Packaged standalone executable
        os.execv(sys.executable, [sys.executable, *sys.argv[1:]])
    else:
        # Development Python script
        os.execv(sys.executable, [sys.executable, str(base_dir / "main.py"), *sys.argv[1:]])
