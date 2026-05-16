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
  <a href="https://ck42x.com/tools/voicerefine">Download</a>
  &nbsp;|&nbsp;
  <a href="https://ck42x.com">CK42X</a>
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
- **Named polish presets.** Bind different prompts to different hotkey chords — `Win+Alt` for default, `Win+Alt+C` for code, `Win+Alt+E` for email, `Win+Alt+S` for summary. Add your own.
- **Whisper transcription.** Audio goes to OpenAI Whisper, or `faster-whisper` running locally on your machine — your choice.
- **GPT polish.** Per-preset system prompt. Cleans grammar, fixes punctuation, preserves your voice.
- **Clipboard delivery.** Polished text lands on the clipboard. Paste anywhere.
- **First-run wizard.** Guided setup — paste key, test mic with live waveform, bind a hotkey by pressing it.
- **Sidebar Settings.** Modern seven-section UI (General / Polish / Hotkeys / Audio / Vault / Backend / About).
- **Rich tray menu.** Live preview of the last capture, pause/resume hotkeys, today's capture count and word count.
- **Floating overlay.** Pill-style chip with animated waveform during recording. Configurable position.
- **History viewer.** Browse, search, and re-copy past transcriptions from the tray menu.
- **Optional vault writes.** Mirror each capture into an Obsidian vault under `11-Data/<category>/YYYY/MM/<id>.json + .md`.
- **MCP server.** Expose voice capture, history search, and vault writes as tools for Claude Code, Gemini CLI, and Codex CLI.
- **WebSocket stream.** Broadcast polished text events to local listeners in real time.
- **Dark and light themes.** CK42X matte-black dark by default.

See [`CHANGELOG.md`](CHANGELOG.md) for what's new in each release.

---

## Installation

**Requirements:** Python 3.10+, an OpenAI API key.

```bash
git clone https://github.com/lordbuffcloud/VoiceRefine.git
cd VoiceRefine
pip install -r requirements.txt
```

**Windows users:** if `sounddevice` fails to install, you may need the Microsoft C++ Build Tools.

On first run VoiceRefine opens a guided setup window. Paste your OpenAI API key once, save, and the app starts cleanly. The key stays local in `config.json`; you can also set `OPENAI_API_KEY` instead.

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

### Microphone troubleshooting

If the hotkey appears to do nothing, first confirm Windows has an enabled recording device. VoiceRefine now shows a visible error when no microphone input device is available instead of silently dropping the hotkey event.

Open **Settings > API > Input device** to select a specific microphone. If the list says no input devices were found, enable or connect a microphone in Windows Sound settings, then reopen VoiceRefine.

### Settings

Open via the tray menu or run:

```bash
python voicerefine.py --settings
```

Tabs: **API** (key, GPT model, Whisper model), **Prompt** (system prompt + presets), **Hotkey**, **Appearance** (overlay, theme).

Settings are saved to `config.json` next to the executable.
The app also links back to [CK42X](https://ck42x.com) from Settings, History, and the tray menu.

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

### Claude Code (CLI)

The recommended way is the `claude mcp add` command. Run from your project directory for project scope, or with `-s user` for user-scope:

```bash
# Project scope (writes to .mcp.json in the project root)
claude mcp add voicerefine python /path/to/voicerefine.py --mcp

# User scope (works in every project)
claude mcp add -s user voicerefine python /path/to/voicerefine.py --mcp
```

Or edit `.mcp.json` in your project root manually:

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

> **Heads up:** `~/.claude/claude_desktop_config.json` is the Anthropic Desktop app's config, **not** Claude Code. Use `claude mcp add` or `.mcp.json` for the Claude Code CLI.

Restart Claude Code. The following tools become available:

| Tool | Description |
|------|-------------|
| `voice_capture` | Record for N seconds, transcribe, polish. Optional `preset` arg. Returns text. |
| `voice_capture_until_silence` | Record until silence detected. Optional `preset`. |
| `voice_polish_text` | Polish existing text. Accepts `prompt_override` or `preset`. No mic. |
| `voice_polish_to_vault` | Polish + write the result to the configured Obsidian vault. |
| `voice_replay_last` | Return the most recent capture (raw + polished) from local history. |
| `voice_history_search` | Substring search across local capture history. |
| `voice_list_presets` | List configured presets and their bound hotkeys. |

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
