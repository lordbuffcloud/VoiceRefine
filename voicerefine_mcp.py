#!/usr/bin/env python3
"""VoiceRefine MCP Server - exposes voice capture and polish as MCP tools."""
import sys
import os
import time
import json
import asyncio
import numpy as np

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voicerefine import AudioRecorder, VoiceProcessor, load_config, DEFAULT_CONFIG, load_history

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

server = Server("voicerefine")
config = load_config()


def _maybe_write_vault(raw, polished, duration, preset):
    """Best-effort vault write if enabled in config. Returns capture id or None."""
    if not config.get("vault_enabled") or not config.get("vault_path"):
        return None
    try:
        from voicerefine_vault import write_capture
        return write_capture(
            config["vault_path"],
            config.get("vault_category", "voice-captures"),
            raw_text=raw or "",
            improved_text=polished or "",
            duration_seconds=duration or 0,
            model=config.get("model", "gpt-4o-mini"),
            preset_name=preset or "default",
            hotkey="mcp",
        )
    except Exception as e:
        print(f"[mcp] vault write failed: {e}", file=sys.stderr)
        return None


def _resolve_preset(name):
    """Return the prompt string for a preset, or None if unknown."""
    if not name:
        return None
    return (config.get("presets") or {}).get(name)

def get_processor():
    return VoiceProcessor(config)

