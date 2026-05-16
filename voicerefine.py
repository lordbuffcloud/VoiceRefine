#!/usr/bin/env python3
"""
VoiceRefine v2.0 - Voice to polished text, straight to your clipboard.
"""
import sys, os, traceback
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0] if hasattr(sys, 'argv') and sys.argv else __file__)), "voicerefine_crash.log")
def crash_handler(exc_type, exc_value, exc_tb):
    with open(LOG_PATH, "a") as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Crash at {__import__('datetime').datetime.now()}\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
    sys.__excepthook__(exc_type, exc_value, exc_tb)
sys.excepthook = crash_handler

import json, io, wave, threading, time, datetime, webbrowser
from pathlib import Path
import numpy as np
import sounddevice as sd
import pyperclip
from openai import OpenAI
from pynput import keyboard
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext, font as tkfont
    HAS_TK = True
except ImportError:
    HAS_TK = False

# CustomTkinter UI modules (preferred). Fall back to legacy Tk surfaces if missing.
try:
    import customtkinter as _ctk_probe  # noqa: F401
    from voicerefine_wizard import Wizard as _CtkWizard
    from voicerefine_settings import SettingsWindow as _CtkSettings
    HAS_CTK_UI = True
except ImportError:
    HAS_CTK_UI = False
    _CtkWizard = None
    _CtkSettings = None

if getattr(sys, 'frozen', False):
    _RESOURCE_BASE = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    _CONFIG_BASE = Path(sys.executable).parent
else:
    _RESOURCE_BASE = Path(__file__).parent
    _CONFIG_BASE = _RESOURCE_BASE
CONFIG_PATH = _CONFIG_BASE / "config.json"
HISTORY_PATH = _CONFIG_BASE / "history.json"
APP_NAME = "VoiceRefine"
APP_VERSION = "2.1.1"
CK42X_URL = "https://ck42x.com"
OPENAI_KEYS_URL = "https://platform.openai.com/api-keys"
APP_ICON_PATH = _RESOURCE_BASE / "branding" / "app-icon.ico"
_DEFAULT_PROMPT = "You are a writing assistant. Take the following transcribed speech and improve it: fix grammar, punctuation, and spelling errors. Make it clear and well-structured while preserving the speaker's original meaning and tone. If the text is a quick message, keep it casual. If it's more formal, match that register. Do not add information that wasn't in the original. Return only the improved text, nothing else."
DEFAULT_PRESETS = {
    "default": _DEFAULT_PROMPT,
    "code": "You are a coding assistant. The transcription is dictation intended as code, a code comment, a commit message, or a shell command. Clean up speech artifacts (uh, um, you know). Use precise technical vocabulary. Preserve identifier names, file paths, and command syntax exactly as spoken. Do NOT wrap the output in markdown code fences unless the speaker clearly asked for them. Return only the cleaned dictation.",
    "email": "You are an email writing assistant. Rewrite the transcription as a clear, professional email. Add greeting and sign-off only if obvious from context. Fix grammar and structure. Keep paragraphs short. Return only the email body, no subject line unless dictated.",
    "summary": "Summarize the transcription into concise bullet points. Each bullet should be a single complete thought. Return only the bullets, no preamble.",
}
DEFAULT_PRESET_HOTKEYS = {
    "<cmd>+<alt>": "default",
    "<cmd>+<alt>+c": "code",
    "<cmd>+<alt>+e": "email",
    "<cmd>+<alt>+s": "summary",
}
DEFAULT_CONFIG = {"openai_api_key":"","model":"gpt-4o-mini","whisper_model":"whisper-1","hotkey":"<cmd>+<alt>","prompt":_DEFAULT_PROMPT,"sample_rate":16000,"input_device":None,"show_overlay":True,"overlay_position":"bottom-right","overlay_duration":3,"window_opacity":0.96,"auto_paste":False,"play_sounds":True,"theme":"dark","max_history":100,"presets":DEFAULT_PRESETS,"preset_hotkeys":DEFAULT_PRESET_HOTKEYS,"active_preset":"default","vault_enabled":False,"vault_path":"","vault_category":"voice-captures","transcription_backend":"openai","local_model_size":"base"}
THEMES = {"dark":{"bg":"#0b0b0c","fg":"#e9e9ea","accent":"#ffb300","accent2":"#e94560","success":"#4ecca3","recording":"#e94560","thinking":"#ffb300","done":"#4ecca3","error":"#ff6b6b","panel":"#151517","panel2":"#101012","border":"#2a2b30","input_bg":"#101012","input_fg":"#e9e9ea","button":"#ffb300","button_fg":"#0b0b0c","subtle":"#a2a3a8"},"light":{"bg":"#f5f5f5","fg":"#1a1a1a","accent":"#d49100","accent2":"#c0392b","success":"#27ae60","recording":"#c0392b","thinking":"#d49100","done":"#27ae60","error":"#e74c3c","panel":"#ffffff","panel2":"#f0f0f1","border":"#d8d8dc","input_bg":"#ffffff","input_fg":"#1a1a1a","button":"#d49100","button_fg":"#ffffff","subtle":"#6c6d72"}}

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH,"r") as f: saved=json.load(f)
        merged={**DEFAULT_CONFIG,**saved}
        merged=migrate_config(merged,saved)
        return merged
    cfg=DEFAULT_CONFIG.copy(); save_config(cfg); return cfg

def migrate_config(merged, saved):
    """Backfill new keys (presets, preset_hotkeys, vault, backend) from legacy single-prompt/hotkey configs.

    Idempotent — only fills when the new key is absent or empty in the saved file.
    """
    # Presets: if user had a custom prompt but no presets dict saved, seed presets with it as default.
    if "presets" not in saved or not isinstance(saved.get("presets"), dict) or not saved.get("presets"):
        merged["presets"] = {**DEFAULT_PRESETS}
        legacy_prompt = saved.get("prompt") or ""
        if legacy_prompt and legacy_prompt.strip() and legacy_prompt != _DEFAULT_PROMPT:
            merged["presets"]["default"] = legacy_prompt
    else:
        # Ensure 'default' always exists
        if "default" not in merged["presets"]:
            merged["presets"]["default"] = saved.get("prompt") or _DEFAULT_PROMPT
    # Preset hotkeys: if missing, derive from legacy single hotkey
    if "preset_hotkeys" not in saved or not isinstance(saved.get("preset_hotkeys"), dict) or not saved.get("preset_hotkeys"):
        merged["preset_hotkeys"] = {**DEFAULT_PRESET_HOTKEYS}
        legacy_hotkey = saved.get("hotkey")
        if legacy_hotkey and legacy_hotkey != "<cmd>+<alt>":
            # User had a custom single hotkey — bind it to 'default', drop the canonical default mapping
            merged["preset_hotkeys"] = {legacy_hotkey: "default"}
    return merged

def save_config(cfg):
    with open(CONFIG_PATH,"w") as f: json.dump(cfg,f,indent=2)

def load_history():
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH,"r") as f: return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_PATH,"w") as f: json.dump(history,f,indent=2,ensure_ascii=False)

def has_api_key(config):
    return bool((config.get("openai_api_key","") or os.environ.get("OPENAI_API_KEY","")).strip())

def open_url(url):
    try: webbrowser.open_new_tab(url)
    except Exception as e: print(f"  Could not open {url}: {e}")

def apply_window_chrome(root,theme,alpha=0.96):
    root.configure(bg=theme["bg"])
    if APP_ICON_PATH.exists():
        try: root.iconbitmap(str(APP_ICON_PATH))
        except Exception: pass
    try: root.attributes("-alpha",alpha)
    except Exception: pass

def load_icon_photo(size=42):
    if not HAS_TK or not APP_ICON_PATH.exists(): return None
    try:
        from PIL import Image, ImageTk
        img=Image.open(APP_ICON_PATH).resize((size,size))
        return ImageTk.PhotoImage(img)
    except Exception:
        return None

def get_input_devices():
    try:
        devices=sd.query_devices()
        return [(i,d["name"]) for i,d in enumerate(devices) if d.get("max_input_channels",0)>0]
    except Exception:
        return []

def normalize_input_device(device):
    if device in (None,"","default"): return None
    try: return int(device)
    except (TypeError,ValueError): return None

