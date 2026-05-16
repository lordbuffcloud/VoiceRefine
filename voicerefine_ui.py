#!/usr/bin/env python3
"""VoiceRefine UI design system.

CK42X aesthetic — matte black, amber accent, soft borders, generous whitespace.
Built on customtkinter for rounded surfaces and modern widget feel.

Public surface:
  - TOKENS         : design tokens (spacing, radii, type, motion)
  - COLORS         : dark/light palettes
  - apply_theme()  : configure CustomTkinter globals
  - Card           : rounded panel container with optional title + subtitle
  - SectionHeader  : H2-style heading inside a Card
  - Hint           : subtle helper text
  - ChordCaptureButton : press-to-bind hotkey widget
  - WaveformBars   : live-RMS bar widget for overlay/wizard
  - StepIndicator  : dots + active highlight for wizards
"""
from __future__ import annotations

import math
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False

try:
    from pynput import keyboard as pyn_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Tokens:
    # Spacing scale (px)
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_5: int = 24
    space_6: int = 32
    space_7: int = 48
    # Radii
    radius_sm: int = 6
    radius_md: int = 10
    radius_lg: int = 16
    radius_pill: int = 999
    # Type sizes
    text_xs: int = 11
    text_sm: int = 12
    text_md: int = 13
    text_lg: int = 15
    text_xl: int = 18
    text_2xl: int = 22
    text_3xl: int = 30
    # Motion (ms)
    motion_fast: int = 120
    motion_base: int = 200
    motion_slow: int = 360


TOKENS = _Tokens()


COLORS = {
    "dark": {
        "bg":         "#0b0b0c",
        "bg_alt":     "#101012",
        "surface":    "#151517",
        "surface_2":  "#1c1c1f",
        "surface_3":  "#23232a",
        "border":     "#2a2b30",
        "border_hi":  "#3a3b42",
        "text":       "#e9e9ea",
        "text_dim":   "#b8b9bf",
        "text_subtle":"#888992",
        "accent":     "#ffb300",
        "accent_hi":  "#ffc233",
        "accent_lo":  "#cc8f00",
        "on_accent":  "#0b0b0c",
        "danger":     "#e94560",
        "warn":       "#ffb300",
        "ok":         "#4ecca3",
        "rec":        "#e94560",
        "thinking":   "#ffb300",
        "done":       "#4ecca3",
        "error":      "#ff6b6b",
    },
    "light": {
        "bg":         "#f5f5f5",
        "bg_alt":     "#ececec",
        "surface":    "#ffffff",
        "surface_2":  "#f4f4f5",
        "surface_3":  "#e7e7ea",
        "border":     "#d8d8dc",
        "border_hi":  "#c0c0c6",
        "text":       "#1a1a1a",
        "text_dim":   "#3f3f46",
        "text_subtle":"#6c6d72",
        "accent":     "#d49100",
        "accent_hi":  "#e3a31a",
        "accent_lo":  "#a06b00",
        "on_accent":  "#ffffff",
        "danger":     "#c0392b",
        "warn":       "#d49100",
        "ok":         "#27ae60",
        "rec":        "#c0392b",
        "thinking":   "#d49100",
        "done":       "#27ae60",
        "error":      "#e74c3c",
    },
}


FONT_FAMILY = "Segoe UI"
FONT_MONO = "Consolas"


def font(size=TOKENS.text_md, weight="normal", family=None):
    return (family or FONT_FAMILY, size, weight)


def apply_theme(theme="dark"):
    """Apply CK42X theme to customtkinter globals. Idempotent."""
    if not HAS_CTK:
        return
    ctk.set_appearance_mode("dark" if theme == "dark" else "light")
    # Use a built-in theme for sane defaults; we override per-widget colors at use-site.
    try:
        ctk.set_default_color_theme("dark-blue")
    except Exception:
        pass


def palette(theme="dark"):
    return COLORS.get(theme, COLORS["dark"])


