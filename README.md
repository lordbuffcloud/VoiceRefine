<p align="center">
  <img src="branding/logo-lockup.svg" alt="VoiceRefine" width="320">
</p>

<p align="center">
  <em>Press to talk. Paste polished.</em>
</p>

<p align="center">
  Hold the hotkey, talk, release. Whisper transcribes. GPT polishes. The result lands on your clipboard.
</p>

<p align="center">
  <a href="https://github.com/CK42X/VoiceRefine/releases">Download</a>
  &nbsp;|&nbsp;
  <a href="#mcp-integration">MCP</a>
  &nbsp;|&nbsp;
  <a href="#websocket-streaming">WebSocket</a>
  &nbsp;|&nbsp;
  <a href="#building-from-source">Build</a>
</p>

---

## Features

- **Hold-to-record hotkey.** Press and hold to capture. Release to process. No clicking.
- **Whisper transcription.** Audio goes to OpenAI Whisper. Accurate across accents and registers.
- **GPT polish.** Configurable system prompt. Cleans grammar, fixes punctuation, preserves your voice.
- **Clipboard delivery.** Polished text lands on the clipboard. Paste anywhere.
- **System tray.** Color-coded tray icon tracks state: recording (red), refining (amber), done (teal).
- **Floating overlay.** Non-intrusive status window. Configurable position and duration.
- **History viewer.** Browse, search, and re-copy past transcriptions from the tray menu.
- **MCP server.** Expose voice capture as tools for Claude Code, Gemini CLI, and Codex CLI.
- **WebSocket stream.** Broadcast polished text events to local listeners in real time.
- **Dark and light themes.** CK42X matte-black dark by default.

---

## Installation

**Requirements:** Python 3.10+, an OpenAI API key.

```bash
git clone https://github.com/CK42X/VoiceRefine.git
cd VoiceRefine
pip install -r requirements.txt
```

**Windows users:** if `sounddevice` fails to install, you may need the Microsoft C++ Build Tools.

On first run you will be prompted to enter your OpenAI API key in the Settings window.

---

## Usage

```bash
python voicerefine.py
```

### Hotkey

Default: `Win + Alt`. Hold to record. Release to process. The tray icon and overlay reflect state in real time.

Change the hotkey in **Settings > Hotkey**. Supported modifiers: `<cmd>`, `<alt>`, `<ctrl>`, `<shift>`. Combine with a letter if needed: `<ctrl>+<alt>+r`.

### System tray

Right-click the tray icon to access Settings, History, and Quit.

Tray icon colors:
| Color | State |
|-------|-------|
| Grey | Ready |
| Red `#e94560` | Recording |
| Amber `#ffb300` | Transcribing / refining |
| Teal `#4ecca3` | Copied to clipboard |

### Settings

Open via the tray menu or run:

```bash
python voicerefine.py --settings
```

Tabs: **API** (key, GPT model, Whisper model), **Prompt** (system prompt + presets), **Hotkey**, **Appearance** (overlay, theme).

Settings are saved to `config.json` next to the executable.

### Flags

| Flag | Behavior |
|------|----------|
| _(none)_ | Standard hotkey mode |
| `--settings` | Open Settings window directly |
| `--history` | Open History window directly |
| `--mcp` | Start as MCP server (stdio) |
| `--stream` | Hotkey mode + WebSocket broadcast |

---

## MCP Integration

Run VoiceRefine as an MCP server to give AI coding tools a `voice_capture` tool. Say what you want - the AI gets polished text without you typing.

### Claude Code

Add to `.claude/mcp.json` in your project, or to `~/.claude/claude_desktop_config.json` for global access:

```json
{
  "mcpServers": {
    "voicerefine": {
      "command": "python",
      "args": ["/path/to/voicerefine.py", "--mcp"]
    }
  }
}
```

Restart Claude Code. The following tools become available:

| Tool | Description |
|------|-------------|
| `voice_capture` | Record for N seconds, transcribe, polish. Returns text. |
| `voice_capture_until_silence` | Record until silence detected, transcribe, polish. |
| `voice_polish_text` | Polish existing text through the configured prompt. No mic. |

### Gemini CLI

Add to your Gemini CLI MCP config (typically `~/.gemini/mcp_config.json`):

```json
{
  "servers": {
    "voicerefine": {
      "command": "python",
      "args": ["/path/to/voicerefine.py", "--mcp"],
      "transport": "stdio"
    }
  }
}
```

### Codex CLI

Add to your Codex CLI config (typically `~/.codex/config.json`):

```json
{
  "mcpServers": {
    "voicerefine": {
      "command": "python",
      "args": ["/path/to/voicerefine.py", "--mcp"],
      "transport": "stdio"
    }
  }
}
```

### Example MCP usage

Once connected, prompt the AI:

```
Use voice_capture to record 10 seconds, then write a function based on what I describe.
```

The tool records, transcribes, and polishes your speech. The AI receives clean text and proceeds.

---

## WebSocket Streaming

Start VoiceRefine in stream mode to broadcast polished text events over a local WebSocket:

```bash
python voicerefine.py --stream
```

Default port: `8765`. Override in `config.json`:

```json
{ "stream_port": 8765 }
```

### Event format

Each recording cycle emits a JSON event:

```json
{
  "type": "polished",
  "text": "The polished text.",
  "raw": "the raw transcription",
  "duration_ms": 4200,
  "timestamp": "2026-04-26T14:30:00"
}
```

### Example consumer

```bash
python examples/stream-consumer.py
```

Or connect from any WebSocket client:

```python
import asyncio, websockets, json

async def listen():
    async with websockets.connect("ws://127.0.0.1:8765") as ws:
        async for msg in ws:
            event = json.loads(msg)
            if event["type"] == "polished":
                print(event["text"])

asyncio.run(listen())
```

---

## Building from Source

Produces a single `VoiceRefine.exe` (Windows) with no Python runtime required.

```bash
pip install pyinstaller
pyinstaller VoiceRefine.spec --clean
```

Output: `dist/VoiceRefine.exe`

The spec file bundles `voicerefine_mcp.py` as a hidden import and excludes heavy ML dependencies (`torch`, `transformers`, etc.) to keep the binary small.

---

## Branding

VoiceRefine is part of the **CK42X** product family. The brand assets live in `branding/`:

| File | Use |
|------|-----|
| `logo-lockup.svg` | Mark + wordmark. Default for headers. |
| `logo-mark.svg` | Standalone hex mark. Favicons, avatars. |
| `logo-wordmark.svg` | Wordmark only. Dense layouts, footers. |
| `app-icon.svg` | 1024px tile. Source for `.ico` / `.icns`. |
| `social-card.svg` | 1200x630 OG/Twitter card. |
| `tokens.css` | CSS variables for web surfaces. |
| `BRAND.md` | Full brand specification. |

Color system: matte black `#0b0b0c`, off-white `#e9e9ea`, CK42X amber `#ffb300`.

---

## License

MIT License. See [LICENSE](LICENSE).

Copyright (c) 2026 CK42X / lordb

---

<p align="center">
  <sub>A <a href="https://github.com/CK42X">CK42X</a> project.</sub>
</p>
