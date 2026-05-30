#!/usr/bin/env python3
"""Small GitHub Releases updater for the packaged VoiceRefine Windows app.

No third-party dependencies. Source checkouts can check for updates, but only a
frozen Windows executable can self-install by replacing the current .exe.
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RELEASE_API_URL = "https://api.github.com/repos/lordbuffcloud/VoiceRefine/releases/latest"
RELEASES_URL = "https://github.com/lordbuffcloud/VoiceRefine/releases/latest"
USER_AGENT = "VoiceRefine-updater"


def _version_parts(value: str) -> tuple[int, ...]:
    """Return numeric version parts from tags like v2.3.1 or 2.3.1-beta."""
    parts = re.findall(r"\d+", value or "")
    return tuple(int(p) for p in parts[:4]) or (0,)


def is_newer_version(latest: str, current: str) -> bool:
    return _version_parts(latest) > _version_parts(current)


def _request_json(url: str, timeout: int = 12) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _best_windows_asset(assets: list[dict]) -> dict | None:
    candidates = []
    for asset in assets or []:
        name = (asset.get("name") or "").lower()
        url = asset.get("browser_download_url")
        if not url:
            continue
        if not (name.endswith(".exe") or name.endswith(".zip")):
            continue
        score = 0
        if "voicerefine" in name:
            score += 10
        if "windows" in name or "win" in name:
            score += 4
        if "x64" in name or "amd64" in name:
            score += 2
        if name.endswith(".exe"):
            score += 3
        candidates.append((score, asset))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def check_for_update(current_version: str, timeout: int = 12) -> dict:
    """Return update metadata. Raises for network/API failures."""
    release = _request_json(RELEASE_API_URL, timeout=timeout)
    tag = release.get("tag_name") or release.get("name") or ""
    asset = _best_windows_asset(release.get("assets") or [])
    return {
        "current_version": current_version,
        "latest_version": tag.lstrip("v") or tag,
        "tag_name": tag,
        "update_available": is_newer_version(tag, current_version),
        "release_url": release.get("html_url") or RELEASES_URL,
        "asset_name": asset.get("name") if asset else None,
        "asset_url": asset.get("browser_download_url") if asset else None,
        "published_at": release.get("published_at"),
        "body": release.get("body") or "",
    }


def can_self_install() -> bool:
    return bool(getattr(sys, "frozen", False) and platform.system().lower() == "windows")


def download_asset(asset_url: str, dest_dir: str | Path | None = None, timeout: int = 60) -> Path:
    if not asset_url:
        raise ValueError("No release asset URL was provided.")
    dest_dir = Path(dest_dir or tempfile.gettempdir())
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = asset_url.rsplit("/", 1)[-1].split("?", 1)[0] or "VoiceRefine-update.exe"
    dest = dest_dir / name
    req = urllib.request.Request(asset_url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)
    return dest


def _write_windows_replace_script(downloaded: Path, target_exe: Path) -> Path:
    bat = Path(tempfile.gettempdir()) / f"voicerefine-update-{int(time.time())}.bat"
    log = Path(tempfile.gettempdir()) / "voicerefine-update.log"
    script = f"""@echo off
setlocal
set "SRC={downloaded}"
set "DST={target_exe}"
set "LOG={log}"
echo VoiceRefine update started %date% %time% > "%LOG%"
timeout /t 2 /nobreak >nul
:wait_loop
copy /Y "%SRC%" "%DST%" >> "%LOG%" 2>&1
if errorlevel 1 (
  timeout /t 1 /nobreak >nul
  goto wait_loop
)
start "" "%DST%"
del "%SRC%" >nul 2>&1
del "%~f0" >nul 2>&1
"""
    bat.write_text(script, encoding="utf-8")
    return bat


def install_downloaded_update(downloaded: str | Path) -> Path:
    """Schedule a Windows .exe replacement. Caller should exit the app after this."""
    if not can_self_install():
        raise RuntimeError("Automatic install is only available from the packaged Windows executable.")
    downloaded = Path(downloaded)
    if downloaded.suffix.lower() != ".exe":
        raise RuntimeError("Automatic install requires a direct .exe release asset.")
    target_exe = Path(sys.executable)
    bat = _write_windows_replace_script(downloaded, target_exe)
    subprocess.Popen(["cmd", "/c", "start", "", str(bat)], shell=False)
    return bat


def check_download_and_install(current_version: str) -> dict:
    """Check latest release and schedule install when possible.

    Returns the check metadata with extra keys: downloaded_path, installer_script,
    install_scheduled, or skipped_reason.
    """
    info = check_for_update(current_version)
    if not info.get("update_available"):
        info["install_scheduled"] = False
        info["skipped_reason"] = "already-current"
        return info
    if not info.get("asset_url"):
        info["install_scheduled"] = False
        info["skipped_reason"] = "no-windows-release-asset"
        return info
    if not can_self_install():
        info["install_scheduled"] = False
        info["skipped_reason"] = "not-packaged-windows-exe"
        return info
    if not (info.get("asset_name") or "").lower().endswith(".exe"):
        info["install_scheduled"] = False
        info["skipped_reason"] = "no-direct-exe-release-asset"
        return info
    downloaded = download_asset(info["asset_url"])
    info["downloaded_path"] = str(downloaded)
    installer = install_downloaded_update(downloaded)
    info["installer_script"] = str(installer)
    info["install_scheduled"] = True
    return info