# ---------------------------------------------------------------------------
# Reusable widgets
# ---------------------------------------------------------------------------
class Card(ctk.CTkFrame if HAS_CTK else tk.Frame):
    """Rounded surface with optional title + subtitle."""

    def __init__(self, master, title: str = "", subtitle: str = "", theme="dark",
                 padding=TOKENS.space_5, **kwargs):
        c = palette(theme)
        if HAS_CTK:
            super().__init__(master, corner_radius=TOKENS.radius_lg,
                             fg_color=c["surface"], border_color=c["border"],
                             border_width=1, **kwargs)
        else:
            super().__init__(master, bg=c["surface"], highlightbackground=c["border"],
                             highlightthickness=1, **kwargs)
        self._theme = theme
        self._c = c
        self._pad = padding
        self._content = self
        if title or subtitle:
            head = ctk.CTkFrame(self, fg_color="transparent") if HAS_CTK else tk.Frame(self, bg=c["surface"])
            head.pack(fill="x", padx=padding, pady=(padding, TOKENS.space_3))
            if title:
                t = ctk.CTkLabel(head, text=title, text_color=c["text"],
                                 font=font(TOKENS.text_xl, "bold"), anchor="w") if HAS_CTK else \
                    tk.Label(head, text=title, fg=c["text"], bg=c["surface"],
                             font=font(TOKENS.text_xl, "bold"), anchor="w")
                t.pack(anchor="w")
            if subtitle:
                s = ctk.CTkLabel(head, text=subtitle, text_color=c["text_subtle"],
                                 font=font(TOKENS.text_sm), anchor="w", wraplength=520, justify="left") if HAS_CTK else \
                    tk.Label(head, text=subtitle, fg=c["text_subtle"], bg=c["surface"],
                             font=font(TOKENS.text_sm), anchor="w", wraplength=520, justify="left")
                s.pack(anchor="w", pady=(TOKENS.space_1, 0))
            self._content = ctk.CTkFrame(self, fg_color="transparent") if HAS_CTK else tk.Frame(self, bg=c["surface"])
            self._content.pack(fill="both", expand=True, padx=padding, pady=(0, padding))

    @property
    def body(self):
        return self._content


class SectionHeader:
    """Helper to add a section header inside any frame."""
    def __init__(self, master, title: str, subtitle: str = "", theme="dark"):
        c = palette(theme)
        bg = master.cget("fg_color") if HAS_CTK else master.cget("bg")
        if isinstance(bg, (list, tuple)):
            bg = bg[1] if ctk.get_appearance_mode() == "Dark" else bg[0]
        wrap = ctk.CTkFrame(master, fg_color="transparent") if HAS_CTK else tk.Frame(master, bg=c["surface"])
        wrap.pack(fill="x", pady=(0, TOKENS.space_3))
        title_lbl = ctk.CTkLabel(wrap, text=title, text_color=c["text"],
                                 font=font(TOKENS.text_lg, "bold"), anchor="w") if HAS_CTK else \
                    tk.Label(wrap, text=title, fg=c["text"], font=font(TOKENS.text_lg, "bold"), anchor="w")
        title_lbl.pack(anchor="w")
        if subtitle:
            sub = ctk.CTkLabel(wrap, text=subtitle, text_color=c["text_subtle"],
                               font=font(TOKENS.text_sm), anchor="w", wraplength=520, justify="left") if HAS_CTK else \
                  tk.Label(wrap, text=subtitle, fg=c["text_subtle"], font=font(TOKENS.text_sm),
                           anchor="w", wraplength=520, justify="left")
            sub.pack(anchor="w", pady=(TOKENS.space_1, 0))
        self.widget = wrap


class Hint:
    """Subtle helper text under a control."""
    def __init__(self, master, text: str, theme="dark", **kwargs):
        c = palette(theme)
        lbl = ctk.CTkLabel(master, text=text, text_color=c["text_subtle"],
                           font=font(TOKENS.text_sm), anchor="w",
                           wraplength=kwargs.pop("wraplength", 540), justify="left") if HAS_CTK else \
              tk.Label(master, text=text, fg=c["text_subtle"], font=font(TOKENS.text_sm),
                       anchor="w", wraplength=kwargs.pop("wraplength", 540), justify="left")
        self.widget = lbl


