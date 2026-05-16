#!/usr/bin/env python3
"""VoiceRefine vault writer - persists captures to an Obsidian vault under 11-Data/<category>/YYYY/MM/.

Matches the existing PersonalData intake schema:
  - id: YYYYMMDD-HHMMSS-<6char>
  - JSON sidecar with id, category, source, created_at, cleaned_text, features, etc.
  - Markdown note with YAML frontmatter
  - Append-only _index.jsonl at the vault data root
"""
import json
import os
import random
import string
from datetime import datetime, timezone
from pathlib import Path


def _gen_id(now=None):
    now = now or datetime.now(timezone.utc).astimezone()
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{rand}", now


def _safe_category(cat):
    safe = "".join(c for c in (cat or "voice-captures") if c.isalnum() or c in "-_")
    return safe or "voice-captures"


def write_capture(vault_root, category, *, raw_text, improved_text,
                  duration_seconds, model, preset_name, hotkey=None):
    """Write a capture into the vault. Returns the capture id, or None on failure.

    vault_root: path to the vault root (the folder containing 11-Data/).
    category: subfolder name under 11-Data/ (e.g. 'voice-captures').
    """
    if not vault_root:
        return None
    root = Path(vault_root)
    if not root.exists():
        raise FileNotFoundError(f"Vault root does not exist: {root}")

    cap_id, now = _gen_id()
    cat = _safe_category(category)
    data_dir = root / "11-Data" / cat / now.strftime("%Y") / now.strftime("%m")
    data_dir.mkdir(parents=True, exist_ok=True)

    iso = now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    record = {
        "id": cap_id,
        "category": cat,
        "source": "voice",
        "source_hint": "voicerefine",
        "created_at": iso,
        "tags": [f"preset:{preset_name}"] if preset_name else [],
        "summary": (improved_text[:140] + ("..." if len(improved_text) > 140 else "")) if improved_text else "",
        "features": {
            "people": [],
            "places": [],
            "dates": [],
            "numbers": [],
            "sentiment": "neutral",
        },
        "cleaned_text": improved_text or "",
        "confidence": 1.0,
        "model_used": model or "",
        "attachment_path": None,
        "note": None,
        "raw_length": len(raw_text or ""),
        # VoiceRefine-specific extension fields
        "voicerefine": {
            "raw": raw_text or "",
            "duration_seconds": round(float(duration_seconds or 0), 2),
            "preset": preset_name or "default",
            "hotkey": hotkey or "",
        },
    }

    json_path = data_dir / f"{cap_id}.json"
    md_path = data_dir / f"{cap_id}.md"

    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    fm_lines = [
        "---",
        "type: voice-capture",
        f"id: {cap_id}",
        f"created: {iso}",
        f"category: {cat}",
        f"preset: {preset_name or 'default'}",
        f"model: {model or ''}",
        f"duration_seconds: {round(float(duration_seconds or 0), 2)}",
        "source: voicerefine",
        f"tags: [voice-capture, preset-{preset_name or 'default'}]",
        "---",
        "",
        f"# Voice Capture {cap_id}",
        "",
        "## Polished",
        "",
        improved_text or "_(no text)_",
        "",
        "## Raw transcription",
        "",
        raw_text or "_(no transcription)_",
        "",
    ]
    md_path.write_text("\n".join(fm_lines), encoding="utf-8")

    index_path = root / "11-Data" / "_index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with open(index_path, "a", encoding="utf-8") as fp:
        fp.write(json.dumps({
            "id": cap_id,
            "category": cat,
            "created_at": iso,
            "source": "voicerefine",
            "preset": preset_name or "default",
            "summary": record["summary"],
            "path": str(json_path.relative_to(root)).replace(os.sep, "/"),
        }) + "\n")

    return cap_id


def list_recent_captures(vault_root, category=None, limit=20):
    """Return the most recent voice captures by reading the index tail."""
    if not vault_root:
        return []
    root = Path(vault_root)
    index_path = root / "11-Data" / "_index.jsonl"
    if not index_path.exists():
        return []
    try:
        with open(index_path, "r", encoding="utf-8") as fp:
            lines = fp.readlines()
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            rec = json.loads(line.strip())
        except json.JSONDecodeError:
            continue
        if rec.get("source") != "voicerefine":
            continue
        if category and rec.get("category") != category:
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return out
