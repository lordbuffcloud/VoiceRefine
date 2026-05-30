import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voicerefine_update import _best_windows_asset, is_newer_version


def test_version_compare_handles_v_prefixed_tags():
    assert is_newer_version("v2.3.0", "2.2.1")
    assert not is_newer_version("v2.2.1", "2.2.1")
    assert not is_newer_version("v2.1.9", "2.2.1")


def test_best_windows_asset_prefers_voicerefine_x64_exe():
    assets = [
        {"name": "source.zip", "browser_download_url": "https://example/source.zip"},
        {"name": "VoiceRefine-windows-x64.zip", "browser_download_url": "https://example/app.zip"},
        {"name": "VoiceRefine-windows-x64.exe", "browser_download_url": "https://example/app.exe"},
    ]

    asset = _best_windows_asset(assets)

    assert asset is not None
    assert asset["name"] == "VoiceRefine-windows-x64.exe"