class ChordCaptureButton(ctk.CTkButton if HAS_CTK else tk.Button):
    """Press-to-bind keychord widget.

    Click → button enters listen mode → user holds modifiers (+ optional letter) → release captures.
    on_capture(chord_str) is invoked with VoiceRefine's hotkey string format, e.g. '<cmd>+<alt>+c'.
    Pass clear=True with no capture to set empty.
    """
    MOD_TO_TOKEN = {}
    if HAS_PYNPUT:
        MOD_TO_TOKEN = {
            pyn_keyboard.Key.alt: "<alt>", pyn_keyboard.Key.alt_l: "<alt>", pyn_keyboard.Key.alt_r: "<alt>",
            pyn_keyboard.Key.ctrl: "<ctrl>", pyn_keyboard.Key.ctrl_l: "<ctrl>", pyn_keyboard.Key.ctrl_r: "<ctrl>",
            pyn_keyboard.Key.cmd: "<cmd>", pyn_keyboard.Key.cmd_l: "<cmd>", pyn_keyboard.Key.cmd_r: "<cmd>",
            pyn_keyboard.Key.shift: "<shift>", pyn_keyboard.Key.shift_l: "<shift>", pyn_keyboard.Key.shift_r: "<shift>",
        }
    ORDER = ["<cmd>", "<ctrl>", "<alt>", "<shift>"]

    def __init__(self, master, initial_chord: str = "", on_capture: Optional[Callable[[str], None]] = None,
                 theme="dark", **kwargs):
        c = palette(theme)
        self._theme = theme
        self._c = c
        self._listening = False
        self._listener = None
        self._captured_mods = set()
        self._captured_char = None
        self._on_capture = on_capture
        self._current = initial_chord or ""
        text = self._render_text(self._current)
        if HAS_CTK:
            super().__init__(master, text=text, command=self._toggle_listen,
                             corner_radius=TOKENS.radius_md,
                             fg_color=c["surface_2"], hover_color=c["surface_3"],
                             border_color=c["border"], border_width=1,
                             text_color=c["text"], font=font(TOKENS.text_md, "bold"),
                             height=36, **kwargs)
        else:
            super().__init__(master, text=text, command=self._toggle_listen, **kwargs)

    def get_chord(self):
        return self._current

    def set_chord(self, chord: str, fire_callback: bool = False):
        self._current = chord or ""
        self.configure(text=self._render_text(self._current))
        if fire_callback and self._on_capture:
            self._on_capture(self._current)

    def _render_text(self, chord: str) -> str:
        if self._listening:
            return "Press keys…  (Esc to clear)"
        if not chord:
            return "Click to bind…"
        return self._chord_display(chord)

    @staticmethod
    def _chord_display(chord: str) -> str:
        if not chord:
            return ""
        parts = [p.strip() for p in chord.split("+") if p.strip()]
        pretty = []
        for p in parts:
            p_low = p.lower()
            mapping = {"<cmd>": "Win", "<ctrl>": "Ctrl", "<alt>": "Alt", "<shift>": "Shift"}
            if p_low in mapping:
                pretty.append(mapping[p_low])
            elif len(p) == 1:
                pretty.append(p.upper())
            else:
                pretty.append(p)
        return "  +  ".join(pretty)

    def _toggle_listen(self):
        if not HAS_PYNPUT:
            return
        if self._listening:
            self._stop_listening(commit=False)
        else:
            self._start_listening()

    def _start_listening(self):
        self._listening = True
        self._captured_mods = set()
        self._captured_char = None
        self.configure(text=self._render_text(""), border_color=self._c["accent"], text_color=self._c["accent"])
        try:
            self._listener = pyn_keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
            self._listener.start()
        except Exception:
            self._listening = False

    def _stop_listening(self, commit=True):
        self._listening = False
        if self._listener:
            try: self._listener.stop()
            except Exception: pass
            self._listener = None
        if commit and (self._captured_mods or self._captured_char):
            tokens = [t for t in self.ORDER if t in self._captured_mods]
            if self._captured_char:
                tokens.append(self._captured_char)
            chord = "+".join(tokens)
            if chord:
                self._current = chord
                if self._on_capture: self._on_capture(chord)
        self.configure(text=self._render_text(self._current),
                       border_color=self._c["border"], text_color=self._c["text"])

    def _on_press(self, key):
        try:
            if key == pyn_keyboard.Key.esc:
                self._current = ""
                self._captured_mods.clear()
                self._captured_char = None
                self.after(0, lambda: self._stop_listening(commit=False))
                self.after(10, lambda: (self.configure(text=self._render_text(""))))
                if self._on_capture:
                    self.after(15, lambda: self._on_capture(""))
                return False
            tok = self.MOD_TO_TOKEN.get(key)
            if tok:
                self._captured_mods.add(tok)
            else:
                ch = getattr(key, "char", None)
                if ch and len(ch) == 1 and ch.isprintable():
                    self._captured_char = ch.lower()
                    # Letter key + at least one mod = commit
                    if self._captured_mods:
                        self.after(0, lambda: self._stop_listening(commit=True))
                        return False
        except Exception:
            pass

    def _on_release(self, key):
        if not self._listening:
            return
        tok = self.MOD_TO_TOKEN.get(key)
        if tok and tok in self._captured_mods and not self._captured_char:
            # Released a modifier without committing a letter — commit modifier-only chord
            self.after(0, lambda: self._stop_listening(commit=True))
            return False