def choose_input_device(configured_device=None):
    inputs=get_input_devices()
    if not inputs:
        raise RuntimeError("No microphone input device found. Connect or enable a microphone in Windows Sound settings, then reopen VoiceRefine.")
    configured_device=normalize_input_device(configured_device)
    available={idx for idx,_ in inputs}
    if configured_device in available: return configured_device
    default_device=sd.default.device[0] if isinstance(sd.default.device,(list,tuple)) else sd.default.device
    if isinstance(default_device,int) and default_device in available: return default_device
    return inputs[0][0]

class AudioRecorder:
    def __init__(self,sample_rate=16000,input_device=None):
        self.sample_rate=sample_rate;self.input_device=normalize_input_device(input_device);self.frames=[];self.recording=False;self.stream=None;self.start_time=None
    def start(self):
        self.frames=[];self.recording=True;self.start_time=time.time()
        try:
            device=choose_input_device(self.input_device)
            self.stream=sd.InputStream(samplerate=self.sample_rate,channels=1,dtype="int16",device=device,callback=self._callback)
            self.stream.start()
        except Exception:
            self.recording=False;self.start_time=None;self.stream=None
            raise
    def _callback(self,indata,frame_count,time_info,status):
        if self.recording: self.frames.append(indata.copy())
    def get_duration(self): return time.time()-self.start_time if self.start_time else 0
    def get_level(self):
        if self.frames:
            rms=np.sqrt(np.mean(self.frames[-1].astype(float)**2));return min(rms/3000,1.0)
        return 0
    def stop(self):
        self.recording=False
        if self.stream: self.stream.stop();self.stream.close();self.stream=None
        if not self.frames: return None
        return np.concatenate(self.frames,axis=0)
    def to_wav_bytes(self,audio):
        buf=io.BytesIO()
        with wave.open(buf,"wb") as wf: wf.setnchannels(1);wf.setsampwidth(2);wf.setframerate(self.sample_rate);wf.writeframes(audio.tobytes())
        buf.seek(0);return buf

class VoiceProcessor:
    def __init__(self,config):
        self.config=config;api_key=config.get("openai_api_key","") or os.environ.get("OPENAI_API_KEY","")
        if not api_key: raise ValueError("No OpenAI API key found. Set it in config.json or OPENAI_API_KEY env var.")
        self.client=OpenAI(api_key=api_key)
        self._local_backend=None
    def _get_local_backend(self):
        if self._local_backend is None:
            from voicerefine_local_whisper import LocalWhisperBackend
            self._local_backend=LocalWhisperBackend(model_size=self.config.get("local_model_size","base"))
        return self._local_backend
    def transcribe(self,wav_bytes):
        wav_bytes.name="recording.wav"
        backend=(self.config.get("transcription_backend","openai") or "openai").lower()
        if backend in ("local","auto"):
            try:
                wav_bytes.seek(0)
                text=self._get_local_backend().transcribe(wav_bytes)
                if text: return text
                if backend=="local": return ""
                # auto with empty result -> try OpenAI
                wav_bytes.seek(0)
            except Exception as e:
                if backend=="local": raise
                print(f"  [transcribe] local backend failed, falling back to OpenAI: {e}")
                wav_bytes.seek(0)
        return self.client.audio.transcriptions.create(model=self.config.get("whisper_model","whisper-1"),file=wav_bytes,response_format="text").strip()
    def improve(self,raw_text,prompt_override=None,preset_name=None):
        if prompt_override:
            prompt=prompt_override
        elif preset_name:
            prompt=self.config.get("presets",{}).get(preset_name) or self.config.get("prompt",DEFAULT_CONFIG["prompt"])
        else:
            prompt=self.config.get("prompt",DEFAULT_CONFIG["prompt"])
        return self.client.chat.completions.create(model=self.config.get("model","gpt-4o-mini"),messages=[{"role":"system","content":prompt},{"role":"user","content":raw_text}],temperature=0.3,max_tokens=2048).choices[0].message.content.strip()

class HotkeyManager:
    def __init__(self,hotkey_str,on_activate,on_release):
        self.on_activate=on_activate;self.on_release=on_release;self.pressed_keys=set()
        self.hotkey_keys=self._parse_hotkey(hotkey_str);self.active=False;self.listener=None
    def _parse_hotkey(self,s):
        keys=set();km={"<cmd>":keyboard.Key.cmd,"<alt>":keyboard.Key.alt,"<ctrl>":keyboard.Key.ctrl,"<shift>":keyboard.Key.shift,"<alt_l>":keyboard.Key.alt_l,"<alt_r>":keyboard.Key.alt_r,"<ctrl_l>":keyboard.Key.ctrl_l,"<ctrl_r>":keyboard.Key.ctrl_r,"<cmd_l>":keyboard.Key.cmd_l,"<cmd_r>":keyboard.Key.cmd_r}
        for p in s.lower().split("+"):
            p=p.strip()
            if p in km: keys.add(km[p])
            elif len(p)==1: keys.add(keyboard.KeyCode.from_char(p))
        return keys
    def _norm(self,key):
        v={keyboard.Key.alt_l:keyboard.Key.alt,keyboard.Key.alt_r:keyboard.Key.alt,keyboard.Key.ctrl_l:keyboard.Key.ctrl,keyboard.Key.ctrl_r:keyboard.Key.ctrl,keyboard.Key.cmd_l:keyboard.Key.cmd,keyboard.Key.cmd_r:keyboard.Key.cmd,keyboard.Key.shift_l:keyboard.Key.shift,keyboard.Key.shift_r:keyboard.Key.shift}
        return v.get(key,key)
    def _on_press(self,key):
        key=self._norm(key);self.pressed_keys.add(key)
        if self.hotkey_keys.issubset(self.pressed_keys) and not self.active: self.active=True;self.on_activate()
    def _on_release(self,key):
        key=self._norm(key)
        if self.active and key in self.hotkey_keys: self.active=False;self.on_release()
        self.pressed_keys.discard(key)
    def start(self): self.listener=keyboard.Listener(on_press=self._on_press,on_release=self._on_release);self.listener.start()
    def stop(self):
        if self.listener: self.listener.stop()

class MultiHotkeyManager:
    """Multiple hold-to-trigger chords. Longest-match wins; short commit-delay disambiguates supersets.

    hotkey_map: {hotkey_str: preset_name}
    on_activate(preset_name): called when a chord is committed.
    on_release(preset_name): called when any key in the active chord is released.
    """
    COMMIT_DELAY = 0.08

    def __init__(self, hotkey_map, on_activate, on_release):
        self.on_activate = on_activate
        self.on_release = on_release
        self.chords = []
        for hk_str, preset in (hotkey_map or {}).items():
            keys = self._parse_hotkey(hk_str)
            if keys:
                self.chords.append((frozenset(keys), preset, hk_str))
        self.chords.sort(key=lambda c: -len(c[0]))
        self._longest_len = max((len(c[0]) for c in self.chords), default=0)
        self.pressed_keys = set()
        self.active_chord = None
        self._pending_timer = None
        self.listener = None

    def _parse_hotkey(self, s):
        keys = set()
        km = {"<cmd>": keyboard.Key.cmd, "<alt>": keyboard.Key.alt, "<ctrl>": keyboard.Key.ctrl,
              "<shift>": keyboard.Key.shift, "<alt_l>": keyboard.Key.alt_l, "<alt_r>": keyboard.Key.alt_r,
              "<ctrl_l>": keyboard.Key.ctrl_l, "<ctrl_r>": keyboard.Key.ctrl_r,
              "<cmd_l>": keyboard.Key.cmd_l, "<cmd_r>": keyboard.Key.cmd_r}
        for p in (s or "").lower().split("+"):
            p = p.strip()
            if not p:
                continue
            if p in km:
                keys.add(km[p])
            elif len(p) == 1:
                keys.add(keyboard.KeyCode.from_char(p))
        return keys

    def _norm(self, key):
        v = {keyboard.Key.alt_l: keyboard.Key.alt, keyboard.Key.alt_r: keyboard.Key.alt,
             keyboard.Key.ctrl_l: keyboard.Key.ctrl, keyboard.Key.ctrl_r: keyboard.Key.ctrl,
             keyboard.Key.cmd_l: keyboard.Key.cmd, keyboard.Key.cmd_r: keyboard.Key.cmd,
             keyboard.Key.shift_l: keyboard.Key.shift, keyboard.Key.shift_r: keyboard.Key.shift}
        return v.get(key, key)

    def _find_longest_match(self):
        for keyset, preset, _ in self.chords:
            if keyset.issubset(self.pressed_keys):
                return (keyset, preset)
        return None

    def _cancel_pending(self):
        if self._pending_timer:
            try: self._pending_timer.cancel()
            except Exception: pass
            self._pending_timer = None

    def _fire(self, match):
        self._pending_timer = None
        if self.active_chord is not None:
            return
        current = self._find_longest_match()
        if current is None:
            return
        self.active_chord = current
        try: self.on_activate(current[1])
        except Exception as e: print(f"  [hotkey] on_activate error: {e}")

    def _on_press(self, key):
        key = self._norm(key)
        self.pressed_keys.add(key)
        if self.active_chord is not None:
            return
        match = self._find_longest_match()
        if match is None:
            return
        self._cancel_pending()
        if len(match[0]) < self._longest_len:
            self._pending_timer = threading.Timer(self.COMMIT_DELAY, lambda m=match: self._fire(m))
            self._pending_timer.daemon = True
            self._pending_timer.start()
        else:
            self._fire(match)

    def _on_release(self, key):
        key = self._norm(key)
        if self.active_chord and key in self.active_chord[0]:
            preset = self.active_chord[1]
            self.active_chord = None
            self._cancel_pending()
            try: self.on_release(preset)
            except Exception as e: print(f"  [hotkey] on_release error: {e}")
        self.pressed_keys.discard(key)
        if self.active_chord is None and not self.pressed_keys:
            self._cancel_pending()

    def start(self):
        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.start()

    def stop(self):
        self._cancel_pending()
        if self.listener:
            self.listener.stop()

