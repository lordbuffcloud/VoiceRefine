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

from voicerefine import AudioRecorder, VoiceProcessor, load_config, DEFAULT_CONFIG

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

server = Server("voicerefine")
config = load_config()

def get_processor():
    return VoiceProcessor(config)

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="voice_capture",
            description="Record audio for N seconds, transcribe with Whisper, polish with GPT. Returns polished text.",
            inputSchema={
                "type": "object",
                "properties": {
                    "seconds": {"type": "integer", "default": 8, "description": "Recording duration in seconds"}
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
                    "rms_threshold": {"type": "integer", "default": 350, "description": "RMS level below which counts as silence"}
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
                    "prompt_override": {"type": "string", "description": "Optional custom system prompt"}
                },
                "required": ["raw"]
            }
        ),
    ]

@server.call_tool()
async def call_tool(name, arguments):
    processor = get_processor()

    if name == "voice_capture":
        seconds = arguments.get("seconds", 8)
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
        polished = processor.improve(raw)
        return [TextContent(type="text", text=polished)]

    elif name == "voice_capture_until_silence":
        max_seconds = arguments.get("max_seconds", 60)
        silence_ms = arguments.get("silence_ms", 1500)
        rms_threshold = arguments.get("rms_threshold", 350)

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
        polished = processor.improve(raw)
        return [TextContent(type="text", text=polished)]

    elif name == "voice_polish_text":
        raw = arguments.get("raw", "")
        prompt_override = arguments.get("prompt_override")
        if prompt_override:
            old_prompt = config.get("prompt")
            config["prompt"] = prompt_override
            result = processor.improve(raw)
            config["prompt"] = old_prompt
        else:
            result = processor.improve(raw)
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