class WaveformBars:
    """Animated bar visualizer for live RMS level. Renders into a host frame."""
    @staticmethod
    def _resolve_master_bg(master, fallback):
        # Try CTk widget first, then tk widget, finally fall back to a known color.
        try:
            fg = master.cget("fg_color")
            if isinstance(fg, (list, tuple)):
                # CTk theme tuple: (light, dark)
                if HAS_CTK:
                    try:
                        return fg[1] if ctk.get_appearance_mode() == "Dark" else fg[0]
                    except Exception:
                        return fg[-1]
                return fg[-1]
            return fg
        except tk.TclError:
            pass
        try:
            return master.cget("bg")
        except Exception:
            return fallback

    def __init__(self, master, theme="dark", bars=12, width=160, height=36, idle_color=None, active_color=None):
        self._c = palette(theme)
        self._bars = bars
        self._w = width
        self._h = height
        self._idle = idle_color or self._c["border"]
        self._active = active_color or self._c["accent"]
        bg = self._resolve_master_bg(master, self._c["surface"])
        self.canvas = tk.Canvas(master, width=width, height=height, bg=bg,
                                highlightthickness=0, bd=0)
        self._rects = []
        gap = 3
        bw = max((width - gap * (bars - 1)) // bars, 2)
        x = 0
        for _ in range(bars):
            r = self.canvas.create_rectangle(x, height - 2, x + bw, height - 2, fill=self._idle, outline="")
            self._rects.append((r, x, bw))
            x += bw + gap
        self._levels = [0.0] * bars
        self._phase = 0.0

    def set_level(self, level: float, state: str = "recording"):
        # 0..1 input, smoothed; produces wavelike heights using last-N memory + phase shift
        level = max(0.0, min(1.0, float(level)))
        self._levels.pop(0)
        self._levels.append(level)
        self._phase += 0.35
        color = {
            "recording": self._c["rec"],
            "thinking":  self._c["thinking"],
            "done":      self._c["done"],
            "error":     self._c["error"],
            "idle":      self._c["border"],
        }.get(state, self._active)
        for i, (r, x, bw) in enumerate(self._rects):
            lv = self._levels[i]
            wave = 0.5 + 0.5 * math.sin(self._phase + i * 0.45)
            blended = (lv * 0.65) + (wave * lv * 0.35)
            h = max(int(blended * (self._h - 4)), 2)
            self.canvas.coords(r, x, self._h - h, x + bw, self._h - 2)
            self.canvas.itemconfigure(r, fill=color if lv > 0.05 else self._idle)


class StepIndicator:
    """Horizontal dots for wizard step progress."""
    def __init__(self, master, steps: int, current: int = 0, theme="dark"):
        c = palette(theme)
        self._c = c
        self._steps = steps
        self._current = current
        self.frame = ctk.CTkFrame(master, fg_color="transparent") if HAS_CTK else tk.Frame(master, bg=c["bg"])
        bg = WaveformBars._resolve_master_bg(master, c["bg"])
        self._dots = []
        for i in range(steps):
            d = tk.Canvas(self.frame, width=14, height=14, bg=bg,
                          highlightthickness=0, bd=0)
            oval = d.create_oval(2, 2, 12, 12, fill=c["border"], outline="")
            d.pack(side="left", padx=4)
            self._dots.append((d, oval))
        self.set_current(current)

    def set_current(self, idx: int):
        self._current = idx
        for i, (d, oval) in enumerate(self._dots):
            if i < idx:
                d.itemconfigure(oval, fill=self._c["accent_lo"])
            elif i == idx:
                d.itemconfigure(oval, fill=self._c["accent"])
            else:
                d.itemconfigure(oval, fill=self._c["border"])
