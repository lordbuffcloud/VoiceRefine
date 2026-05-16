# Security policy

## Reporting a vulnerability

If you discover a security issue in VoiceRefine, please **do not** open a
public GitHub issue. Instead, email the maintainer privately:

- **Contact:** the email listed on https://ck42x.com (or open a private
  GitHub security advisory at
  https://github.com/lordbuffcloud/VoiceRefine/security/advisories/new).

When reporting, include:

- A clear description of the issue and its impact.
- Steps to reproduce, ideally with a minimal repro environment.
- The affected version (see `APP_VERSION` in `voicerefine.py` or run the
  built `VoiceRefine.exe --help` once that flag lands).
- Any proof-of-concept or recordings, if relevant.

You should expect an acknowledgement within **5 business days**. Triaged
fixes ship in a patch release; coordinated disclosure timelines are
agreed case by case.

## Supported versions

Only the latest minor release receives security fixes:

| Version  | Supported |
|----------|-----------|
| 2.2.x    | ✅        |
| < 2.2.0  | ❌        |

## Threat model

VoiceRefine is a single-user desktop tool. The trust boundary is
intentionally simple: **the local user is trusted**; everything else is
not.

What this means in practice:

- **API keys.** The OpenAI API key is stored locally in `config.json`
  next to the executable. The key is never transmitted anywhere except
  to OpenAI's API endpoints over HTTPS. The key is masked in the UI by
  default and never logged.
- **Audio.** Microphone audio is captured locally, uploaded to OpenAI
  for transcription (or processed locally via faster-whisper if
  configured), and discarded after transcription. Audio is not written
  to disk.
- **Transcripts and history.** Polished text is written to
  `history.json` next to the executable. If you enable vault writes,
  captures are also written to the configured vault path. Both are
  local-only.
- **Hotkeys.** Pressed-key events are observed via a global keyboard
  listener (pynput) only while the app is running. Modifier keys and one
  optional letter form a chord; key events outside a configured chord
  are not retained.
- **Network.** Outbound calls go to OpenAI's API only, over TLS. There
  is no telemetry, no analytics, no auto-update.

## Scope

In scope:

- Credential exposure (logging or transmitting the API key, etc.).
- Local privilege escalation through the installed app.
- Code-injection or sandbox escape via crafted input (audio, config,
  history).
- Hotkey hijacking that allows other processes to spy on captures.

Out of scope:

- Risks inherent to running unsigned executables (mitigated by the
  Authenticode-signed releases starting in 2.2.x).
- Vulnerabilities in third-party dependencies that do not have a
  practical impact on VoiceRefine's threat model.
- Social engineering against the user's OpenAI account.

## Hardening recommendations for operators

- Use a dedicated OpenAI API key for VoiceRefine with usage limits.
- If you mirror captures to an Obsidian vault, make sure that vault is
  not synced to a public location.
- On shared machines, prefer the local Whisper backend
  (`pip install faster-whisper`) so audio never leaves the device.

## Credits

Reported issues are credited in the changelog under the version that
ships the fix, unless the reporter requests anonymity.
