# VoiceRefine Brand Kit

**Family:** CK42X. VoiceRefine inherits the CK42X visual system unchanged. Same matte black, same one accent (amber), same hairline geometry, same operator voice.

**Tagline:** Press to talk. Paste polished.

**One-liner:** Hold the hotkey, talk, release. Whisper transcribes, GPT cleans it up, polished text lands on the clipboard.

---

## TL;DR

- Background `#0b0b0c`. Foreground `#e9e9ea`. One accent: amber `#ffb300`.
- Geist Sans for body. Geist Mono for eyebrows and code. Headings tracked at `-0.02em`.
- Radius 14px. Motion 180ms `cubic-bezier(.2, .8, .2, 1)`. Shadow `0 8px 24px rgba(0, 0, 0, .35)`. No glow.
- Logo: hex container, 3 descending bars, terminal amber dot. Voice in, polished out.
- Operator voice: short, declarative, second-person, no fluff, no em dashes.

---

## Colors

| Token | Hex | Role |
|------|-----|------|
| `--vr-bg` | `#0b0b0c` | matte black, app background |
| `--vr-fg` | `#e9e9ea` | off-white, primary text |
| `--vr-muted` | `#151517` | cards, surfaces |
| `--vr-border` | `#222326` | hairline borders |
| `--vr-subtle` | `#a2a3a8` | secondary text, eyebrows |
| `--vr-accent` | `#ffb300` | CK42X amber, single accent |
| `--vr-accent-ink` | `#0b0b0c` | text/glyph color when sitting on amber |

**Canon:** the accent is `#ffb300`. The legacy VoiceRefine amber `#f5a623` is replaced. Anywhere it still ships, swap it on next theme touch.

### Operational state palette

The one-accent rule applies to **chrome only** (buttons, focus rings, links, marks). Operational states are a separate semantic layer because users need clear feedback during the recording loop.

| Token | Hex | Trigger |
|------|-----|--------|
| `--vr-recording` | `#e94560` | hotkey pressed, audio capturing |
| `--vr-thinking`  | `#ffb300` | uploading, transcribing, polishing |
| `--vr-done`      | `#4ecca3` | text on clipboard, ready to paste |
| `--vr-error`     | `#ff6b6b` | API failure, no-audio, hotkey conflict |

State colors only appear on the live overlay and tray icon. They do not appear in marketing surfaces, docs, or the app's settings chrome.

---

## Typography

**Body:** Geist Sans. Weights 400/500/700/800. Loaded from Google Fonts on web surfaces.

**Mono / eyebrows / code:** Geist Mono. Weight 500. Tracked at `0.08em`, uppercase, used for section labels and metadata strips.

**Headings:** -0.02em tracking, weights 700 to 800. H1 may use the CK42X amber gradient `linear-gradient(135deg, #ffb300 0%, #ff9500 100%)` clipped to text. H2 sits in solid amber with a 2px amber underline.

**Tkinter fallback chain (desktop app):**
```
Geist -> Inter -> Segoe UI (Windows) / SF Pro (macOS) / DejaVu Sans (Linux)
```
Tkinter doesn't auto-load Geist. Either bundle the TTF and register with `tkfont.Font(family="Geist", ...)`, or accept the system fallback for v1. Bundling is post-MVP polish.

---

## Geometry & motion

| Token | Value | Note |
|------|-------|------|
| `--vr-radius` | `14px` | All cards, buttons, surfaces. Identical to CK42X canonical. |
| `--vr-hairline` | `1px` | Borders are always 1px, never 2px outside the logo mark. |
| `--vr-ease` | `cubic-bezier(.2, .8, .2, 1)` | Quick-out curve. |
| `--vr-dur` | `180ms` | Default transition. Keep it snappy. |
| `--vr-shadow-1` | `0 8px 24px rgba(0, 0, 0, .35)` | Soft drop. **No glow.** |

If you find yourself reaching for a glow, reach for a hairline border instead.

---

## Logo system

Four assets ship in this kit:

| File | Use |
|------|-----|
| `logo-mark.svg` | Standalone hex+waveform mark. Favicons, social avatars, in-app chrome. |
| `logo-wordmark.svg` | "VoiceRefine" text only. Footers, dense layouts, anywhere the mark would be too loud. |
| `logo-lockup.svg` | Mark + wordmark, horizontal. Default for headers and READMEs. |
| `app-icon.svg` | Square 1024 tile with safe-area inset. Build target for `.icns` and `.ico`. |

### Concept

A hex container (the CK42X family signal) wraps a 3-bar waveform that descends from rough on the left to a single solid amber dot on the right. Reads as "voice in, polished out". The dot is the polished text dropping onto the clipboard.

### Clear space

