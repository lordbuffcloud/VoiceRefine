# Changelog

All notable changes to VoiceRefine are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [2.2.0] - 2026-05-16

The "awesomer + UI rewrite" release. Named presets, vault writes, local
Whisper, MCP power-up, and a top-to-bottom UI redesign on customtkinter.

### Added

- **Named polish presets.** Each preset has its own GPT system prompt and
  can be bound to its own hotkey chord. Built-ins: `default`, `code`,
  `email`, `summary`. Add / rename / delete presets in Settings → Polish.
- **Multi-hotkey routing.** Hold different chords to trigger different
  presets. Default bindings: `Win+Alt` → default, `Win+Alt+C` → code,
  `Win+Alt+E` → email, `Win+Alt+S` → summary. Longest chord wins;
  80 ms commit delay disambiguates supersets.
- **Press-to-bind hotkey capture.** Settings → Hotkeys now uses a chord
  capture widget (click, press the keys you want, release). Esc clears.
- **Optional vault writes.** Settings → Vault enables capture writes to
  any Obsidian vault under `11-Data/<category>/YYYY/MM/<id>.json + .md`,
  matching the PersonalData intake schema. Includes append-only
  `11-Data/_index.jsonl` for fast indexing.
- **Local Whisper backend (opt-in).** Settings → Backend chooses `openai`
  (default), `local` (faster-whisper on this PC), or `auto` (try local,
  fall back to OpenAI). Install with `pip install faster-whisper`.
- **MCP power-up.** New tools: `voice_replay_last`, `voice_history_search`,
  `voice_list_presets`, `voice_polish_to_vault`. Existing tools now accept
  an optional `preset` argument and write to the vault when enabled.
- **First-run onboarding wizard.** Five-step setup (Welcome → API Key with
  live validation → Microphone with 3 s live waveform test → Hotkey
  press-to-bind → Done). Replaces the bare key-paste field.
- **Sidebar Settings.** Seven sections (General / Polish / Hotkeys / Audio
  / Vault / Backend / About) replace the old notebook tabs.
- **Richer tray menu.** Last capture preview, pause/resume hotkeys,
  today's stats (`N captures · M words`). Menu refreshes automatically.
- **Pause hotkeys.** Mute hotkeys without quitting via the tray menu;
  paused state has its own tray icon color.

### Changed

- **Floating overlay redesigned.** Pill-style chip with a 14-bar
  phase-shifted live waveform, state-aware glyph (filled dot / arc /
  check / X), and bolder typography. Bottom-center is now the default
  position.
- **CustomTkinter** is the new UI base for the wizard, settings, and
  reusable widgets. Raw Tk paths kept as fallback.
- **README MCP section** rewritten for the Claude Code CLI (`claude mcp
  add` / `.mcp.json`). The old `~/.claude/claude_desktop_config.json`
  reference (Anthropic Desktop, not Claude Code) was removed.
- **PyInstaller spec** declares the new modules in `hiddenimports` and
  excludes `faster_whisper` / `ctranslate2` from the bundle so the exe
  stays small.

### Fixed

- pystray menu construction: factory callables now live on individual
  `MenuItem.text` fields rather than being passed as the whole `menu`
  argument.
- `WaveformBars` and `StepIndicator` no longer crash when the master
  widget is a plain `tk.Frame` (defensive `cget` resolution).

### Configuration

The config file `config.json` now carries new keys. Old configs migrate
on first launch — any existing custom prompt becomes your `default`
preset, and any custom hotkey is rebound to that preset.

New keys:

```
presets               object   { name -> system prompt }
preset_hotkeys        object   { hotkey -> preset name }
active_preset         string   default preset name
transcription_backend string   "openai" | "auto" | "local"
local_model_size      string   "tiny" | "base" | "small" | "medium" | "large-v3"
vault_enabled         bool     write each capture to a vault
vault_path            string   absolute path to vault root
vault_category        string   subfolder under 11-Data/
```

## [2.1.1] - 2026-05-05

### Fixed

- Handle missing microphone devices with a visible error instead of a
  silently-dropped hotkey event.

## [2.1.0] - 2026-04-26

### Changed

- Polished first-run setup window and branded UI.

## [2.0.0] - 2026-04-15

### Added

- Initial public release. Hold-to-record hotkey, Whisper transcription,
  GPT polish, clipboard delivery, system tray, floating overlay, history
  viewer, MCP server (3 tools), WebSocket stream mode, dark/light themes.

[2.2.0]: https://github.com/lordbuffcloud/VoiceRefine/releases/tag/v2.2.0
[2.1.1]: https://github.com/lordbuffcloud/VoiceRefine/releases/tag/v2.1.1
[2.1.0]: https://github.com/lordbuffcloud/VoiceRefine/releases/tag/v2.1.0
[2.0.0]: https://github.com/lordbuffcloud/VoiceRefine/releases/tag/v2.0.0
