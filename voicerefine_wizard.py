#!/usr/bin/env python3
"""VoiceRefine first-run onboarding wizard.

5 steps:
  1. Welcome      — branding + "Let's get you set up"
  2. API Key      — paste + live validate against OpenAI /v1/models
  3. Microphone   — device picker + 3s live test with waveform
  4. Hotkey       — chord capture for the 'default' preset
  5. Done         — summary + Launch

Designed to feel like a modern desktop app onboarding — single window,
clear step progress, focused content per step.
"""
from __future__ import annotations

import threading
import time
import webbrowser
from pathlib import Path

try:
    import customtkinter as ctk
    import tkinter as tk
    HAS_CTK = True
except ImportError:
    HAS_CTK = False
    ctk = None
    import tkinter as tk

import numpy as np
import sounddevice as sd

from voicerefine_ui import (
    TOKENS, COLORS, palette, font, apply_theme,
    Card, SectionHeader, Hint, ChordCaptureButton, WaveformBars, StepIndicator,
)


CK42X_URL = "https://ck42x.com"
OPENAI_KEYS_URL = "https://platform.openai.com/api-keys"


class Wizard:
    """First-run setup wizard.

    Construct with the current config dict and on_complete callback.
    on_complete(updated_config) is fired only if the user finishes; cancellation
    leaves the original config unchanged.
    """
    STEPS = ("Welcome", "API Key", "Microphone", "Hotkey", "Ready")

    def __init__(self, config: dict, on_complete=None, icon_path: Path = None, theme: str = "dark"):
        self._cfg = dict(config)
        self._on_complete = on_complete
        self._icon = icon_path
        self._theme = theme
        self._c = palette(theme)
        self._step = 0
        self._completed = False
        self._mic_test_thread = None
        self._mic_test_stop = threading.Event()
        # Result holders
        self._api_var = None
        self._api_status_var = None
        self._device_var = None
        self._device_meta = []
        self._waveform = None
        self._chord_button = None
        self._captured_chord = self._cfg.get("preset_hotkeys", {}) or {}

    def run(self):
        if not HAS_CTK:
            return
        apply_theme(self._theme)
        self.root = ctk.CTk()
        self.root.title("Welcome to VoiceRefine")
        self.root.geometry("780x560")
        self.root.minsize(720, 520)
        try:
            if self._icon and Path(self._icon).exists():
                self.root.iconbitmap(str(self._icon))
        except Exception:
            pass
        self._center()
        self._build_chrome()
        self._render_step()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())
        self.root.mainloop()
        return self._completed

    # ------------------------------------------------------------------ chrome
    def _center(self):
        self.root.update_idletasks()
        w, h = 780, 560
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build_chrome(self):
        c = self._c
        self.root.configure(fg_color=c["bg"])
        # Top bar: brand + step indicator
        top = ctk.CTkFrame(self.root, fg_color="transparent")
        top.pack(fill="x", padx=TOKENS.space_5, pady=(TOKENS.space_5, TOKENS.space_3))
        brand = ctk.CTkLabel(top, text="VoiceRefine", text_color=c["text"],
                             font=font(TOKENS.text_2xl, "bold"))
        brand.pack(side="left")
        ctk.CTkLabel(top, text="·  setup", text_color=c["text_subtle"],
                     font=font(TOKENS.text_lg)).pack(side="left", padx=(TOKENS.space_2, 0))
        link = ctk.CTkButton(top, text="ck42x.com", width=84, height=28,
                             fg_color="transparent", hover_color=c["surface_2"],
                             text_color=c["text_subtle"], border_width=0,
                             command=lambda: webbrowser.open_new_tab(CK42X_URL))
        link.pack(side="right")

        # Content area (single Card swapped per step)
        self.content_holder = ctk.CTkFrame(self.root, fg_color="transparent")
        self.content_holder.pack(fill="both", expand=True, padx=TOKENS.space_5, pady=TOKENS.space_2)

        # Bottom bar: step indicator + nav
        bottom = ctk.CTkFrame(self.root, fg_color="transparent")
        bottom.pack(fill="x", padx=TOKENS.space_5, pady=(TOKENS.space_3, TOKENS.space_5))
        self.step_ind = StepIndicator(bottom, steps=len(self.STEPS), current=0, theme=self._theme)
        self.step_ind.frame.pack(side="left")

        nav = ctk.CTkFrame(bottom, fg_color="transparent")
        nav.pack(side="right")
        self.back_btn = ctk.CTkButton(nav, text="Back", width=88, height=36,
                                      fg_color="transparent", hover_color=c["surface_2"],
                                      text_color=c["text_dim"], border_width=1, border_color=c["border"],
                                      command=self._prev_step)
        self.back_btn.pack(side="left", padx=(0, TOKENS.space_2))
        self.next_btn = ctk.CTkButton(nav, text="Next", width=120, height=36,
                                      fg_color=c["accent"], hover_color=c["accent_hi"],
                                      text_color=c["on_accent"], font=font(TOKENS.text_md, "bold"),
                                      command=self._next_step)
        self.next_btn.pack(side="left")

    def _render_step(self):
        for w in self.content_holder.winfo_children():
            w.destroy()
        self.step_ind.set_current(self._step)
        renderer = (self._step_welcome, self._step_api, self._step_mic, self._step_hotkey, self._step_done)[self._step]
        renderer()
        # Nav button state
        self.back_btn.configure(state="disabled" if self._step == 0 else "normal")
        if self._step == 0:
            self.next_btn.configure(text="Get started")
        elif self._step == len(self.STEPS) - 1:
            self.next_btn.configure(text="Launch VoiceRefine")
        else:
            self.next_btn.configure(text="Continue")

    def _prev_step(self):
        if self._step > 0:
            self._step -= 1
            self._render_step()

    def _next_step(self):
        if self._step < len(self.STEPS) - 1:
            # validations between steps
            if self._step == 1 and not self._api_var.get().strip():
                self._api_status_var.set("(API key required to continue)")
                return
            self._step += 1
            self._render_step()
        else:
            self._finish()

    def _on_close(self):
        if self._mic_test_thread and self._mic_test_thread.is_alive():
            self._mic_test_stop.set()
        try:
            self.root.destroy()
        except Exception:
            pass

    def _finish(self):
        # Persist captured values into config
        self._cfg["openai_api_key"] = (self._api_var.get() or "").strip()
        # Device
        if self._device_var and self._device_var.get():
            label = self._device_var.get()
            if label and label[0].isdigit():
                try: self._cfg["input_device"] = int(label.split(":", 1)[0])
                except Exception: self._cfg["input_device"] = None
            else:
                self._cfg["input_device"] = None
        # Hotkey
        chord = self._chord_button.get_chord() if self._chord_button else ""
        if chord:
            new_map = dict(self._cfg.get("preset_hotkeys") or {})
            # Drop any existing binding to 'default' and any other preset using this chord
            for k in [k for k, v in new_map.items() if v == "default"]:
                new_map.pop(k, None)
            new_map[chord] = "default"
            self._cfg["preset_hotkeys"] = new_map
            self._cfg["hotkey"] = chord  # legacy mirror
        self._completed = True
        if self._on_complete:
            try: self._on_complete(self._cfg)
            except Exception as e: print(f"  [wizard] on_complete error: {e}")
        try:
            self.root.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------ steps
    def _step_welcome(self):
        c = self._c
        card = Card(self.content_holder, theme=self._theme, padding=TOKENS.space_6)
        card.pack(fill="both", expand=True)
        body = card.body
        # Big mark + tagline
        ctk.CTkLabel(body, text="Press to talk.", text_color=c["text"],
                     font=font(TOKENS.text_3xl, "bold")).pack(anchor="w", pady=(0, TOKENS.space_1))
        ctk.CTkLabel(body, text="Paste polished.", text_color=c["accent"],
                     font=font(TOKENS.text_3xl, "bold")).pack(anchor="w", pady=(0, TOKENS.space_4))
        ctk.CTkLabel(body, text="Hold a hotkey to record. Whisper transcribes. GPT polishes. The result lands on your clipboard, ready to paste anywhere.",
                     text_color=c["text_dim"], font=font(TOKENS.text_lg), wraplength=620, justify="left", anchor="w").pack(anchor="w", pady=(0, TOKENS.space_5))
        # Three quick bullets
        for icon, line in [
            ("●", "Multiple polish presets bound to different hotkey chords"),
            ("●", "Optional local Whisper for offline transcription"),
            ("●", "Optional vault writes for second-brain capture"),
        ]:
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(anchor="w", pady=TOKENS.space_1)
            ctk.CTkLabel(row, text=icon, text_color=c["accent"], font=font(TOKENS.text_md)).pack(side="left", padx=(0, TOKENS.space_2))
            ctk.CTkLabel(row, text=line, text_color=c["text_dim"], font=font(TOKENS.text_md), anchor="w").pack(side="left")
        ctk.CTkLabel(body, text="Setup takes about 60 seconds.",
                     text_color=c["text_subtle"], font=font(TOKENS.text_sm)).pack(anchor="w", pady=(TOKENS.space_5, 0))

    def _step_api(self):
        c = self._c
        import os
        card = Card(self.content_holder, title="Your OpenAI API key",
                    subtitle="Stored locally in config.json next to the executable. We never see it.",
                    theme=self._theme, padding=TOKENS.space_6)
        card.pack(fill="both", expand=True)
        body = card.body

        env_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self._api_var = tk.StringVar(value=self._cfg.get("openai_api_key", "") or env_key)
        self._api_status_var = tk.StringVar(value=("Loaded from OPENAI_API_KEY env var." if env_key and not self._cfg.get("openai_api_key") else ""))

        # Input row
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(TOKENS.space_2, TOKENS.space_2))
        entry = ctk.CTkEntry(row, textvariable=self._api_var, height=44,
                             corner_radius=TOKENS.radius_md,
                             fg_color=c["surface_2"], border_color=c["border"], border_width=1,
                             text_color=c["text"], placeholder_text="sk-...",
                             font=font(TOKENS.text_md, family="Consolas"), show="*")
        entry.pack(side="left", fill="x", expand=True, padx=(0, TOKENS.space_2))
        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            show_var.set(not show_var.get())
            entry.configure(show="" if show_var.get() else "*")
            show_btn.configure(text="Hide" if show_var.get() else "Show")
        show_btn = ctk.CTkButton(row, text="Show", width=72, height=44,
                                 fg_color="transparent", hover_color=c["surface_2"],
                                 text_color=c["text_dim"], border_width=1, border_color=c["border"],
                                 command=toggle_show)
        show_btn.pack(side="left", padx=(0, TOKENS.space_2))
        validate_btn = ctk.CTkButton(row, text="Validate", width=104, height=44,
                                     fg_color=c["surface_2"], hover_color=c["surface_3"],
                                     text_color=c["text"], border_width=1, border_color=c["border"],
                                     command=lambda: self._validate_api(entry))
        validate_btn.pack(side="left")
        # Status
        self.status_lbl = ctk.CTkLabel(body, textvariable=self._api_status_var,
                                       text_color=c["text_subtle"], font=font(TOKENS.text_sm),
                                       anchor="w", justify="left", wraplength=620)
        self.status_lbl.pack(anchor="w", pady=(TOKENS.space_2, TOKENS.space_4))
        # Helper bar
        helper = ctk.CTkFrame(body, fg_color=c["surface_2"], corner_radius=TOKENS.radius_md, border_color=c["border"], border_width=1)
        helper.pack(fill="x", pady=(0, TOKENS.space_3))
        ctk.CTkLabel(helper, text="Don't have a key yet?", text_color=c["text_dim"],
                     font=font(TOKENS.text_md), anchor="w").pack(side="left", padx=TOKENS.space_4, pady=TOKENS.space_3)
        ctk.CTkButton(helper, text="Get one from OpenAI →", height=32,
                      fg_color=c["accent"], hover_color=c["accent_hi"], text_color=c["on_accent"],
                      font=font(TOKENS.text_md, "bold"),
                      command=lambda: webbrowser.open_new_tab(OPENAI_KEYS_URL)).pack(side="right", padx=TOKENS.space_3, pady=TOKENS.space_2)
        entry.focus_set()

    def _validate_api(self, entry_widget):
        key = (self._api_var.get() or "").strip()
        if not key:
            self._api_status_var.set("(Empty)  Paste a key and click Validate.")
            return
        self._api_status_var.set("Checking…")
        def worker():
            try:
                from openai import OpenAI
                client = OpenAI(api_key=key)
                # Light call — list models
                _ = client.models.list()
                self._api_status_var.set("✓ Connected to OpenAI.")
            except Exception as e:
                self._api_status_var.set(f"✗ Validation failed: {str(e)[:140]}")
        threading.Thread(target=worker, daemon=True).start()

    def _step_mic(self):
        c = self._c
        card = Card(self.content_holder, title="Your microphone",
                    subtitle="Pick an input device. Hit Test to confirm VoiceRefine is hearing you.",
                    theme=self._theme, padding=TOKENS.space_6)
        card.pack(fill="both", expand=True)
        body = card.body
        # Device dropdown
        try:
            devs = sd.query_devices()
            self._device_meta = [(i, d["name"]) for i, d in enumerate(devs) if d.get("max_input_channels", 0) > 0]
        except Exception:
            self._device_meta = []
        labels = ["System default"] + [f"{i}: {n}" for i, n in self._device_meta]
        if not self._device_meta:
            labels = ["No input devices found"]
        configured = self._cfg.get("input_device")
        configured_label = next((f"{i}: {n}" for i, n in self._device_meta if i == configured), labels[0])
        self._device_var = tk.StringVar(value=configured_label)
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(TOKENS.space_2, TOKENS.space_3))
        ctk.CTkLabel(row, text="Input device", text_color=c["text_dim"],
                     font=font(TOKENS.text_md), width=120, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(row, variable=self._device_var, values=labels,
                          fg_color=c["surface_2"], button_color=c["surface_3"],
                          button_hover_color=c["border_hi"], text_color=c["text"],
                          height=40, dynamic_resizing=False, width=420).pack(side="left", fill="x", expand=True)
        # Live waveform
        wf_card = ctk.CTkFrame(body, fg_color=c["surface_2"], corner_radius=TOKENS.radius_md,
                               border_color=c["border"], border_width=1)
        wf_card.pack(fill="x", pady=(TOKENS.space_3, TOKENS.space_2))
        inner = ctk.CTkFrame(wf_card, fg_color=c["surface_2"])
        inner.pack(fill="x", padx=TOKENS.space_4, pady=TOKENS.space_4)
        self._wf_status_var = tk.StringVar(value="Click Test to listen for 3 seconds.")
        ctk.CTkLabel(inner, textvariable=self._wf_status_var, text_color=c["text_dim"],
                     font=font(TOKENS.text_md), anchor="w").pack(side="left", fill="x", expand=True)
        # Waveform widget on the right
        self._waveform = WaveformBars(inner, theme=self._theme, bars=14, width=180, height=36)
        self._waveform.canvas.configure(bg=c["surface_2"])
        self._waveform.canvas.pack(side="right")
        # Test button
        test_btn = ctk.CTkButton(body, text="Test microphone (3s)", height=40,
                                 fg_color=c["accent"], hover_color=c["accent_hi"], text_color=c["on_accent"],
                                 font=font(TOKENS.text_md, "bold"),
                                 command=self._run_mic_test)
        test_btn.pack(anchor="w", pady=(TOKENS.space_3, 0))
        Hint(body, "If the bars stay flat while you speak, switch device above or check Windows Sound settings.",
             theme=self._theme).widget.pack(anchor="w", pady=(TOKENS.space_3, 0))

    def _run_mic_test(self):
        if self._mic_test_thread and self._mic_test_thread.is_alive():
            return
        # Resolve device
        sel = self._device_var.get() if self._device_var else ""
        device = None
        if sel and sel[0].isdigit():
            try: device = int(sel.split(":", 1)[0])
            except Exception: device = None
        self._mic_test_stop.clear()
        self._wf_status_var.set("Listening…")
        def worker():
            try:
                sr = 16000
                frames = []
                def cb(indata, n, t, status):
                    frames.append(indata.copy())
                stream = sd.InputStream(samplerate=sr, channels=1, dtype="int16",
                                        device=device, callback=cb)
                stream.start()
                t0 = time.time()
                while time.time() - t0 < 3.0 and not self._mic_test_stop.is_set():
                    time.sleep(0.05)
                    if frames:
                        rms = float(np.sqrt(np.mean(frames[-1].astype(float) ** 2)))
                        level = min(rms / 3000.0, 1.0)
                        # Marshal to main thread
                        self.root.after(0, lambda l=level: self._waveform.set_level(l, "recording"))
                stream.stop(); stream.close()
                peak = 0.0
                for fr in frames:
                    rms = float(np.sqrt(np.mean(fr.astype(float) ** 2)))
                    peak = max(peak, min(rms / 3000.0, 1.0))
                if peak < 0.04:
                    self._wf_status_var.set("✗ Silence detected. Try speaking louder or switch device.")
                else:
                    self._wf_status_var.set(f"✓ Mic working. Peak level {int(peak*100)}%.")
                self.root.after(0, lambda: self._waveform.set_level(0, "idle"))
            except Exception as e:
                self._wf_status_var.set(f"✗ Mic error: {str(e)[:140]}")
        self._mic_test_thread = threading.Thread(target=worker, daemon=True)
        self._mic_test_thread.start()

    def _step_hotkey(self):
        c = self._c
        card = Card(self.content_holder, title="Pick a record hotkey",
                    subtitle="Click below and press the keys you want to hold. You can change this — and add hotkeys for other presets — in Settings.",
                    theme=self._theme, padding=TOKENS.space_6)
        card.pack(fill="both", expand=True)
        body = card.body
        # Existing default chord
        default_chord = next((hk for hk, p in (self._cfg.get("preset_hotkeys") or {}).items() if p == "default"),
                             self._cfg.get("hotkey", "<cmd>+<alt>"))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x", pady=(TOKENS.space_2, TOKENS.space_3))
        ctk.CTkLabel(row, text="Default preset chord", text_color=c["text_dim"],
                     font=font(TOKENS.text_md), width=200, anchor="w").pack(side="left")
        self._chord_button = ChordCaptureButton(row, initial_chord=default_chord,
                                                theme=self._theme, width=300)
        self._chord_button.pack(side="left", fill="x", expand=True)
        # Tip card
        tip = ctk.CTkFrame(body, fg_color=c["surface_2"], corner_radius=TOKENS.radius_md,
                           border_color=c["border"], border_width=1)
        tip.pack(fill="x", pady=(TOKENS.space_3, 0))
        ctk.CTkLabel(tip, text="Recommended", text_color=c["accent"], font=font(TOKENS.text_sm, "bold"),
                     anchor="w").pack(anchor="w", padx=TOKENS.space_4, pady=(TOKENS.space_3, 0))
        ctk.CTkLabel(tip, text="Win + Alt is a global combo that doesn't conflict with most apps. Hold, talk, release.",
                     text_color=c["text_dim"], font=font(TOKENS.text_md), wraplength=620, justify="left", anchor="w").pack(
                     anchor="w", padx=TOKENS.space_4, pady=(0, TOKENS.space_3))
        Hint(body, "You can add hotkeys for 'code', 'email', and 'summary' presets in Settings → Hotkeys after setup.",
             theme=self._theme).widget.pack(anchor="w", pady=(TOKENS.space_4, 0))

    def _step_done(self):
        c = self._c
        card = Card(self.content_holder, theme=self._theme, padding=TOKENS.space_6)
        card.pack(fill="both", expand=True)
        body = card.body
        # Big checkmark via canvas
        check = tk.Canvas(body, width=64, height=64,
                          bg=c["surface"], highlightthickness=0, bd=0)
        check.pack(anchor="w", pady=(0, TOKENS.space_3))
        check.create_oval(4, 4, 60, 60, outline=c["ok"], width=3)
        check.create_line(18, 33, 28, 43, fill=c["ok"], width=3, capstyle="round")
        check.create_line(28, 43, 48, 23, fill=c["ok"], width=3, capstyle="round")
        ctk.CTkLabel(body, text="You're ready.", text_color=c["text"],
                     font=font(TOKENS.text_3xl, "bold")).pack(anchor="w", pady=(0, TOKENS.space_2))
        # Summary
        default_chord = self._chord_button.get_chord() if self._chord_button else self._cfg.get("hotkey", "<cmd>+<alt>")
        device_label = self._device_var.get() if self._device_var else "System default"
        for label, val in [
            ("Hotkey", ChordCaptureButton._chord_display(default_chord) if default_chord else "(none)"),
            ("Microphone", device_label),
            ("Polish model", self._cfg.get("model", "gpt-4o-mini")),
            ("Transcription", self._cfg.get("transcription_backend", "openai")),
        ]:
            r = ctk.CTkFrame(body, fg_color="transparent")
            r.pack(fill="x", anchor="w", pady=TOKENS.space_1)
            ctk.CTkLabel(r, text=label, text_color=c["text_subtle"], font=font(TOKENS.text_md),
                         width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, text_color=c["text"], font=font(TOKENS.text_md, "bold"),
                         anchor="w").pack(side="left")
        ctk.CTkLabel(body, text="Click Launch to start. The tray icon appears in the bottom-right of your screen.",
                     text_color=c["text_dim"], font=font(TOKENS.text_md), wraplength=620, justify="left", anchor="w").pack(
                     anchor="w", pady=(TOKENS.space_4, 0))