Minimum clear space around the mark equals the height of the **terminal dot** (~6px in the 64-grid mark, scale proportionally). Nothing crops or overlaps inside this margin, including text, edges, and other marks.

### Minimum size

| Asset | Minimum |
|------|---------|
| `logo-mark.svg` | 24x24 px. Below that, drop the mark and use a single amber dot. |
| `logo-wordmark.svg` | 80px wide. Below that, switch to the mark. |
| `logo-lockup.svg` | 160px wide. Below that, switch to the mark only. |
| `app-icon.svg` | 32x32 px. Already designed for icon mask sizes. |

### Color rules

The mark renders in amber `#ffb300` over any of the brand surfaces (`#0b0b0c`, `#151517`, `#e9e9ea`). On amber backgrounds, render the mark in `#0b0b0c` ink instead. Never tint, never recolor, never apply a gradient to the mark.

### Anti-patterns

- ❌ Adding a glow filter to the mark "for emphasis". The brand is hairlines, not neon.
- ❌ Recoloring the bars to a rainbow gradient. One accent only.
- ❌ Using the mark on a busy background. Place on a flat brand surface.
- ❌ Confusing the hex motif with HexBee or hivesys. VoiceRefine's hex contains a waveform with a terminal dot. HexBee uses honeycomb fields. If in doubt, use the lockup so the wordmark disambiguates.
- ❌ Reading the mark as a wifi/signal icon. It isn't. The terminal dot is solid and centered, not a chevron.

---

## Voice

Operator voice. Short, declarative, second-person. Functional verbs first.

### Do

- "Hold the hotkey. Talk. Release."
- "Polished text lands on the clipboard."
- "Paste anywhere."
- "API key required. Set it in Settings."

### Don't

- "Effortlessly transform your spoken words..."
- "Unleash the power of AI to..."
- "Seamlessly integrates with your workflow..."
- Any sentence that uses an em dash. Use periods, commas, or rewrite.

### Eyebrows (mono, uppercase, tracked)

Use as section labels above headings:

- `RECORD`, `TRANSCRIBE`, `POLISH`, `PASTE`
- `SETTINGS`, `HOTKEYS`, `HISTORY`, `MODELS`
- `STATUS`, `DIAGNOSTICS`, `LOGS`

---

## Integration: voicerefine.py

Drop-in patch for the `THEMES` dict in `voicerefine.py`. Replaces the legacy amber `#f5a623` with CK42X canon `#ffb300` and aligns the surface palette.

```python
THEMES = {
    "dark": {
        "bg":         "#0b0b0c",  # was #1a1a2e
        "fg":         "#e9e9ea",  # was #e0e0e0
        "accent":     "#ffb300",  # was #f5a623 (CK42X canon)
        "accent2":    "#e94560",  # recording, unchanged
        "success":    "#4ecca3",  # done, unchanged
        "recording":  "#e94560",
        "thinking":   "#ffb300",  # was #f5a623
        "done":       "#4ecca3",
        "error":      "#ff6b6b",
        "panel":      "#151517",  # was #16213e
        "border":     "#222326",  # was #0f3460
        "input_bg":   "#151517",  # was #0f3460
        "input_fg":   "#e9e9ea",  # was #e0e0e0
        "button":     "#ffb300",  # was #f5a623
        "button_fg":  "#0b0b0c",  # was #1a1a2e
        "subtle":     "#a2a3a8",  # NEW: secondary text
    },
    "light": {
        "bg":         "#f5f5f5",
        "fg":         "#1a1a1a",
        "accent":     "#d49100",  # darkened CK42X amber for AA contrast on light
        "accent2":    "#c0392b",
        "success":    "#27ae60",
        "recording":  "#c0392b",
        "thinking":   "#d49100",
        "done":       "#27ae60",
        "error":      "#e74c3c",
        "panel":      "#ffffff",
        "border":     "#e2e2e3",
        "input_bg":   "#ffffff",
        "input_fg":   "#1a1a1a",
        "button":     "#d49100",
        "button_fg":  "#ffffff",
        "subtle":     "#6c6d72",
    },
}
```

Apply when: next time you touch theme code. Don't ship a one-off PR just for this.

---

## Web surface boilerplate

For any web-facing VoiceRefine surface (landing page, docs, marketing):

```html
<link rel="stylesheet" href="/branding/tokens.css">
<style>
  body {
    background: var(--vr-bg);
    color: var(--vr-fg);
    font-family: var(--vr-font-sans);
  }
  h1, h2, h3 { letter-spacing: var(--vr-track-tight); }
</style>
```

Eyebrow + heading pattern:

```html
<p class="vr-eyebrow">Record</p>
<h2>Hold the hotkey. Talk. Release.</h2>
```

