#!/usr/bin/env python3
"""VoiceRefine Settings window — sidebar nav, modern CTk surfaces.

Sections: General, Polish, Hotkeys, Audio, Vault, Backend, About.
Save commits all sections at once.
"""
from __future__ import annotations

import os
import threading
import time
import webbrowser
from pathlib import Path

import numpy as np
import sounddevice as sd

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

try:
    import customtkinter as ctk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False
    ctk = None

from voicerefine_ui import (
    TOKENS, palette, font, apply_theme,
    Card, SectionHeader, Hint, ChordCaptureButton, WaveformBars,
)


CK42X_URL = "https://ck42x.com"
OPENAI_KEYS_URL = "https://platform.openai.com/api-keys"

SECTIONS = [
    ("general",  "General"),
    ("polish",   "Polish"),
    ("hotkeys",  "Hotkeys"),
    ("audio",    "Audio"),
    ("vault",    "Vault"),
    ("backend",  "Backend"),
    ("about",    "About"),
]


class SettingsWindow:
    """Modern Settings — call .show(); fires on_save(updated_cfg) on commit."""

    def __init__(self, config: dict, on_save=None, icon_path: Path = None,
                 default_section: str = "general", theme: str = "dark", app_version: str = ""):
        self._cfg = dict(config)
        self._on_save = on_save
        self._icon = icon_path
        self._theme = theme
        self._app_version = app_version
        self._default_section = default_section
        self._c = palette(theme)
        self._presets_state = {k: str(v) for k, v in (config.get("presets") or {}).items()}
        if "default" not in self._presets_state:
            self._presets_state["default"] = config.get("prompt", "")
        self._preset_hotkeys_state = dict(config.get("preset_hotkeys") or {})
        self._editor_dirty_preset = None
        self._section_renderers = {}
        self._panel_widgets = {}
        self._current_section = default_section
        self._nav_buttons = {}
        # Audio test thread
        self._mic_thread = None
        self._mic_stop = threading.Event()
        self._mic_wf = None
        self._mic_status_var = None
        # StringVars (created on render so root exists)

    def show(self):
        if not HAS_CTK:
            return
        apply_theme(self._theme)
        self.root = ctk.CTk()
        self.root.title("VoiceRefine — Settings")
        self.root.geometry("960x640")
        self.root.minsize(880, 600)
        try:
            if self._icon and Path(self._icon).exists():
                self.root.iconbitmap(str(self._icon))
        except Exception:
            pass
        self.root.configure(fg_color=self._c["bg"])
        self._build_layout()
        self._select_section(self._default_section)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())
        self.root.mainloop()

    # --------------------------------------------------------- layout
    def _build_layout(self):
        c = self._c
        # Top brand strip
        top = ctk.CTkFrame(self.root, fg_color="transparent")
        top.pack(fill="x", padx=TOKENS.space_5, pady=(TOKENS.space_4, TOKENS.space_2))
        ctk.CTkLabel(top, text="VoiceRefine", text_color=c["text"],
                     font=font(TOKENS.text_2xl, "bold")).pack(side="left")
        ctk.CTkLabel(top, text="·  settings", text_color=c["text_subtle"],
                     font=font(TOKENS.text_md)).pack(side="left", padx=(TOKENS.space_2, 0))
        ctk.CTkLabel(top, text=f"v{self._app_version}" if self._app_version else "",
                     text_color=c["text_subtle"], font=font(TOKENS.text_sm)).pack(side="right")

        # Main area: sidebar + content
        main = ctk.CTkFrame(self.root, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=TOKENS.space_5, pady=TOKENS.space_2)

        # Sidebar
        side = ctk.CTkFrame(main, fg_color=c["surface"], corner_radius=TOKENS.radius_lg,
                            border_color=c["border"], border_width=1, width=200)
        side.pack(side="left", fill="y", padx=(0, TOKENS.space_4))
        side.pack_propagate(False)
        inner = ctk.CTkFrame(side, fg_color="transparent")
        inner.pack(fill="x", padx=TOKENS.space_2, pady=TOKENS.space_3)
        for key, label in SECTIONS:
            btn = ctk.CTkButton(inner, text=label, height=36, anchor="w",
                                fg_color="transparent",
                                hover_color=c["surface_2"],
                                text_color=c["text_dim"],
                                font=font(TOKENS.text_md),
                                command=lambda k=key: self._select_section(k))
            btn.pack(fill="x", padx=TOKENS.space_2, pady=2)
            self._nav_buttons[key] = btn

        # Content area
        self.content = ctk.CTkScrollableFrame(main, fg_color="transparent",
                                              scrollbar_button_color=c["border"],
                                              scrollbar_button_hover_color=c["border_hi"])
        self.content.pack(side="left", fill="both", expand=True)

        # Bottom action bar
        actions = ctk.CTkFrame(self.root, fg_color="transparent")
        actions.pack(fill="x", padx=TOKENS.space_5, pady=(TOKENS.space_2, TOKENS.space_4))
        ctk.CTkButton(actions, text="ck42x.com", height=36,
                      fg_color="transparent", hover_color=c["surface_2"],
                      text_color=c["text_subtle"], border_width=0,
                      command=lambda: webbrowser.open_new_tab(CK42X_URL)).pack(side="left")
        ctk.CTkButton(actions, text="Cancel", width=110, height=36,
                      fg_color="transparent", hover_color=c["surface_2"],
                      text_color=c["text_dim"], border_width=1, border_color=c["border"],
                      command=self._on_close).pack(side="right", padx=(TOKENS.space_2, 0))
        ctk.CTkButton(actions, text="Save changes", width=140, height=36,
                      fg_color=c["accent"], hover_color=c["accent_hi"],
                      text_color=c["on_accent"], font=font(TOKENS.text_md, "bold"),
                      command=self._save).pack(side="right")

    def _select_section(self, key):
        c = self._c
        self._current_section = key
        # Highlight nav
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(fg_color=c["surface_2"], text_color=c["accent"])
            else:
                btn.configure(fg_color="transparent", text_color=c["text_dim"])
        # Render the section
        for w in self.content.winfo_children():
            w.destroy()
        renderer = {
            "general": self._render_general,
            "polish":  self._render_polish,
            "hotkeys": self._render_hotkeys,
            "audio":   self._render_audio,
            "vault":   self._render_vault,
            "backend": self._render_backend,
            "about":   self._render_about,
        }[key]
        renderer(self.content)

    # --------------------------------------------------------- sections
    def _render_general(self, parent):
        c = self._c
        # API + model
        card = Card(parent, title="OpenAI", subtitle="Required for polish (and for cloud Whisper). Stored locally.",
                    theme=self._theme)
        card.pack(fill="x", pady=(0, TOKENS.space_3))
        b = card.body
        self._api_var = tk.StringVar(value=self._cfg.get("openai_api_key", ""))
        row = ctk.CTkFrame(b, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="API key", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=120, anchor="w").pack(side="left")
        entry = ctk.CTkEntry(row, textvariable=self._api_var, height=36, show="*",
                             fg_color=c["surface_2"], border_color=c["border"], border_width=1,
                             text_color=c["text"], font=font(TOKENS.text_md, family="Consolas"))
        entry.pack(side="left", fill="x", expand=True, padx=(0, TOKENS.space_2))
        show_var = tk.BooleanVar(value=False)
        def toggle():
            show_var.set(not show_var.get())
            entry.configure(show="" if show_var.get() else "*")
            btn.configure(text="Hide" if show_var.get() else "Show")
        btn = ctk.CTkButton(row, text="Show", width=72, height=36,
                            fg_color="transparent", hover_color=c["surface_2"],
                            text_color=c["text_dim"], border_width=1, border_color=c["border"],
                            command=toggle)
        btn.pack(side="left", padx=(0, TOKENS.space_2))
        ctk.CTkButton(row, text="Get key", width=84, height=36,
                      fg_color=c["surface_2"], hover_color=c["surface_3"],
                      text_color=c["text"], border_width=1, border_color=c["border"],
                      command=lambda: webbrowser.open_new_tab(OPENAI_KEYS_URL)).pack(side="left")
        env_key = os.environ.get("OPENAI_API_KEY", "").strip()
        Hint(b, "OPENAI_API_KEY env var is also detected." if env_key else "Or set the OPENAI_API_KEY environment variable.",
             theme=self._theme).widget.pack(anchor="w", pady=(TOKENS.space_1, 0))

        row = ctk.CTkFrame(b, fg_color="transparent"); row.pack(fill="x", pady=(TOKENS.space_3, 0))
        ctk.CTkLabel(row, text="Polish model", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=120, anchor="w").pack(side="left")
        self._model_var = tk.StringVar(value=self._cfg.get("model", "gpt-4o-mini"))
        ctk.CTkOptionMenu(row, variable=self._model_var,
                          values=["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "gpt-4-turbo"],
                          fg_color=c["surface_2"], button_color=c["surface_3"],
                          button_hover_color=c["border_hi"], text_color=c["text"],
                          height=36, width=200, dynamic_resizing=False).pack(side="left")

        # Appearance
        card2 = Card(parent, title="Appearance", theme=self._theme)
        card2.pack(fill="x", pady=(0, TOKENS.space_3))
        b2 = card2.body
        self._theme_var = tk.StringVar(value=self._cfg.get("theme", "dark"))
        row = ctk.CTkFrame(b2, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Theme", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=160, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, variable=self._theme_var, values=["dark", "light"],
                          fg_color=c["surface_2"], button_color=c["surface_3"],
                          button_hover_color=c["border_hi"], text_color=c["text"],
                          height=36, width=160, dynamic_resizing=False).pack(side="left")
        self._overlay_var = tk.BooleanVar(value=self._cfg.get("show_overlay", True))
        ctk.CTkCheckBox(b2, text="Show floating status overlay", variable=self._overlay_var,
                        text_color=c["text"], font=font(TOKENS.text_md),
                        fg_color=c["accent"], hover_color=c["accent_hi"],
                        checkmark_color=c["on_accent"], border_color=c["border"]).pack(anchor="w", pady=TOKENS.space_2)
        row = ctk.CTkFrame(b2, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Overlay position", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=160, anchor="w").pack(side="left")
        self._pos_var = tk.StringVar(value=self._cfg.get("overlay_position", "bottom-right"))
        ctk.CTkOptionMenu(row, variable=self._pos_var,
                          values=["bottom-right", "bottom-left", "bottom-center", "top-right", "top-left", "center"],
                          fg_color=c["surface_2"], button_color=c["surface_3"],
                          button_hover_color=c["border_hi"], text_color=c["text"],
                          height=36, width=200, dynamic_resizing=False).pack(side="left")
        row = ctk.CTkFrame(b2, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Overlay duration (s)", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=160, anchor="w").pack(side="left")
        self._dur_var = tk.IntVar(value=int(self._cfg.get("overlay_duration", 3)))
        ctk.CTkSlider(row, from_=1, to=10, number_of_steps=9, variable=self._dur_var,
                      fg_color=c["surface_3"], progress_color=c["accent"],
                      button_color=c["accent"], button_hover_color=c["accent_hi"], width=240).pack(side="left", padx=(0, TOKENS.space_2))
        ctk.CTkLabel(row, textvariable=self._dur_var, text_color=c["text"], font=font(TOKENS.text_md), width=24).pack(side="left")

        row = ctk.CTkFrame(b2, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Window opacity", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=160, anchor="w").pack(side="left")
        self._opacity_var = tk.DoubleVar(value=float(self._cfg.get("window_opacity", 0.96)))
        ctk.CTkSlider(row, from_=0.86, to=1.0, number_of_steps=14, variable=self._opacity_var,
                      fg_color=c["surface_3"], progress_color=c["accent"],
                      button_color=c["accent"], button_hover_color=c["accent_hi"], width=240).pack(side="left")

    def _render_polish(self, parent):
        c = self._c
        card = Card(parent, title="Polish presets",
                    subtitle="Each preset has its own GPT system prompt. Bind preset hotkeys in the Hotkeys section.",
                    theme=self._theme)
        card.pack(fill="x", pady=(0, TOKENS.space_3))
        b = card.body

        # Active preset picker + add/delete
        top = ctk.CTkFrame(b, fg_color="transparent"); top.pack(fill="x", pady=(0, TOKENS.space_3))
        ctk.CTkLabel(top, text="Editing preset", text_color=c["text_dim"],
                     font=font(TOKENS.text_md), width=140, anchor="w").pack(side="left")
        self._active_preset_var = tk.StringVar(value=self._cfg.get("active_preset", "default"))
        preset_picker = ctk.CTkOptionMenu(top, variable=self._active_preset_var,
                                          values=sorted(self._presets_state.keys()),
                                          fg_color=c["surface_2"], button_color=c["surface_3"],
                                          button_hover_color=c["border_hi"], text_color=c["text"],
                                          height=36, width=220, dynamic_resizing=False,
                                          command=lambda _v: self._switch_preset())
        preset_picker.pack(side="left", padx=(0, TOKENS.space_2))
        self._preset_picker = preset_picker

        def add_preset():
            name = simpledialog.askstring("New preset", "Preset name (letters, numbers, dashes):", parent=self.root)
            if not name: return
            name = "".join(ch for ch in name.strip().lower() if ch.isalnum() or ch == "-")
            if not name or name in self._presets_state: return
            self._stash_editor()
            self._presets_state[name] = self._presets_state.get(self._active_preset_var.get(), "")
            preset_picker.configure(values=sorted(self._presets_state.keys()))
            self._active_preset_var.set(name)
            self._switch_preset()

        def del_preset():
            n = self._active_preset_var.get()
            if n == "default":
                messagebox.showinfo("Can't delete", "The 'default' preset cannot be deleted.")
                return
            if not messagebox.askyesno("Delete preset", f"Delete preset '{n}'?"):
                return
            self._presets_state.pop(n, None)
            for hk in [k for k, v in self._preset_hotkeys_state.items() if v == n]:
                self._preset_hotkeys_state.pop(hk, None)
            preset_picker.configure(values=sorted(self._presets_state.keys()))
            self._active_preset_var.set("default")
            self._switch_preset()

        ctk.CTkButton(top, text="+ New", height=36, width=84,
                      fg_color=c["surface_2"], hover_color=c["surface_3"],
                      text_color=c["text"], border_width=1, border_color=c["border"],
                      command=add_preset).pack(side="left", padx=(0, TOKENS.space_2))
        ctk.CTkButton(top, text="Delete", height=36, width=84,
                      fg_color="transparent", hover_color=c["surface_2"],
                      text_color=c["danger"], border_width=1, border_color=c["border"],
                      command=del_preset).pack(side="left")

        # Editor textarea
        self._prompt_text = ctk.CTkTextbox(b, height=220, wrap="word",
                                           fg_color=c["surface_2"], border_color=c["border"], border_width=1,
                                           text_color=c["text"], font=font(TOKENS.text_md))
        self._prompt_text.pack(fill="both", expand=True, pady=(TOKENS.space_2, TOKENS.space_2))
        self._editor_dirty_preset = self._active_preset_var.get()
        self._prompt_text.insert("1.0", self._presets_state.get(self._active_preset_var.get(), ""))

        Hint(b, "Switching presets auto-saves the editor into the chosen preset. Click Save changes (bottom) to persist all.",
             theme=self._theme).widget.pack(anchor="w", pady=(TOKENS.space_1, 0))

        # Whisper model (cloud)
        card2 = Card(parent, title="Cloud Whisper model",
                     subtitle="Only used when Backend = openai or auto.",
                     theme=self._theme)
        card2.pack(fill="x")
        b2 = card2.body
        self._whisper_var = tk.StringVar(value=self._cfg.get("whisper_model", "whisper-1"))
        row = ctk.CTkFrame(b2, fg_color="transparent"); row.pack(fill="x")
        ctk.CTkLabel(row, text="Whisper model", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=160, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=self._whisper_var, height=36,
                     fg_color=c["surface_2"], border_color=c["border"], border_width=1,
                     text_color=c["text"], font=font(TOKENS.text_md, family="Consolas")).pack(side="left", fill="x", expand=True)

    def _switch_preset(self):
        # Stash current
        if self._editor_dirty_preset:
            self._presets_state[self._editor_dirty_preset] = self._prompt_text.get("1.0", "end").strip()
        # Load new
        new = self._active_preset_var.get()
        self._prompt_text.delete("1.0", "end")
        self._prompt_text.insert("1.0", self._presets_state.get(new, ""))
        self._editor_dirty_preset = new

    def _stash_editor(self):
        if self._editor_dirty_preset:
            self._presets_state[self._editor_dirty_preset] = self._prompt_text.get("1.0", "end").strip()

    def _render_hotkeys(self, parent):
        c = self._c
        card = Card(parent, title="Preset hotkeys",
                    subtitle="Click a chord button and press the keys you want. Esc clears. Hotkeys must be unique.",
                    theme=self._theme)
        card.pack(fill="x")
        b = card.body
        self._chord_buttons = {}  # preset -> ChordCaptureButton
        preset_to_hotkey = {p: hk for hk, p in self._preset_hotkeys_state.items()}
        for preset_name in sorted(self._presets_state.keys()):
            row = ctk.CTkFrame(b, fg_color="transparent")
            row.pack(fill="x", pady=TOKENS.space_2)
            badge = ctk.CTkLabel(row, text=preset_name, text_color=c["text"],
                                 font=font(TOKENS.text_md, "bold"), width=140, anchor="w")
            badge.pack(side="left")
            btn = ChordCaptureButton(row, initial_chord=preset_to_hotkey.get(preset_name, ""),
                                     theme=self._theme, width=320)
            btn.pack(side="left", fill="x", expand=True)
            self._chord_buttons[preset_name] = btn

        # Auto-paste
        card2 = Card(parent, title="Paste behavior", theme=self._theme)
        card2.pack(fill="x", pady=(TOKENS.space_3, 0))
        self._auto_paste_var = tk.BooleanVar(value=self._cfg.get("auto_paste", False))
        ctk.CTkCheckBox(card2.body, text="Auto-paste with Ctrl+V after copying to clipboard",
                        variable=self._auto_paste_var,
                        text_color=c["text"], font=font(TOKENS.text_md),
                        fg_color=c["accent"], hover_color=c["accent_hi"],
                        checkmark_color=c["on_accent"], border_color=c["border"]).pack(anchor="w")

    def _render_audio(self, parent):
        c = self._c
        card = Card(parent, title="Microphone",
                    subtitle="Pick a recording device and verify VoiceRefine can hear you.",
                    theme=self._theme)
        card.pack(fill="x")
        b = card.body
        try:
            devs = sd.query_devices()
            inputs = [(i, d["name"]) for i, d in enumerate(devs) if d.get("max_input_channels", 0) > 0]
        except Exception:
            inputs = []
        labels = ["System default"] + [f"{i}: {n}" for i, n in inputs]
        if not inputs:
            labels = ["No input devices found"]
        configured = self._cfg.get("input_device")
        configured_label = next((f"{i}: {n}" for i, n in inputs if i == configured), labels[0])
        self._device_var = tk.StringVar(value=configured_label)

        row = ctk.CTkFrame(b, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Input device", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=140, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, variable=self._device_var, values=labels,
                          fg_color=c["surface_2"], button_color=c["surface_3"],
                          button_hover_color=c["border_hi"], text_color=c["text"],
                          height=36, width=380, dynamic_resizing=False).pack(side="left")
        # Mic test
        test_card = ctk.CTkFrame(b, fg_color=c["surface_2"], corner_radius=TOKENS.radius_md,
                                 border_color=c["border"], border_width=1)
        test_card.pack(fill="x", pady=(TOKENS.space_3, 0))
        inner = ctk.CTkFrame(test_card, fg_color=c["surface_2"])
        inner.pack(fill="x", padx=TOKENS.space_4, pady=TOKENS.space_3)
        self._mic_status_var = tk.StringVar(value="Hit Test to listen for 3 seconds.")
        ctk.CTkLabel(inner, textvariable=self._mic_status_var, text_color=c["text_dim"],
                     font=font(TOKENS.text_md), anchor="w").pack(side="left", fill="x", expand=True)
        self._mic_wf = WaveformBars(inner, theme=self._theme, bars=14, width=180, height=36)
        self._mic_wf.canvas.configure(bg=c["surface_2"])
        self._mic_wf.canvas.pack(side="right")
        ctk.CTkButton(b, text="Test microphone (3s)", height=36,
                      fg_color=c["accent"], hover_color=c["accent_hi"],
                      text_color=c["on_accent"], font=font(TOKENS.text_md, "bold"),
                      command=self._run_mic_test).pack(anchor="w", pady=(TOKENS.space_3, 0))

    def _run_mic_test(self):
        if self._mic_thread and self._mic_thread.is_alive():
            return
        sel = self._device_var.get() if self._device_var else ""
        device = None
        if sel and sel[0].isdigit():
            try: device = int(sel.split(":", 1)[0])
            except Exception: device = None
        self._mic_stop.clear()
        self._mic_status_var.set("Listening…")
        def worker():
            try:
                sr = 16000
                frames = []
                def cb(indata, n, t, status): frames.append(indata.copy())
                stream = sd.InputStream(samplerate=sr, channels=1, dtype="int16",
                                        device=device, callback=cb)
                stream.start()
                t0 = time.time()
                while time.time() - t0 < 3.0 and not self._mic_stop.is_set():
                    time.sleep(0.05)
                    if frames:
                        rms = float(np.sqrt(np.mean(frames[-1].astype(float) ** 2)))
                        level = min(rms / 3000.0, 1.0)
                        self.root.after(0, lambda l=level: self._mic_wf.set_level(l, "recording"))
                stream.stop(); stream.close()
                peak = 0.0
                for fr in frames:
                    rms = float(np.sqrt(np.mean(fr.astype(float) ** 2)))
                    peak = max(peak, min(rms / 3000.0, 1.0))
                if peak < 0.04:
                    self._mic_status_var.set("✗ Silence detected. Try speaking louder or switch device.")
                else:
                    self._mic_status_var.set(f"✓ Mic working. Peak level {int(peak*100)}%.")
                self.root.after(0, lambda: self._mic_wf.set_level(0, "idle"))
            except Exception as e:
                self._mic_status_var.set(f"✗ Mic error: {str(e)[:140]}")
        self._mic_thread = threading.Thread(target=worker, daemon=True)
        self._mic_thread.start()

    def _render_vault(self, parent):
        c = self._c
        card = Card(parent, title="Obsidian vault writes",
                    subtitle="Save each capture to your vault under 11-Data/<category>/YYYY/MM/<id>.json + .md, matching the PersonalData intake schema.",
                    theme=self._theme)
        card.pack(fill="x")
        b = card.body
        self._vault_enabled_var = tk.BooleanVar(value=self._cfg.get("vault_enabled", False))
        ctk.CTkCheckBox(b, text="Write each capture to the vault",
                        variable=self._vault_enabled_var,
                        text_color=c["text"], font=font(TOKENS.text_md),
                        fg_color=c["accent"], hover_color=c["accent_hi"],
                        checkmark_color=c["on_accent"], border_color=c["border"]).pack(anchor="w", pady=(0, TOKENS.space_2))

        row = ctk.CTkFrame(b, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Vault root", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=140, anchor="w").pack(side="left")
        self._vault_path_var = tk.StringVar(value=self._cfg.get("vault_path", ""))
        ctk.CTkEntry(row, textvariable=self._vault_path_var, height=36,
                     fg_color=c["surface_2"], border_color=c["border"], border_width=1,
                     text_color=c["text"], font=font(TOKENS.text_md, family="Consolas")).pack(side="left", fill="x", expand=True, padx=(0, TOKENS.space_2))
        def browse():
            p = filedialog.askdirectory(title="Select vault root (folder containing 11-Data/)")
            if p: self._vault_path_var.set(p)
        ctk.CTkButton(row, text="Browse", width=80, height=36,
                      fg_color=c["surface_2"], hover_color=c["surface_3"],
                      text_color=c["text"], border_width=1, border_color=c["border"],
                      command=browse).pack(side="left")

        row = ctk.CTkFrame(b, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Category", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=140, anchor="w").pack(side="left")
        self._vault_category_var = tk.StringVar(value=self._cfg.get("vault_category", "voice-captures"))
        ctk.CTkEntry(row, textvariable=self._vault_category_var, height=36,
                     fg_color=c["surface_2"], border_color=c["border"], border_width=1,
                     text_color=c["text"], font=font(TOKENS.text_md)).pack(side="left", fill="x", expand=True)
        Hint(b, "Subfolder under 11-Data/. Letters, numbers, dashes only. Defaults to voice-captures.",
             theme=self._theme).widget.pack(anchor="w", pady=(TOKENS.space_2, 0))

    def _render_backend(self, parent):
        c = self._c
        card = Card(parent, title="Transcription backend",
                    subtitle="Choose where audio gets transcribed. Polish (GPT) always uses OpenAI.",
                    theme=self._theme)
        card.pack(fill="x")
        b = card.body
        self._backend_var = tk.StringVar(value=self._cfg.get("transcription_backend", "openai"))
        row = ctk.CTkFrame(b, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Engine", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=140, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, variable=self._backend_var,
                          values=["openai", "auto", "local"],
                          fg_color=c["surface_2"], button_color=c["surface_3"],
                          button_hover_color=c["border_hi"], text_color=c["text"],
                          height=36, width=200, dynamic_resizing=False).pack(side="left")
        Hint(b, "openai = cloud Whisper API.   local = faster-whisper on this PC.   auto = try local first, fall back to OpenAI.",
             theme=self._theme).widget.pack(anchor="w", pady=(TOKENS.space_1, 0))

        row = ctk.CTkFrame(b, fg_color="transparent"); row.pack(fill="x", pady=TOKENS.space_2)
        ctk.CTkLabel(row, text="Local model size", text_color=c["text_dim"], font=font(TOKENS.text_md),
                     width=140, anchor="w").pack(side="left")
        self._local_size_var = tk.StringVar(value=self._cfg.get("local_model_size", "base"))
        ctk.CTkOptionMenu(row, variable=self._local_size_var,
                          values=["tiny", "base", "small", "medium", "large-v3"],
                          fg_color=c["surface_2"], button_color=c["surface_3"],
                          button_hover_color=c["border_hi"], text_color=c["text"],
                          height=36, width=200, dynamic_resizing=False).pack(side="left")
        # Probe
        try:
            from voicerefine_local_whisper import is_available as _ok
            ok = _ok()
        except Exception: ok = False
        status = "✓ faster-whisper is installed." if ok else "✗ faster-whisper is NOT installed. Run: pip install faster-whisper"
        Hint(b, status, theme=self._theme).widget.pack(anchor="w", pady=(TOKENS.space_2, 0))

    def _render_about(self, parent):
        c = self._c
        card = Card(parent, title="About VoiceRefine",
                    subtitle=f"v{self._app_version} · CK42X project · MIT licensed.",
                    theme=self._theme)
        card.pack(fill="x")
        b = card.body
        for label, val in [
            ("Config path", "config.json (next to the executable)"),
            ("History path", "history.json (next to the executable)"),
            ("Brand", "CK42X — matte black + amber"),
        ]:
            r = ctk.CTkFrame(b, fg_color="transparent"); r.pack(fill="x", pady=TOKENS.space_1)
            ctk.CTkLabel(r, text=label, text_color=c["text_subtle"], font=font(TOKENS.text_md),
                         width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, text_color=c["text"], font=font(TOKENS.text_md),
                         anchor="w").pack(side="left")
        actions = ctk.CTkFrame(b, fg_color="transparent"); actions.pack(fill="x", pady=(TOKENS.space_3, 0))
        ctk.CTkButton(actions, text="Open CK42X.com", height=36,
                      fg_color=c["surface_2"], hover_color=c["surface_3"],
                      text_color=c["text"], border_width=1, border_color=c["border"],
                      command=lambda: webbrowser.open_new_tab(CK42X_URL)).pack(side="left", padx=(0, TOKENS.space_2))
        ctk.CTkButton(actions, text="GitHub repo", height=36,
                      fg_color=c["surface_2"], hover_color=c["surface_3"],
                      text_color=c["text"], border_width=1, border_color=c["border"],
                      command=lambda: webbrowser.open_new_tab("https://github.com/lordbuffcloud/VoiceRefine")).pack(side="left")

    # --------------------------------------------------------- save / close
    def _save(self):
        # Stash any in-flight prompt editor
        if hasattr(self, "_prompt_text") and self._editor_dirty_preset:
            self._presets_state[self._editor_dirty_preset] = self._prompt_text.get("1.0", "end").strip()
        # Build new preset_hotkeys map from chord buttons (only if hotkeys section was rendered;
        # otherwise keep prior state).
        new_map = dict(self._preset_hotkeys_state)
        if hasattr(self, "_chord_buttons"):
            new_map = {}
            for preset, btn in self._chord_buttons.items():
                ch = (btn.get_chord() or "").strip()
                if ch:
                    new_map[ch] = preset
        legacy_hotkey = next((hk for hk, p in new_map.items() if p == "default"),
                             self._cfg.get("hotkey", "<cmd>+<alt>"))
        # Device selection
        device = None
        if hasattr(self, "_device_var"):
            sel = self._device_var.get() or ""
            if sel and sel[0].isdigit():
                try: device = int(sel.split(":", 1)[0])
                except Exception: device = None
        else:
            device = self._cfg.get("input_device")
        # Compose updated config
        self._cfg.update({
            "openai_api_key":    self._api_var.get().strip() if hasattr(self, "_api_var") else self._cfg.get("openai_api_key", ""),
            "model":             self._model_var.get().strip() if hasattr(self, "_model_var") else self._cfg.get("model"),
            "whisper_model":     self._whisper_var.get().strip() if hasattr(self, "_whisper_var") else self._cfg.get("whisper_model"),
            "input_device":      device,
            "hotkey":            legacy_hotkey,
            "presets":           dict(self._presets_state),
            "prompt":            self._presets_state.get("default", self._cfg.get("prompt", "")),
            "preset_hotkeys":    new_map,
            "active_preset":     self._active_preset_var.get() if hasattr(self, "_active_preset_var") else self._cfg.get("active_preset", "default"),
            "auto_paste":        self._auto_paste_var.get() if hasattr(self, "_auto_paste_var") else self._cfg.get("auto_paste", False),
            "show_overlay":      self._overlay_var.get() if hasattr(self, "_overlay_var") else self._cfg.get("show_overlay", True),
            "overlay_position":  self._pos_var.get() if hasattr(self, "_pos_var") else self._cfg.get("overlay_position", "bottom-right"),
            "overlay_duration":  int(self._dur_var.get()) if hasattr(self, "_dur_var") else self._cfg.get("overlay_duration", 3),
            "window_opacity":    round(float(self._opacity_var.get()), 2) if hasattr(self, "_opacity_var") else self._cfg.get("window_opacity", 0.96),
            "theme":             self._theme_var.get() if hasattr(self, "_theme_var") else self._cfg.get("theme", "dark"),
            "vault_enabled":     self._vault_enabled_var.get() if hasattr(self, "_vault_enabled_var") else self._cfg.get("vault_enabled", False),
            "vault_path":        self._vault_path_var.get().strip() if hasattr(self, "_vault_path_var") else self._cfg.get("vault_path", ""),
            "vault_category":   (self._vault_category_var.get().strip() if hasattr(self, "_vault_category_var") else "voice-captures") or "voice-captures",
            "transcription_backend": self._backend_var.get() if hasattr(self, "_backend_var") else self._cfg.get("transcription_backend", "openai"),
            "local_model_size":  self._local_size_var.get() if hasattr(self, "_local_size_var") else self._cfg.get("local_model_size", "base"),
        })
        if self._on_save:
            try: self._on_save(self._cfg)
            except Exception as e: print(f"  [settings] on_save error: {e}")
        try: self.root.destroy()
        except Exception: pass

    def _on_close(self):
        if self._mic_thread and self._mic_thread.is_alive():
            self._mic_stop.set()
        try: self.root.destroy()
        except Exception: pass