@server.list_tools()
async def list_tools():
    preset_names = sorted((config.get("presets") or {"default": ""}).keys())
    preset_doc = ", ".join(preset_names) if preset_names else "default"
    return [
        Tool(
            name="voice_capture",
            description="Record audio for N seconds, transcribe with Whisper, polish with GPT. Returns polished text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "seconds": {"type": "integer", "default": 8, "description": "Recording duration in seconds"},
                    "preset": {"type": "string", "description": f"Preset to polish with. Available: {preset_doc}. Default: 'default'."}
                }
            }
        ),
        Tool(
            name="voice_capture_until_silence",
            description="Record until silence detected, transcribe and polish. Returns polished text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_seconds": {"type": "integer", "default": 60},
                    "silence_ms": {"type": "integer", "default": 1500, "description": "Silence duration to trigger stop (ms)"},
                    "rms_threshold": {"type": "integer", "default": 350, "description": "RMS level below which counts as silence"},
                    "preset": {"type": "string", "description": f"Preset to polish with. Available: {preset_doc}."}
                }
            }
        ),
        Tool(
            name="voice_polish_text",
            description="Polish raw text through the configured GPT prompt. No recording, no mic access.",
            inputSchema={
                "type": "object",
                "properties": {
                    "raw": {"type": "string", "description": "Raw text to polish"},
                    "prompt_override": {"type": "string", "description": "Optional custom system prompt (wins over preset)"},
                    "preset": {"type": "string", "description": f"Preset name to use. Available: {preset_doc}."}
                },
                "required": ["raw"]
            }
        ),
        Tool(
            name="voice_replay_last",
            description="Return the most recent captured transcription (raw + polished) from local history.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="voice_history_search",
            description="Search local capture history (raw + polished text). Case-insensitive substring match. Returns up to N matches.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Substring to search for"},
                    "limit": {"type": "integer", "default": 10},
                    "field": {"type": "string", "description": "Which field to search: 'raw', 'improved', or 'both' (default)"}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="voice_list_presets",
            description="List configured polish presets and their bound hotkeys.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="voice_polish_to_vault",
            description="Polish raw text and (if vault enabled) write the result to the configured Obsidian vault under 11-Data/. Returns the capture id and polished text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "raw": {"type": "string"},
                    "preset": {"type": "string", "description": f"Preset to polish with. Available: {preset_doc}."}
                },
                "required": ["raw"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name, arguments):
    arguments = arguments or {}

    if name == "voice_list_presets":
        presets = config.get("presets") or {}
        hotkeys = config.get("preset_hotkeys") or {}
        preset_to_hotkey = {p: hk for hk, p in hotkeys.items()}
        lines = ["Configured presets:"]
        for p in sorted(presets.keys()):
            hk = preset_to_hotkey.get(p, "(unbound)")
            lines.append(f"  - {p}: hotkey={hk}")
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "voice_replay_last":
        hist = load_history()
        if not hist:
            return [TextContent(type="text", text="History is empty.")]
        last = hist[-1]
        out = {
            "timestamp": last.get("timestamp", ""),
            "preset": last.get("preset", "default"),
            "raw": last.get("raw", ""),
            "improved": last.get("improved", ""),
            "duration": last.get("duration", 0),
            "model": last.get("model", ""),
        }
        return [TextContent(type="text", text=json.dumps(out, indent=2, ensure_ascii=False))]

    if name == "voice_history_search":
        q = (arguments.get("query") or "").strip().lower()
        if not q:
            return [TextContent(type="text", text="Empty query.")]
        limit = max(1, int(arguments.get("limit", 10)))
        field = (arguments.get("field") or "both").lower()
        hist = load_history()
        matches = []
        for entry in reversed(hist):
            raw = (entry.get("raw") or "").lower()
            imp = (entry.get("improved") or "").lower()
            hit = (field == "raw" and q in raw) or (field == "improved" and q in imp) or (field == "both" and (q in raw or q in imp))
            if hit:
                matches.append({
                    "timestamp": entry.get("timestamp", ""),
                    "preset": entry.get("preset", "default"),
                    "improved": entry.get("improved", ""),
                    "raw": entry.get("raw", ""),
                })
                if len(matches) >= limit:
                    break
        if not matches:
            return [TextContent(type="text", text=f"No matches for: {q}")]
        return [TextContent(type="text", text=json.dumps(matches, indent=2, ensure_ascii=False))]

    if name == "voice_polish_to_vault":
        raw = arguments.get("raw", "")
        preset = arguments.get("preset") or "default"
        if not raw.strip():
            return [TextContent(type="text", text="raw text is empty.")]
        processor = get_processor()
        polished = processor.improve(raw, preset_name=preset)
        cap_id = _maybe_write_vault(raw, polished, 0, preset)
        out = {"polished": polished, "vault_id": cap_id, "preset": preset}
        return [TextContent(type="text", text=json.dumps(out, indent=2, ensure_ascii=False))]

    processor = get_processor()

    if name == "voice_capture":
        seconds = arguments.get("seconds", 8)
        preset = arguments.get("preset") or "default"
        recorder = AudioRecorder(config.get("sample_rate", 16000))
        recorder.start()
        await asyncio.sleep(seconds)
        audio = recorder.stop()
        if audio is None or len(audio) < 1600:
            return [TextContent(type="text", text="Recording too short, no audio captured.")]
        wav = recorder.to_wav_bytes(audio)
        raw = processor.transcribe(wav)
        if not raw:
            return [TextContent(type="text", text="No speech detected.")]
        polished = processor.improve(raw, preset_name=preset)
        duration = len(audio) / config.get("sample_rate", 16000)
        _maybe_write_vault(raw, polished, duration, preset)
        return [TextContent(type="text", text=polished)]

    elif name == "voice_capture_until_silence":
        max_seconds = arguments.get("max_seconds", 60)
        silence_ms = arguments.get("silence_ms", 1500)
        rms_threshold = arguments.get("rms_threshold", 350)
        preset = arguments.get("preset") or "default"

        recorder = AudioRecorder(config.get("sample_rate", 16000))
        recorder.start()
        silence_start = None
        start_time = time.time()

        while time.time() - start_time < max_seconds:
            await asyncio.sleep(0.1)
            if recorder.frames:
                last = recorder.frames[-1]
                rms = float(np.sqrt(np.mean(last.astype(float) ** 2)))
                if rms < rms_threshold:
                    if silence_start is None:
                        silence_start = time.time()
                    elif (time.time() - silence_start) * 1000 >= silence_ms:
                        break
                else:
                    silence_start = None

        audio = recorder.stop()
        if audio is None or len(audio) < 1600:
            return [TextContent(type="text", text="Recording too short.")]
        wav = recorder.to_wav_bytes(audio)
        raw = processor.transcribe(wav)
        if not raw:
            return [TextContent(type="text", text="No speech detected.")]
        polished = processor.improve(raw, preset_name=preset)
        duration = len(audio) / config.get("sample_rate", 16000)
        _maybe_write_vault(raw, polished, duration, preset)
        return [TextContent(type="text", text=polished)]

    elif name == "voice_polish_text":
        raw = arguments.get("raw", "")
        prompt_override = arguments.get("prompt_override")
        preset = arguments.get("preset")
        if prompt_override:
            result = processor.improve(raw, prompt_override=prompt_override)
        elif preset:
            result = processor.improve(raw, preset_name=preset)
        else:
            result = processor.improve(raw)
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