---

## File index

| Path | Purpose |
|------|---------|
| `branding/BRAND.md` | This document. Source of truth. |
| `branding/tokens.css` | CSS variables for web surfaces. |
| `branding/logo-mark.svg` | Standalone mark, 64x64 viewBox. |
| `branding/logo-wordmark.svg` | Wordmark only, 360x64 viewBox. |
| `branding/logo-lockup.svg` | Mark + wordmark, 420x64 viewBox. Default. |
| `branding/app-icon.svg` | App icon tile, 1024x1024 viewBox. |
| `branding/social-card.svg` | OG / Twitter card, 1200x630 viewBox. |

Convert SVG to PNG/ICNS/ICO with `rsvg-convert`, ImageMagick, or any platform tool. Keep the SVGs as the source.

### Production export note

The `logo-wordmark.svg`, `logo-lockup.svg`, and `social-card.svg` files use Google Fonts via `@import` for live preview. Most browsers render this fine. Some rasterizers, email clients, and GitHub renders do **not** load remote fonts. For production raster export (PNGs in READMEs, OG cards), convert the `<text>` elements to outlined paths first:

```bash
# with Inkscape
inkscape --export-text-to-path --export-type=png --export-dpi=144 logo-lockup.svg

# or with Resvg
resvg --use-fonts-dir /path/to/Geist logo-lockup.svg out.png
```

Keep the original SVGs with live `<text>` for editing.

---

## Favicon

Use `logo-mark.svg` directly as a favicon. Modern browsers render SVG favicons natively and the mark is built for it (single-color amber on transparent reads well at 16-32px).

```html
<link rel="icon" type="image/svg+xml" href="/branding/logo-mark.svg">
<link rel="icon" type="image/png" sizes="32x32" href="/branding/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/branding/apple-touch-icon.png">
```

To generate the PNG variants:
```bash
rsvg-convert -w 32  branding/logo-mark.svg > branding/favicon-32.png
rsvg-convert -w 180 branding/app-icon.svg  > branding/apple-touch-icon.png
```

---

## Social card (OG / Twitter)

Use `social-card.svg`, 1200x630. Lockup-style layout: mark top-left, eyebrow `CK42X / VOICEREFINE`, wordmark headline, tagline `Press to talk. Paste polished.`

Export to PNG for social platforms:
```bash
rsvg-convert -w 1200 -h 630 branding/social-card.svg > branding/social-card.png
```

Reference in HTML head:
```html
<meta property="og:image" content="https://voicerefine.dev/branding/social-card.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://voicerefine.dev/branding/social-card.png">
```

Customize per release: swap the eyebrow line to `CK42X / RELEASE NOTES`, `CK42X / DOWNLOAD`, etc. Keep the rest of the layout fixed.

---

## README header

Drop-in pattern for the project README. Renders correctly on GitHub.

```markdown
<p align="center">
  <img src="branding/logo-lockup.svg" alt="VoiceRefine" width="320">
</p>

<p align="center">
  <em>Press to talk. Paste polished.</em>
</p>

<p align="center">
  Hold the hotkey, talk, release. Whisper transcribes, GPT polishes, the result lands on your clipboard.
</p>
```

Note: GitHub strips remote `@import` from inline SVG. For READMEs, export the lockup to PNG first or rely on the wordmark falling back to system fonts (still readable, just not Geist).

---

## Monochrome fallback

For surfaces that can't render brand color (legal print, faxed docs, single-ink merch, e-ink screens):

| Surface | Mark fill |
|---------|-----------|
| White or light surface | `#0b0b0c` (ink black, 100%) |
| Dark or ink surface | `#e9e9ea` (off-white, 100%) |
| Single-ink amber | `#ffb300` (already canon) |

Replace the hex stroke and bar/dot fills with the chosen ink. The wordmark splits stay: render `Voice` in the chosen ink, render `Refine` in the chosen ink as well (no second color in monochrome).

---

## Light-mode variant

The mark works on light surfaces unchanged: amber `#ffb300` reads cleanly on `#f5f5f5` or `#ffffff`. The hex stroke contrast against pure white drops slightly, so on white-on-white surfaces increase the stroke width from 2 to 2.5 in the rendered SVG.

Wordmark on light: render `Voice` in `#1a1a1a` (not `#e9e9ea`, which would vanish), keep `Refine` in `#d49100` (the AA-contrast amber from the light THEMES patch above) instead of `#ffb300`.

---

## Change log

- **2026-04-26** v1.0. Initial kit. Inherits CK42X canon (`#ffb300`, `#0b0b0c`, hairline geometry, Geist). Mark concept: hex + 3-bar waveform + terminal amber dot. Tagline: "Press to talk. Paste polished."