class StatusOverlay:
    """Pill-shaped floating status. Uses voicerefine_ui design tokens + animated waveform bars."""
    def __init__(self,config):
        self.config=config;self.root=None;self.label=None;self.canvas=None;self.dots_after=None
        self.dot_count=0;self._wf=None;self.active=False
        try:
            from voicerefine_ui import palette as _pal, font as _font, TOKENS as _TOK, WaveformBars as _WF
            self._pal=_pal(config.get("theme","dark"));self._font=_font;self._TOK=_TOK;self._WF=_WF
            self._USE_UI=True
        except ImportError:
            self._pal=THEMES.get(config.get("theme","dark"),THEMES["dark"])
            self._font=lambda s=12,w="normal",family=None:(family or "Segoe UI", s, w)
            class _T: space_2=8; space_3=12; space_4=16
            self._TOK=_T(); self._WF=None; self._USE_UI=False
        # Adapt theme keys: voicerefine_ui uses 'text','rec','done','thinking','error','surface','border'
        # Old THEMES uses 'fg','recording','done','thinking','error','panel','border'
        self._k_text   = "text"     if self._USE_UI else "fg"
        self._k_bg     = "bg"
        self._k_panel  = "surface"  if self._USE_UI else "panel"
        self._k_border = "border"
        self._k_rec    = "rec"      if self._USE_UI else "recording"
        self._k_think  = "thinking"
        self._k_done   = "done"
        self._k_err    = "error"
        self._k_subtle = "text_subtle" if self._USE_UI else "subtle"

    def _create_window(self):
        if self.root and self.root.winfo_exists(): return
        self.root=tk.Tk();self.root.withdraw();self.root.overrideredirect(True);self.root.attributes("-topmost",True)
        try: self.root.attributes("-alpha",min(self.config.get("window_opacity",0.96),0.94))
        except Exception: pass
        try: self.root.attributes("-toolwindow",True)
        except Exception: pass
        self.root.configure(bg=self._pal[self._k_bg if self._k_bg in self._pal else "bg"])
        # Outer pill: a thick-bordered Frame with extra padding for a chip feel
        outer=tk.Frame(self.root,bg=self._pal[self._k_panel],
                       highlightbackground=self._pal[self._k_border],
                       highlightthickness=1,bd=0)
        outer.pack(fill="both",expand=True)
        inner=tk.Frame(outer,bg=self._pal[self._k_panel],padx=self._TOK.space_4,pady=self._TOK.space_3)
        inner.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(inner,width=18,height=18,bg=self._pal[self._k_panel],highlightthickness=0,bd=0)
        self.canvas.pack(side="left",padx=(0,self._TOK.space_3))
        self.label=tk.Label(inner,text="",fg=self._pal[self._k_text],bg=self._pal[self._k_panel],
                            font=self._font(12,"bold") if sys.platform=="win32" else ("Helvetica",12,"bold"),anchor="w")
        self.label.pack(side="left",fill="x",expand=True)
        self.wf_holder=tk.Frame(inner,bg=self._pal[self._k_panel])
        self.wf_holder.pack(side="right",padx=(self._TOK.space_3,0))
        if self._WF is not None:
            self._wf=self._WF(self.wf_holder,theme=self.config.get("theme","dark"),
                             bars=14,width=150,height=22,
                             idle_color=self._pal[self._k_border],
                             active_color=self._pal[self._k_rec])
            self._wf.canvas.configure(bg=self._pal[self._k_panel])
            self._wf.canvas.pack()

    def _position_window(self):
        if not self.root: return
        pos=self.config.get("overlay_position","bottom-center");self.root.update_idletasks()
        w=max(self.root.winfo_width(),360);h=self.root.winfo_height();sw=self.root.winfo_screenwidth();sh=self.root.winfo_screenheight();m=24
        ps={
            "bottom-right":(sw-w-m,sh-h-m-50),
            "bottom-left":(m,sh-h-m-50),
            "bottom-center":(sw//2-w//2,sh-h-m-50),
            "top-right":(sw-w-m,m),
            "top-left":(m,m),
            "top-center":(sw//2-w//2,m),
            "center":(sw//2-w//2,sh//2-h//2),
        }
        x,y=ps.get(pos,ps["bottom-center"])
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _state_color(self,state):
        return {
            "recording": self._pal[self._k_rec],
            "thinking":  self._pal[self._k_think],
            "done":      self._pal[self._k_done],
            "error":     self._pal[self._k_err],
        }.get(state,self._pal[self._k_text])

    def show(self,state,text="",level=0):
        if not self.config.get("show_overlay",True): return
        def _do():
            self._create_window()
            color=self._state_color(state)
            self.canvas.delete("all")
            if state=="recording":
                # Filled dot with subtle outer ring
                self.canvas.create_oval(3,3,15,15,fill=color,outline="")
                self.canvas.create_oval(1,1,17,17,outline=color,width=1)
            elif state=="thinking":
                self.canvas.create_oval(3,3,15,15,outline=color,width=2)
                self.canvas.create_arc(3,3,15,15,start=0,extent=120,outline=color,style="arc",width=2)
            elif state=="done":
                self.canvas.create_oval(1,1,17,17,outline=color,width=1)
                self.canvas.create_line(4,9,8,13,fill=color,width=2,capstyle="round")
                self.canvas.create_line(8,13,14,5,fill=color,width=2,capstyle="round")
            elif state=="error":
                self.canvas.create_line(4,4,14,14,fill=color,width=2,capstyle="round")
                self.canvas.create_line(14,4,4,14,fill=color,width=2,capstyle="round")
            self.label.configure(text=text,fg=color)
            if state=="recording" and self._wf is not None:
                self._wf.set_level(level,"recording")
                self.wf_holder.pack(side="right",padx=(self._TOK.space_3,0))
            else:
                if state!="recording" and self._wf is not None:
                    self.wf_holder.pack_forget()
            self._position_window();self.root.deiconify();self.active=True
            if self.dots_after:
                try: self.root.after_cancel(self.dots_after)
                except Exception: pass
                self.dots_after=None
            if state in("done","error"):
                self.dots_after=self.root.after(self.config.get("overlay_duration",3)*1000,self.hide)
        if self.root: self.root.after(0,_do)
        else: _do()

    def update_recording(self,duration,level):
        def _do():
            if not self.active or not self.label: return
            self.label.configure(text=f"Recording  {duration:.1f}s")
            if self._wf is not None: self._wf.set_level(level,"recording")
        if self.root: self.root.after(0,_do)

    def animate_thinking(self):
        def _do():
            if not self.active or not self.label: return
            self.dot_count=(self.dot_count+1)%4
            self.label.configure(text=f"Refining{'.'*self.dot_count}")
            self.dots_after=self.root.after(360,self.animate_thinking)
        if self.root: self.root.after(0,_do)

    def hide(self):
        def _do():
            if self.root and self.root.winfo_exists(): self.root.withdraw()
            self.active=False
        if self.root: self.root.after(0,_do)

    def run_loop(self):
        if not HAS_TK: return
        self._create_window();self.root.withdraw();self.root.mainloop()

    def quit(self):
        if self.root: self.root.after(0,self.root.quit)

def create_tray_icon_image(color,size=64):
    try:
        from PIL import Image,ImageDraw
        if APP_ICON_PATH.exists():
            img=Image.open(APP_ICON_PATH).convert("RGBA").resize((size,size))
            draw=ImageDraw.Draw(img)
            r=max(size//7,6)
            draw.ellipse([size-r*2-2,size-r*2-2,size-2,size-2],fill=color,outline=(11,11,12,230),width=2)
            return img
        img=Image.new("RGBA",(size,size),(0,0,0,0));draw=ImageDraw.Draw(img)
        draw.ellipse([4,4,size-4,size-4],fill=color,outline=color)
        cx,cy=size//2,size//2;mc=(255,255,255,220)
        draw.rounded_rectangle([cx-6,cy-14,cx+6,cy+4],radius=6,fill=mc)
        draw.arc([cx-10,cy-8,cx+10,cy+8],0,180,fill=mc,width=2)
        draw.line([cx,cy+8,cx,cy+14],fill=mc,width=2);draw.line([cx-6,cy+14,cx+6,cy+14],fill=mc,width=2)
        return img
    except ImportError: return None

class TrayIcon:
    """Rich tray icon — dynamic menu with last-capture preview, pause toggle, today stats."""
    def __init__(self,on_settings,on_history,on_quit,
                 on_pause_toggle=None,get_paused=None,
                 get_last_preview=None,get_today_stats=None):
        self.on_settings=on_settings;self.on_history=on_history;self.on_quit=on_quit
        self.on_pause_toggle=on_pause_toggle or (lambda: None)
        self.get_paused=get_paused or (lambda: False)
        self.get_last_preview=get_last_preview or (lambda: "")
        self.get_today_stats=get_today_stats or (lambda: (0,0))
        self.icon=None;self.running=False;self._state="idle"

    def start(self):
        try:
            import pystray;from PIL import Image
        except ImportError: print("  [Tray] pystray/Pillow not installed.");return
        idle_img=create_tray_icon_image((100,100,100))

        def _menu_factory():
            # Called every time the menu is opened — values are fresh.
            preview=self.get_last_preview() or ""
            if preview:
                preview=(preview[:46] + ("…" if len(preview)>46 else ""))
                preview_label=f"Last  ·  {preview}"
            else:
                preview_label="Last  ·  (no captures yet)"
            paused=bool(self.get_paused())
            captures,words=self.get_today_stats()
            today_label=f"Today  ·  {captures} captures  ·  {words} words"
            return pystray.Menu(
                pystray.MenuItem(preview_label, None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Resume hotkeys" if paused else "Pause hotkeys",
                    lambda: self.on_pause_toggle()
                ),
                pystray.MenuItem("Settings", lambda: self.on_settings()),
                pystray.MenuItem("History", lambda: self.on_history()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(today_label, None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("CK42X.com", lambda: open_url(CK42X_URL)),
                pystray.MenuItem("Quit", lambda: self.on_quit()),
            )

        self.icon=pystray.Icon("VoiceRefine",idle_img,"VoiceRefine — Ready",menu=_menu_factory)
        self.running=True
        threading.Thread(target=self.icon.run,daemon=True).start()

    def set_state(self,state):
        if not self.icon: return
        self._state=state
        cs={"idle":(100,100,100),"recording":(233,69,96),"thinking":(255,179,0),
            "done":(78,204,163),"error":(255,107,107),"paused":(140,140,148)}
        ts={"idle":"VoiceRefine — Ready","recording":"VoiceRefine — Recording…",
            "thinking":"VoiceRefine — Refining…","done":"VoiceRefine — Copied!",
            "error":"VoiceRefine — Error","paused":"VoiceRefine — Paused"}
        img=create_tray_icon_image(cs.get(state,cs["idle"]))
        if img: self.icon.icon=img
        self.icon.title=ts.get(state,ts["idle"])

    def refresh_menu(self):
        """Force pystray to re-evaluate the menu factory."""
        try:
            if self.icon: self.icon.update_menu()
        except Exception: pass

    def stop(self):
        if self.icon: self.icon.stop()

class SettingsWindow:
    def __init__(self,config,on_save,first_run=False):
        self.config=config.copy();self.on_save=on_save;self.first_run=first_run;self._theme=THEMES.get(config.get("theme","dark"),THEMES["dark"]);self._photos=[]
    def _button(self,parent,text,command,kind="secondary"):
        colors={"primary":(self._theme["button"],self._theme["button_fg"]),"secondary":(self._theme["panel2"],self._theme["fg"]),"danger":(self._theme["error"],"#ffffff")}
        bg,fg=colors.get(kind,colors["secondary"])
        return tk.Button(parent,text=text,command=command,bg=bg,fg=fg,activebackground=bg,activeforeground=fg,relief="flat",bd=0,padx=14,pady=8,font=("Segoe UI",9,"bold"),cursor="hand2")
    def _entry(self,parent,**kw):
        return tk.Entry(parent,bg=self._theme["input_bg"],fg=self._theme["input_fg"],insertbackground=self._theme["fg"],relief="flat",highlightthickness=1,highlightbackground=self._theme["border"],highlightcolor=self._theme["accent"],**kw)
    def _label(self,parent,text,**kw):
        return tk.Label(parent,text=text,bg=self._theme["panel"],fg=self._theme["fg"],font=("Segoe UI",10),**kw)
    def _subtle(self,parent,text,**kw):
        return tk.Label(parent,text=text,bg=self._theme["panel"],fg=self._theme["subtle"],font=("Segoe UI",9),**kw)
    def show(self):
        if not HAS_TK: print("tkinter not available.");return
        root=tk.Toplevel() if hasattr(tk,'_default_root') and tk._default_root else tk.Tk()
        root.title("VoiceRefine Setup" if self.first_run else "VoiceRefine Settings");root.geometry("760x680");root.minsize(720,620);root.resizable(True,True)
        apply_window_chrome(root,self._theme,self.config.get("window_opacity",0.96))

        shell=tk.Frame(root,bg=self._theme["bg"],padx=16,pady=16);shell.pack(fill="both",expand=True)
        header=tk.Frame(shell,bg=self._theme["panel"],highlightbackground=self._theme["border"],highlightthickness=1,padx=18,pady=16);header.pack(fill="x",pady=(0,12))
        icon=load_icon_photo(48)
        if icon:
            self._photos.append(icon);tk.Label(header,image=icon,bg=self._theme["panel"]).pack(side="left",padx=(0,14))
        title_box=tk.Frame(header,bg=self._theme["panel"]);title_box.pack(side="left",fill="x",expand=True)
        tk.Label(title_box,text=APP_NAME,fg=self._theme["fg"],bg=self._theme["panel"],font=("Segoe UI",18,"bold")).pack(anchor="w")
        subtitle="Paste your OpenAI key once, then hold the hotkey and talk." if self.first_run else "Press to talk. Paste polished."
        tk.Label(title_box,text=subtitle,fg=self._theme["subtle"],bg=self._theme["panel"],font=("Segoe UI",10)).pack(anchor="w",pady=(2,0))
        link_box=tk.Frame(header,bg=self._theme["panel"]);link_box.pack(side="right")
        self._button(link_box,"CK42X",lambda:open_url(CK42X_URL)).pack(side="top",fill="x",pady=(0,6))
        self._button(link_box,"Get API key",lambda:open_url(OPENAI_KEYS_URL),"primary").pack(side="top",fill="x")

        style=ttk.Style();style.theme_use("clam")
        style.configure("Custom.TNotebook",background=self._theme["bg"],borderwidth=0)
        style.configure("Custom.TNotebook.Tab",background=self._theme["panel2"],foreground=self._theme["fg"],padding=[16,8],borderwidth=0)
        style.map("Custom.TNotebook.Tab",background=[("selected",self._theme["accent"])],foreground=[("selected",self._theme["button_fg"])])
        style.configure("Custom.TFrame",background=self._theme["panel"])
        style.configure("Custom.TLabel",background=self._theme["panel"],foreground=self._theme["fg"])
        style.configure("Custom.TCheckbutton",background=self._theme["panel"],foreground=self._theme["fg"])

        nb=ttk.Notebook(shell,style="Custom.TNotebook");nb.pack(fill="both",expand=True)

        af=ttk.Frame(nb,style="Custom.TFrame",padding=22);nb.add(af,text="API")
        af.columnconfigure(1,weight=1)
        status_text="API key required" if not has_api_key(self.config) else "API key saved"
        status_fg=self._theme["error"] if not has_api_key(self.config) else self._theme["success"]
        tk.Label(af,text=status_text,fg=status_fg,bg=self._theme["panel"],font=("Segoe UI",11,"bold")).grid(row=0,column=0,columnspan=3,sticky="w",pady=(0,8))
        self._subtle(af,"Your key is stored locally in config.json. You can also set OPENAI_API_KEY instead.",wraplength=640,justify="left").grid(row=1,column=0,columnspan=3,sticky="w",pady=(0,16))
        self._label(af,"OpenAI API Key").grid(row=2,column=0,sticky="w",pady=8)
        api_var=tk.StringVar(value=self.config.get("openai_api_key",""))
        api_entry=self._entry(af,textvariable=api_var,width=50,show="*")
        api_entry.grid(row=2,column=1,sticky="ew",padx=(12,8),pady=8,ipady=7)
        show_key=tk.BooleanVar(value=False)
        def toggle_key():
            show_key.set(not show_key.get());api_entry.configure(show="" if show_key.get() else "*");show_btn.configure(text="Hide" if show_key.get() else "Show")
        show_btn=self._button(af,"Show",toggle_key);show_btn.grid(row=2,column=2,sticky="ew",pady=8)
        env_key=os.environ.get("OPENAI_API_KEY","").strip()
        env_msg="OPENAI_API_KEY is available and will be used if the field is empty." if env_key else "No OPENAI_API_KEY environment variable detected."
        self._subtle(af,env_msg,wraplength=640,justify="left").grid(row=3,column=1,columnspan=2,sticky="w",padx=(12,0),pady=(0,12))
        self._label(af,"GPT Model").grid(row=4,column=0,sticky="w",pady=8)
        model_var=tk.StringVar(value=self.config.get("model","gpt-4o-mini"))
        ttk.Combobox(af,textvariable=model_var,values=["gpt-4o-mini","gpt-4o","gpt-4.1-mini","gpt-4.1","gpt-4-turbo"],width=42).grid(row=4,column=1,columnspan=2,sticky="ew",padx=(12,0),pady=8)
        self._label(af,"Whisper Model").grid(row=5,column=0,sticky="w",pady=8)
        whisper_var=tk.StringVar(value=self.config.get("whisper_model","whisper-1"))
        self._entry(af,textvariable=whisper_var,width=50).grid(row=5,column=1,columnspan=2,sticky="ew",padx=(12,0),pady=8,ipady=7)
        self._label(af,"Input device").grid(row=6,column=0,sticky="w",pady=8)
        input_devices=get_input_devices()
        device_labels=["System default"]+[f"{idx}: {name}" for idx,name in input_devices]
        if not input_devices: device_labels=["No input devices found"]
        configured_device=normalize_input_device(self.config.get("input_device"))
        configured_label=next((f"{idx}: {name}" for idx,name in input_devices if idx==configured_device),device_labels[0])
        input_device_var=tk.StringVar(value=configured_label)
        ttk.Combobox(af,textvariable=input_device_var,values=device_labels,width=42,state="readonly").grid(row=6,column=1,columnspan=2,sticky="ew",padx=(12,0),pady=8)
        mic_msg="No microphone input devices were detected. Enable one in Windows Sound settings, then reopen VoiceRefine." if not input_devices else "Leave this on System default unless VoiceRefine is listening to the wrong microphone."
        self._subtle(af,mic_msg,wraplength=640,justify="left").grid(row=7,column=1,columnspan=2,sticky="w",padx=(12,0),pady=(0,12))
        tip=tk.Frame(af,bg=self._theme["panel2"],highlightbackground=self._theme["border"],highlightthickness=1,padx=14,pady=12);tip.grid(row=8,column=0,columnspan=3,sticky="ew",pady=(18,0))
        tk.Label(tip,text="First run flow",fg=self._theme["accent"],bg=self._theme["panel2"],font=("Segoe UI",10,"bold")).pack(anchor="w")
        tk.Label(tip,text="1. Create or copy an OpenAI API key.  2. Paste it here.  3. Save and VoiceRefine starts cleanly.",fg=self._theme["subtle"],bg=self._theme["panel2"],font=("Segoe UI",9),wraplength=650,justify="left").pack(anchor="w",pady=(4,0))
        if self.first_run: root.after(250,api_entry.focus_set)

        # --- Prompt / Presets tab ---
        pf=ttk.Frame(nb,style="Custom.TFrame",padding=22);nb.add(pf,text="Prompt")
        presets_state={k:str(v) for k,v in (self.config.get("presets") or {}).items()}
        if "default" not in presets_state:
            presets_state["default"]=self.config.get("prompt",DEFAULT_CONFIG["prompt"])
        preset_hotkeys_state=dict(self.config.get("preset_hotkeys") or {})

        top=tk.Frame(pf,bg=self._theme["panel"]);top.pack(fill="x",pady=(0,10))
        self._label(top,"Edit preset").pack(side="left",padx=(0,8))
        active_preset_var=tk.StringVar(value=self.config.get("active_preset","default"))
        preset_picker=ttk.Combobox(top,textvariable=active_preset_var,values=sorted(presets_state.keys()),width=24,state="readonly")
        preset_picker.pack(side="left")
        def add_preset():
            from tkinter import simpledialog
            name=simpledialog.askstring("New preset","Preset name (letters, numbers, dashes):",parent=top)
            if not name: return
            name="".join(c for c in name.strip().lower() if c.isalnum() or c=="-")
            if not name or name in presets_state: return
            presets_state[name]=presets_state.get(active_preset_var.get(),DEFAULT_CONFIG["prompt"])
            preset_picker["values"]=sorted(presets_state.keys())
            active_preset_var.set(name);_load_preset_into_editor()
        def del_preset():
            n=active_preset_var.get()
            if n=="default":
                messagebox.showinfo("Can't delete","The 'default' preset cannot be deleted.");return
            if not messagebox.askyesno("Delete preset",f"Delete preset '{n}'?"): return
            presets_state.pop(n,None)
            # Drop any hotkey bound to this preset
            for hk in list(preset_hotkeys_state.keys()):
                if preset_hotkeys_state[hk]==n: preset_hotkeys_state.pop(hk,None)
            _rebuild_hotkey_rows()
            preset_picker["values"]=sorted(presets_state.keys())
            active_preset_var.set("default");_load_preset_into_editor()
        self._button(top,"+ New",add_preset).pack(side="left",padx=(8,4))
        self._button(top,"Delete",del_preset,"danger").pack(side="left")

        prompt_text=tk.Text(pf,width=60,height=11,wrap="word",bg=self._theme["input_bg"],fg=self._theme["input_fg"],insertbackground=self._theme["fg"],relief="flat",highlightthickness=1,highlightbackground=self._theme["border"],highlightcolor=self._theme["accent"],font=("Consolas",10) if sys.platform=="win32" else ("Courier",10),padx=10,pady=10)
        prompt_text.pack(fill="both",expand=True)
        _current_loaded={"name":active_preset_var.get()}
        def _stash_current_editor():
            n=_current_loaded["name"]
            if n: presets_state[n]=prompt_text.get("1.0","end").strip()
        def _load_preset_into_editor():
            n=active_preset_var.get();_current_loaded["name"]=n
            prompt_text.delete("1.0","end");prompt_text.insert("1.0",presets_state.get(n,""))
        def _on_preset_change(_e=None):
            _stash_current_editor()
            _load_preset_into_editor()
        preset_picker.bind("<<ComboboxSelected>>",_on_preset_change)
        _load_preset_into_editor()
        self._subtle(pf,"Switching presets auto-saves the editor. Click Save (bottom) to persist.",wraplength=640,justify="left").pack(anchor="w",pady=(8,0))

        # --- Hotkeys tab (per-preset bindings) ---
        hf=ttk.Frame(nb,style="Custom.TFrame",padding=22);nb.add(hf,text="Hotkeys")
        hf.columnconfigure(1,weight=1)
        self._label(hf,"Bind a hotkey to each preset").grid(row=0,column=0,columnspan=3,sticky="w",pady=(0,4))
        self._subtle(hf,"Hold to record. Use <cmd>, <alt>, <ctrl>, <shift>, plus an optional letter (e.g. <cmd>+<alt>+c). Leave blank to unbind.",wraplength=640,justify="left").grid(row=1,column=0,columnspan=3,sticky="w",pady=(0,12))
        hotkey_rows_frame=tk.Frame(hf,bg=self._theme["panel"]);hotkey_rows_frame.grid(row=2,column=0,columnspan=3,sticky="ew")
        hotkey_row_vars={}  # preset_name -> StringVar(hotkey)
        def _rebuild_hotkey_rows():
            for w in hotkey_rows_frame.winfo_children(): w.destroy()
            hotkey_row_vars.clear()
            preset_to_hotkey={p:hk for hk,p in preset_hotkeys_state.items()}
            for i,p in enumerate(sorted(presets_state.keys())):
                self._label(hotkey_rows_frame,p).grid(row=i,column=0,sticky="w",padx=(0,12),pady=4)
                v=tk.StringVar(value=preset_to_hotkey.get(p,""))
                self._entry(hotkey_rows_frame,textvariable=v,width=32).grid(row=i,column=1,sticky="w",pady=4,ipady=5)
                hotkey_row_vars[p]=v
        _rebuild_hotkey_rows()
        auto_paste_var=tk.BooleanVar(value=self.config.get("auto_paste",False))
        ttk.Checkbutton(hf,text="Auto-paste after copying with Ctrl+V",variable=auto_paste_var,style="Custom.TCheckbutton").grid(row=3,column=0,columnspan=3,sticky="w",pady=(18,4))

        apf=ttk.Frame(nb,style="Custom.TFrame",padding=22);nb.add(apf,text="Appearance")
        apf.columnconfigure(1,weight=1)
        overlay_var=tk.BooleanVar(value=self.config.get("show_overlay",True))
        ttk.Checkbutton(apf,text="Show floating status overlay",variable=overlay_var,style="Custom.TCheckbutton").grid(row=0,column=0,columnspan=2,sticky="w",pady=8)
        self._label(apf,"Overlay position").grid(row=1,column=0,sticky="w",pady=8)
        pos_var=tk.StringVar(value=self.config.get("overlay_position","bottom-right"))
        ttk.Combobox(apf,textvariable=pos_var,values=["bottom-right","bottom-left","top-right","top-left","center"],width=22).grid(row=1,column=1,sticky="w",padx=(12,0),pady=8)
        self._label(apf,"Overlay duration").grid(row=2,column=0,sticky="w",pady=8)
        dur_var=tk.IntVar(value=self.config.get("overlay_duration",3))
        ttk.Spinbox(apf,from_=1,to=10,textvariable=dur_var,width=6).grid(row=2,column=1,sticky="w",padx=(12,0),pady=8)
        self._label(apf,"Theme").grid(row=3,column=0,sticky="w",pady=8)
        theme_var=tk.StringVar(value=self.config.get("theme","dark"))
        ttk.Combobox(apf,textvariable=theme_var,values=["dark","light"],width=12).grid(row=3,column=1,sticky="w",padx=(12,0),pady=8)
        self._label(apf,"Window opacity").grid(row=4,column=0,sticky="w",pady=8)
        opacity_var=tk.DoubleVar(value=self.config.get("window_opacity",0.96))
        ttk.Scale(apf,from_=0.86,to=1.0,variable=opacity_var,orient="horizontal").grid(row=4,column=1,sticky="ew",padx=(12,0),pady=8)
        self._subtle(apf,"Lower values make Settings, History, and the overlay more transparent.",wraplength=620,justify="left").grid(row=5,column=0,columnspan=2,sticky="w",pady=(0,8))

        # --- Backend tab (transcription engine) ---
        bef=ttk.Frame(nb,style="Custom.TFrame",padding=22);nb.add(bef,text="Backend")
        bef.columnconfigure(1,weight=1)
        self._label(bef,"Transcription engine").grid(row=0,column=0,sticky="w",pady=8)
        backend_var=tk.StringVar(value=self.config.get("transcription_backend","openai"))
        ttk.Combobox(bef,textvariable=backend_var,values=["openai","auto","local"],width=22,state="readonly").grid(row=0,column=1,sticky="w",padx=(12,0),pady=8)
        self._subtle(bef,"openai = cloud Whisper API. local = faster-whisper on this PC (requires `pip install faster-whisper`). auto = try local first, fall back to OpenAI.",wraplength=640,justify="left").grid(row=1,column=0,columnspan=2,sticky="w",pady=(0,12))
        self._label(bef,"Local model size").grid(row=2,column=0,sticky="w",pady=8)
        local_size_var=tk.StringVar(value=self.config.get("local_model_size","base"))
        ttk.Combobox(bef,textvariable=local_size_var,values=["tiny","base","small","medium","large-v3"],width=22,state="readonly").grid(row=2,column=1,sticky="w",padx=(12,0),pady=8)
        try:
            from voicerefine_local_whisper import is_available as _lw_avail
            lw_ok=_lw_avail()
        except Exception: lw_ok=False
        lw_status_text="faster-whisper installed and available." if lw_ok else "faster-whisper not installed. Run: pip install faster-whisper"
        lw_status_fg=self._theme["success"] if lw_ok else self._theme["subtle"]
        tk.Label(bef,text=lw_status_text,fg=lw_status_fg,bg=self._theme["panel"],font=("Segoe UI",9),wraplength=640,justify="left").grid(row=3,column=0,columnspan=2,sticky="w",pady=(8,0))

        # --- Vault tab ---
        vf=ttk.Frame(nb,style="Custom.TFrame",padding=22);nb.add(vf,text="Vault")
        vf.columnconfigure(1,weight=1)
        vault_enabled_var=tk.BooleanVar(value=self.config.get("vault_enabled",False))
        ttk.Checkbutton(vf,text="Write each capture to an Obsidian vault",variable=vault_enabled_var,style="Custom.TCheckbutton").grid(row=0,column=0,columnspan=3,sticky="w",pady=(0,8))
        self._subtle(vf,"Captures land at vault/11-Data/<category>/YYYY/MM/<id>.json + .md, matching the PersonalData intake schema, with an entry appended to 11-Data/_index.jsonl.",wraplength=640,justify="left").grid(row=1,column=0,columnspan=3,sticky="w",pady=(0,12))
        self._label(vf,"Vault root").grid(row=2,column=0,sticky="w",pady=8)
        vault_path_var=tk.StringVar(value=self.config.get("vault_path",""))
        self._entry(vf,textvariable=vault_path_var,width=42).grid(row=2,column=1,sticky="ew",padx=(12,8),pady=8,ipady=6)
        def _browse_vault():
            try:
                from tkinter import filedialog
                p=filedialog.askdirectory(title="Select vault root (folder containing 11-Data/)")
                if p: vault_path_var.set(p)
            except Exception as e: messagebox.showerror("Browse",str(e))
        self._button(vf,"Browse",_browse_vault).grid(row=2,column=2,sticky="ew",pady=8)
        self._label(vf,"Category").grid(row=3,column=0,sticky="w",pady=8)
        vault_category_var=tk.StringVar(value=self.config.get("vault_category","voice-captures"))
        self._entry(vf,textvariable=vault_category_var,width=42).grid(row=3,column=1,columnspan=2,sticky="ew",padx=(12,0),pady=8,ipady=6)
        self._subtle(vf,"Subfolder under 11-Data/. Letters, digits, dashes only. Defaults to voice-captures.",wraplength=640,justify="left").grid(row=4,column=0,columnspan=3,sticky="w",pady=(0,8))

        bf=tk.Frame(shell,bg=self._theme["bg"]);bf.pack(fill="x",pady=(12,0))
        status=tk.Label(bf,text="",bg=self._theme["bg"],fg=self._theme["subtle"],font=("Segoe UI",9));status.pack(side="left")
        def on_save():
            selected_device=None
            if input_device_var.get() and input_device_var.get()[0].isdigit():
                selected_device=int(input_device_var.get().split(":",1)[0])
            # Stash the currently-edited preset back into presets_state
            _stash_current_editor()
            # Build the canonical preset_hotkeys map from the per-preset rows
            new_preset_hotkeys={}
            for preset_name,hk_var in hotkey_row_vars.items():
                hk=(hk_var.get() or "").strip()
                if hk: new_preset_hotkeys[hk]=preset_name
            # Legacy 'hotkey' for fallback compat
            legacy_hotkey=next((hk for hk,p in new_preset_hotkeys.items() if p=="default"),self.config.get("hotkey","<cmd>+<alt>"))
            self.config.update({
                "openai_api_key":api_var.get().strip(),
                "model":model_var.get().strip(),
                "whisper_model":whisper_var.get().strip(),
                "input_device":selected_device,
                "hotkey":legacy_hotkey,
                "prompt":presets_state.get("default",_DEFAULT_PROMPT),
                "presets":dict(presets_state),
                "preset_hotkeys":new_preset_hotkeys,
                "active_preset":active_preset_var.get(),
                "show_overlay":overlay_var.get(),
                "overlay_position":pos_var.get(),
                "overlay_duration":dur_var.get(),
                "window_opacity":round(float(opacity_var.get()),2),
                "auto_paste":auto_paste_var.get(),
                "theme":theme_var.get(),
                "transcription_backend":backend_var.get(),
                "local_model_size":local_size_var.get(),
                "vault_enabled":vault_enabled_var.get(),
                "vault_path":vault_path_var.get().strip(),
                "vault_category":(vault_category_var.get().strip() or "voice-captures"),
            })
            save_config(self.config)
            if self.on_save: self.on_save(self.config)
            status.configure(text="Saved. VoiceRefine is ready.",fg=self._theme["success"])
            if self.first_run: root.after(350,root.destroy)
            else: messagebox.showinfo("Saved","Settings saved.");root.destroy()
        self._button(bf,"Cancel",root.destroy).pack(side="right",padx=(8,0))
        self._button(bf,"Save and start" if self.first_run else "Save",on_save,"primary").pack(side="right")

class HistoryWindow:
    def __init__(self,config): self._theme=THEMES.get(config.get("theme","dark"),THEMES["dark"])
    def show(self):
        if not HAS_TK: return
        history=load_history()
        root=tk.Toplevel() if hasattr(tk,'_default_root') and tk._default_root else tk.Tk()
        root.title("VoiceRefine History");root.geometry("760x540");apply_window_chrome(root,self._theme,load_config().get("window_opacity",0.96))
        hdr=tk.Frame(root,bg=self._theme["panel"],highlightbackground=self._theme["border"],highlightthickness=1,padx=16,pady=12);hdr.pack(fill="x",padx=12,pady=12)
        icon=load_icon_photo(34)
        if icon:
            root._vr_icon=icon;tk.Label(hdr,image=icon,bg=self._theme["panel"]).pack(side="left",padx=(0,10))
        title_box=tk.Frame(hdr,bg=self._theme["panel"]);title_box.pack(side="left",fill="x",expand=True)
        tk.Label(title_box,text=f"History ({len(history)} entries)",fg=self._theme["accent"],bg=self._theme["panel"],font=("Segoe UI",13,"bold")).pack(anchor="w")
        tk.Label(title_box,text="Search, copy, and reuse polished dictations.",fg=self._theme["subtle"],bg=self._theme["panel"],font=("Segoe UI",9)).pack(anchor="w")
        def clr():
            if messagebox.askyesno("Clear","Clear all history?"): save_history([]);root.destroy()
        tk.Button(hdr,text="CK42X",command=lambda:open_url(CK42X_URL),bg=self._theme["panel2"],fg=self._theme["fg"],relief="flat",padx=12,pady=7,cursor="hand2").pack(side="right",padx=(8,0))
        tk.Button(hdr,text="Clear All",command=clr,bg=self._theme["error"],fg="#fff",relief="flat",padx=12,pady=7,cursor="hand2").pack(side="right")
        cv=tk.Canvas(root,bg=self._theme["bg"],highlightthickness=0);sb=ttk.Scrollbar(root,orient="vertical",command=cv.yview)
        sf=tk.Frame(cv,bg=self._theme["bg"]);sf.bind("<Configure>",lambda e:cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0,0),window=sf,anchor="nw");cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left",fill="both",expand=True,padx=10,pady=10);sb.pack(side="right",fill="y")
        for entry in reversed(history):
            card=tk.Frame(sf,bg=self._theme["panel"],highlightbackground=self._theme["border"],highlightthickness=1,padx=12,pady=8);card.pack(fill="x",pady=4,padx=4)
            tk.Label(card,text=entry.get("timestamp",""),fg=self._theme["accent"],bg=self._theme["panel"],font=("Segoe UI",8)).pack(anchor="w")
            tk.Label(card,text=f"Raw: {entry.get('raw','')[:100]}",fg="#888",bg=self._theme["panel"],font=("Segoe UI",9),wraplength=600,justify="left").pack(anchor="w",pady=(2,0))
            improved=entry.get("improved","")
            tk.Label(card,text=improved[:200],fg=self._theme["fg"],bg=self._theme["panel"],font=("Segoe UI",10),wraplength=600,justify="left").pack(anchor="w",pady=(2,0))
            def cp(t=improved): pyperclip.copy(t)
            tk.Button(card,text="Copy",command=cp,bg=self._theme["accent"],fg=self._theme["button_fg"],relief="flat",padx=8,font=("Segoe UI",8)).pack(anchor="e")

class VoiceRefine:
    def __init__(self):
        self.config=load_config();self.recorder=AudioRecorder(self.config.get("sample_rate",16000),self.config.get("input_device"))
        self.processor=None;self.hotkey_mgr=None;self.overlay=None;self.tray=None;self.processing=False
        self._paused=False
        try: self.processor=VoiceProcessor(self.config)
        except ValueError as e:
            print(f"\n{'='*60}\n  SETUP NEEDED: {e}\n  Opening the VoiceRefine setup wizard.\n{'='*60}\n")
            saved={"value":False}
            def after_save(cfg):
                save_config(cfg);self.config=cfg;saved["value"]=has_api_key(cfg)
            if HAS_CTK_UI and _CtkWizard is not None:
                _CtkWizard(self.config, on_complete=after_save, icon_path=APP_ICON_PATH,
                           theme=self.config.get("theme","dark")).run()
            elif HAS_TK:
                SettingsWindow(self.config,after_save,first_run=True).show()
                tk.mainloop()
            if saved["value"]:
                self.config=load_config();self.recorder=AudioRecorder(self.config.get("sample_rate",16000),self.config.get("input_device"));self.processor=VoiceProcessor(self.config);return
            sys.exit(0)
    def _on_hotkey_press(self,preset_name="default"):
        if self.processing: return
        self._active_preset=preset_name
        print(f"  Recording [{preset_name}]...")
        try: self.recorder.start()
        except Exception as e:
            msg=str(e)
            print(f"  Microphone error: {msg}")
            if self.overlay: self.overlay.show("error",msg[:90])
            if self.tray: self.tray.set_state("error")
            def rt():
                time.sleep(4);self.tray and self.tray.set_state("idle")
            threading.Thread(target=rt,daemon=True).start()
            return
        label=f"Recording [{preset_name}]... 0.0s" if preset_name and preset_name!="default" else "Recording... 0.0s"
        if self.overlay: self.overlay.show("recording",label)
        if self.tray: self.tray.set_state("recording")
        self._update_recording()
    def _update_recording(self):
        if not self.recorder.recording: return
        d=self.recorder.get_duration();l=self.recorder.get_level()
        if self.overlay: self.overlay.update_recording(d,l)
        if self.overlay and self.overlay.root: self.overlay.root.after(100,self._update_recording)
    def _on_hotkey_release(self,preset_name="default"):
        if self.processing: return
        self.processing=True
        preset=getattr(self,"_active_preset",preset_name) or preset_name
        threading.Thread(target=self._process,args=(preset,),daemon=True).start()
    def _process(self,preset_name="default"):
        try:
            audio=self.recorder.stop()
            if audio is None or len(audio)<1600:
                print("  Too short.");
                if self.overlay: self.overlay.show("error","Too short, try again")
                if self.tray: self.tray.set_state("idle")
                return
            duration=len(audio)/self.config.get("sample_rate",16000);print(f"  Recorded {duration:.1f}s")
            if self.overlay: self.overlay.show("thinking",f"Refining [{preset_name}]...");self.overlay.animate_thinking()
            if self.tray: self.tray.set_state("thinking")
            wav_bytes=self.recorder.to_wav_bytes(audio);raw_text=self.processor.transcribe(wav_bytes)
            if not raw_text:
                if self.overlay: self.overlay.show("error","No speech detected")
                if self.tray: self.tray.set_state("idle")
                return
            print(f"  Raw: {raw_text}");improved=self.processor.improve(raw_text,preset_name=preset_name);print(f"  Improved [{preset_name}]: {improved}")
            pyperclip.copy(improved);print("  Copied!")
            preview=improved[:60]+("..." if len(improved)>60 else "")
            if self.overlay: self.overlay.show("done",f"Copied: {preview}")
            if self.tray: self.tray.set_state("done")
            if self.config.get("auto_paste"):
                time.sleep(0.2);from pynput.keyboard import Controller,Key;kb=Controller();kb.press(Key.ctrl);kb.press("v");kb.release("v");kb.release(Key.ctrl)
            history=load_history()
            history.append({"timestamp":datetime.datetime.now().isoformat(timespec="seconds"),"raw":raw_text,"improved":improved,"duration":round(duration,1),"model":self.config.get("model","gpt-4o-mini"),"preset":preset_name})
            if len(history)>self.config.get("max_history",100): history=history[-self.config.get("max_history",100):]
            save_history(history)
            if self.tray:
                try: self.tray.refresh_menu()
                except Exception: pass
            # Vault write (best-effort, never blocks the user flow)
            if self.config.get("vault_enabled") and self.config.get("vault_path"):
                try:
                    from voicerefine_vault import write_capture
                    bound_hotkey=next((hk for hk,p in (self.config.get("preset_hotkeys") or {}).items() if p==preset_name),"")
                    cap_id=write_capture(
                        self.config["vault_path"],
                        self.config.get("vault_category","voice-captures"),
                        raw_text=raw_text,
                        improved_text=improved,
                        duration_seconds=duration,
                        model=self.config.get("model","gpt-4o-mini"),
                        preset_name=preset_name,
                        hotkey=bound_hotkey,
                    )
                    if cap_id: print(f"  Vault: wrote {cap_id}")
                except Exception as ve:
                    print(f"  [vault] write failed: {ve}")
            def rt(): time.sleep(3);self.tray and self.tray.set_state("idle")
            threading.Thread(target=rt,daemon=True).start()
        except Exception as e:
            print(f"  Error: {e}")
            if self.overlay: self.overlay.show("error",f"Error: {str(e)[:50]}")
            if self.tray: self.tray.set_state("error")
        finally: self.processing=False
    def _open_settings(self):
        def apply_config(c):
            save_config(c)
            self.config=c
            self.recorder=AudioRecorder(self.config.get("sample_rate",16000),self.config.get("input_device"))
            # Rebuild processor in case API key/backend changed
            try: self.processor=VoiceProcessor(self.config)
            except Exception as e: print(f"  [settings] processor reload failed: {e}")
            # Reload hotkeys
            if self.hotkey_mgr:
                try: self.hotkey_mgr.stop()
                except Exception: pass
                hotkey_map=dict(self.config.get("preset_hotkeys") or {}) or {self.config.get("hotkey","<cmd>+<alt>"):"default"}
                self.hotkey_mgr=MultiHotkeyManager(hotkey_map,self._on_hotkey_press,self._on_hotkey_release)
                self.hotkey_mgr.start()
        def _open():
            if HAS_CTK_UI and _CtkSettings is not None:
                _CtkSettings(self.config, on_save=apply_config, icon_path=APP_ICON_PATH,
                             theme=self.config.get("theme","dark"), app_version=APP_VERSION).show()
            else:
                SettingsWindow(self.config,apply_config).show()
        if self.overlay and self.overlay.root: self.overlay.root.after(0,_open)
        else: _open()
    def _open_history(self):
        hw=HistoryWindow(self.config)
        if self.overlay and self.overlay.root: self.overlay.root.after(0,hw.show)
        else: hw.show()
    def run(self):
        hotkey_map=dict(self.config.get("preset_hotkeys") or {})
        if not hotkey_map:
            # Fallback: use legacy single hotkey, bind to 'default'
            hotkey_map={self.config.get("hotkey","<cmd>+<alt>"): "default"}
        backend=self.config.get("transcription_backend","openai")
        vault_status="off" if not self.config.get("vault_enabled") else f"on -> {self.config.get('vault_path','')}"
        print(f"\n VoiceRefine v{APP_VERSION}")
        print(f" Model: {self.config.get('model','gpt-4o-mini')} | Backend: {backend} | Overlay: {'On' if self.config.get('show_overlay') else 'Off'} | Vault: {vault_status}")
        print(" Hotkeys:")
        for hk,preset in hotkey_map.items():
            print(f"   {hk:<32} -> {preset}")
        print(" Hold a hotkey to record, release to process. Right-click tray for settings.\n")
        self.overlay=StatusOverlay(self.config)
        self.tray=TrayIcon(
            self._open_settings,self._open_history,self._quit,
            on_pause_toggle=self._toggle_pause,
            get_paused=lambda: self._paused,
            get_last_preview=self._get_last_preview,
            get_today_stats=self._get_today_stats,
        )
        self.tray.start()
        self.hotkey_mgr=MultiHotkeyManager(hotkey_map,self._on_hotkey_press,self._on_hotkey_release);self.hotkey_mgr.start()
        try: self.overlay.run_loop()
        except KeyboardInterrupt: self._quit()
    def _quit(self):
        print("\nShutting down...")
        if self.hotkey_mgr: self.hotkey_mgr.stop()
        if self.tray: self.tray.stop()
        if self.overlay: self.overlay.quit()
        sys.exit(0)

    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            if self.hotkey_mgr:
                try: self.hotkey_mgr.stop()
                except Exception: pass
            if self.tray: self.tray.set_state("paused")
            if self.overlay: self.overlay.show("error","Hotkeys paused — tap tray to resume")
        else:
            hotkey_map=dict(self.config.get("preset_hotkeys") or {}) or {self.config.get("hotkey","<cmd>+<alt>"):"default"}
            self.hotkey_mgr=MultiHotkeyManager(hotkey_map,self._on_hotkey_press,self._on_hotkey_release)
            self.hotkey_mgr.start()
            if self.tray: self.tray.set_state("idle")
            if self.overlay: self.overlay.show("done","Hotkeys resumed")
        if self.tray: self.tray.refresh_menu()

    def _get_last_preview(self):
        try:
            h=load_history()
            return (h[-1].get("improved") or "") if h else ""
        except Exception: return ""

    def _get_today_stats(self):
        try:
            h=load_history()
            today=datetime.date.today().isoformat()
            captures=0; words=0
            for e in h:
                ts=(e.get("timestamp") or "")
                if ts.startswith(today):
                    captures+=1
                    words+=len((e.get("improved") or "").split())
            return (captures,words)
        except Exception: return (0,0)

if __name__=="__main__":
    if "--mcp" in sys.argv:
        # MCP server mode - no hotkey, no tray, just MCP stdio
        import asyncio
        from voicerefine_mcp import main as mcp_main
        asyncio.run(mcp_main())
    elif "--stream" in sys.argv:
        # Stream mode - hotkey mode + WebSocket broadcast
        import asyncio, websockets, json as wsjson
        connected = set()
        broadcast_queue = asyncio.Queue()

        async def ws_handler(websocket):
            connected.add(websocket)
            try:
                async for _ in websocket:
                    pass
            finally:
                connected.discard(websocket)

        async def broadcaster():
            while True:
                msg = await broadcast_queue.get()
                for ws in list(connected):
                    try:
                        await ws.send(msg)
                    except:
                        connected.discard(ws)

        _original_process = None

        def start_stream_app():
            import threading
            app = VoiceRefine()
            _orig = app._process
            def patched_process(self_ref=app):
                _orig()
                # After processing, broadcast
                history = load_history()
                if history:
                    last = history[-1]
                    try:
                        broadcast_queue.put_nowait(wsjson.dumps({
                            "type": "polished",
                            "text": last.get("improved", ""),
                            "raw": last.get("raw", ""),
                            "duration_ms": int(last.get("duration", 0) * 1000),
                            "timestamp": last.get("timestamp", "")
                        }))
                    except:
                        pass
            app._process = patched_process
            app.run()

        async def run_stream():
            port = load_config().get("stream_port", 8765)
            async with websockets.serve(ws_handler, "127.0.0.1", port):
                print(f"  WebSocket stream on ws://127.0.0.1:{port}")
                bt = asyncio.create_task(broadcaster())
                import threading
                t = threading.Thread(target=start_stream_app, daemon=True)
                t.start()
                await asyncio.Future()  # run forever

        asyncio.run(run_stream())
    elif len(sys.argv)>1 and sys.argv[1]=="--settings":
        config=load_config()
        if HAS_CTK_UI and _CtkSettings is not None:
            _CtkSettings(config, on_save=save_config, icon_path=APP_ICON_PATH,
                         theme=config.get("theme","dark"), app_version=APP_VERSION).show()
        elif HAS_TK:
            SettingsWindow(config,save_config).show()
            tk.mainloop()
    elif len(sys.argv)>1 and sys.argv[1]=="--history":
        config=load_config();HistoryWindow(config).show()
        if HAS_TK: tk.mainloop()
    else: VoiceRefine().run()
