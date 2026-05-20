import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from voicerefine_ui import StepIndicator, WaveformBars, apply_theme, palette, resolve_tk_bg


class _FakeTransparentWidget:
    def __init__(self, master=None):
        self.master = master

    def cget(self, option):
        if option in {"fg_color", "bg"}:
            return "transparent"
        raise tk.TclError(option)


def test_resolve_tk_bg_never_returns_transparent_from_transparent_ancestry():
    child = _FakeTransparentWidget(_FakeTransparentWidget())

    bg = resolve_tk_bg(child, "#151517")

    assert bg == "#151517"
    assert bg != "transparent"


def test_raw_tk_canvases_under_transparent_ctk_frames_get_concrete_background():
    apply_theme("dark")
    c = palette("dark")
    root = ctk.CTk()
    root.withdraw()
    try:
        root.configure(fg_color=c["bg"])
        holder = ctk.CTkFrame(root, fg_color="transparent")
        holder.pack()

        step = StepIndicator(holder, steps=5, current=0, theme="dark")
        wave = WaveformBars(holder, theme="dark")

        assert step._dots[0][0].cget("background") != "transparent"
        assert wave.canvas.cget("background") != "transparent"
    finally:
        root.destroy()
