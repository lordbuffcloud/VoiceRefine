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

if getattr(sys, 'frozen', False):
    _RESOURCE_BASE = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    _CONFIG_BASE = Path(sys.executable).parent
else:
    _RESOURCE_BASE = Path(__file__).parent
    _CONFIG_BASE = _RESOURCE_BASE
CONFIG_PATH = _CONFIG_BASE / "config.json"
HISTORY_PATH = _CONFIG_BASE / "history.json"
APP_NAME = "VoiceRefine"
APP_VERSION = "2.1"
CK42X_URL = "https://ck42x.com"
OPENAI_KEYS_URL = "https://platform.openai.com/api-keys"
APP_ICON_PATH = _RESOURCE_BASE / "branding" / "app-icon.ico"
DEFAULT_CONFIG = {"openai_api_key":"","model":"gpt-4o-mini","whisper_model":"whisper-1","hotkey":"<cmd>+<alt>","prompt":"You are a writing assistant. Take the following transcribed speech and improve it: fix grammar, punctuation, and spelling errors. Make it clear and well-structured while preserving the speaker's original meaning and tone. If the text is a quick message, keep it casual. If it's more formal, match that register. Do not add information that wasn't in the original. Return only the improved text, nothing else.","sample_rate":16000,"show_overlay":True,"overlay_position":"bottom-right","overlay_duration":3,"window_opacity":0.96,"auto_paste":False,"play_sounds":True,"theme":"dark","max_history":100}
THEMES = {"dark":{"bg":"#0b0b0c","fg":"#e9e9ea","accent":"#ffb300","accent2":"#e94560","success":"#4ecca3","recording":"#e94560","thinking":"#ffb300","done":"#4ecca3","error":"#ff6b6b","panel":"#151517","panel2":"#101012","border":"#2a2b30","input_bg":"#101012","input_fg":"#e9e9ea","button":"#ffb300","button_fg":"#0b0b0c","subtle":"#a2a3a8"},"light":{"bg":"#f5f5f5","fg":"#1a1a1a","accent":"#d49100","accent2":"#c0392b","success":"#27ae60","recording":"#c0392b","thinking":"#d49100","done":"#27ae60","error":"#e74c3c","panel":"#ffffff","panel2":"#f0f0f1","border":"#d8d8dc","input_bg":"#ffffff","input_fg":"#1a1a1a","button":"#d49100","button_fg":"#ffffff","subtle":"#6c6d72"}}

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH,"r") as f: saved=json.load(f)
        return {**DEFAULT_CONFIG,**saved}
    cfg=DEFAULT_CONFIG.copy(); save_config(cfg); return cfg

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

class AudioRecorder:
    def __init__(self,sample_rate=16000):
        self.sample_rate=sample_rate;self.frames=[];self.recording=False;self.stream=None;self.start_time=None
    def start(self):
        self.frames=[];self.recording=True;self.start_time=time.time()
        self.stream=sd.InputStream(samplerate=self.sample_rate,channels=1,dtype="int16",callback=self._callback)
        self.stream.start()
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
    def transcribe(self,wav_bytes):
        wav_bytes.name="recording.wav"
        return self.client.audio.transcriptions.create(model=self.config.get("whisper_model","whisper-1"),file=wav_bytes,response_format="text").strip()
    def improve(self,raw_text):
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

class StatusOverlay:
    def __init__(self,config):
        self.config=config;self.root=None;self.label=None;self.canvas=None;self.dots_after=None
        self.dot_count=0;self.level_bars=[];self.active=False
        self._theme=THEMES.get(config.get("theme","dark"),THEMES["dark"])
    def _create_window(self):
        if self.root and self.root.winfo_exists(): return
        self.root=tk.Tk();self.root.withdraw();self.root.overrideredirect(True);self.root.attributes("-topmost",True)
        try: self.root.attributes("-alpha",min(self.config.get("window_opacity",0.96),0.92))
        except: pass
        self.root.configure(bg=self._theme["bg"])
        frame=tk.Frame(self.root,bg=self._theme["panel"],highlightbackground=self._theme["border"],highlightthickness=1,padx=18,pady=13)
        frame.pack(fill="both",expand=True)
        self.canvas=tk.Canvas(frame,width=16,height=16,bg=self._theme["panel"],highlightthickness=0)
        self.canvas.pack(side="left",padx=(0,10))
        self.label=tk.Label(frame,text="",fg=self._theme["fg"],bg=self._theme["panel"],font=("Segoe UI",11) if sys.platform=="win32" else ("Helvetica",12),anchor="w")
        self.label.pack(side="left",fill="x",expand=True)
        self.level_frame=tk.Frame(frame,bg=self._theme["panel"]);self.level_frame.pack(side="right",padx=(10,0))
        self.level_bars=[]
        for i in range(5):
            bar=tk.Frame(self.level_frame,width=4,height=4,bg=self._theme["border"]);bar.pack(side="left",padx=1);self.level_bars.append(bar)
    def _position_window(self):
        if not self.root: return
        pos=self.config.get("overlay_position","bottom-right");self.root.update_idletasks()
        w=max(self.root.winfo_width(),300);h=self.root.winfo_height();sw=self.root.winfo_screenwidth();sh=self.root.winfo_screenheight();m=20
        ps={"bottom-right":(sw-w-m,sh-h-m-50),"bottom-left":(m,sh-h-m-50),"top-right":(sw-w-m,m),"top-left":(m,m),"center":(sw//2-w//2,sh//2-h//2)}
        x,y=ps.get(pos,ps["bottom-right"]);self.root.geometry(f"{w}x{h}+{x}+{y}")
    def show(self,state,text="",level=0):
        if not self.config.get("show_overlay",True): return
        def _do():
            self._create_window();color=self._theme.get(state,self._theme["fg"]);self.canvas.delete("all")
            if state=="recording": self.canvas.create_oval(2,2,14,14,fill=color,outline="")
            elif state=="thinking": self.canvas.create_oval(2,2,14,14,fill=color,outline="")
            elif state=="done": self.canvas.create_line(3,8,7,12,fill=color,width=2);self.canvas.create_line(7,12,13,4,fill=color,width=2)
            elif state=="error": self.canvas.create_line(3,3,13,13,fill=color,width=2);self.canvas.create_line(13,3,3,13,fill=color,width=2)
            self.label.configure(text=text,fg=color)
            if state=="recording":
                ab=int(level*5)
                for i,bar in enumerate(self.level_bars): bar.configure(height=4+(i+1)*3,bg=color if i<ab else self._theme["border"])
                self.level_frame.pack(side="right",padx=(10,0))
            else: self.level_frame.pack_forget()
            self._position_window();self.root.deiconify();self.active=True
            if self.dots_after: self.root.after_cancel(self.dots_after);self.dots_after=None
            if state in("done","error"): self.dots_after=self.root.after(self.config.get("overlay_duration",3)*1000,self.hide)
        if self.root: self.root.after(0,_do)
        else: _do()
    def update_recording(self,duration,level):
        def _do():
            if not self.active or not self.label: return
            self.label.configure(text=f"Recording... {duration:.1f}s")
            ab=int(level*5);color=self._theme["recording"]
            for i,bar in enumerate(self.level_bars): bar.configure(height=4+(i+1)*3,bg=color if i<=ab else self._theme["border"])
        if self.root: self.root.after(0,_do)
    def animate_thinking(self):
        def _do():
            if not self.active or not self.label: return
            self.dot_count=(self.dot_count+1)%4;self.label.configure(text=f"Refining{'.'*self.dot_count}")
            self.dots_after=self.root.after(400,self.animate_thinking)
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
    def __init__(self,on_settings,on_history,on_quit):
        self.on_settings=on_settings;self.on_history=on_history;self.on_quit=on_quit;self.icon=None;self.running=False
    def start(self):
        try:
            import pystray;from PIL import Image
        except ImportError: print("  [Tray] pystray/Pillow not installed.");return
        idle_img=create_tray_icon_image((100,100,100))
        menu=pystray.Menu(pystray.MenuItem("Settings",lambda:self.on_settings()),pystray.MenuItem("History",lambda:self.on_history()),pystray.MenuItem("CK42X.com",lambda:open_url(CK42X_URL)),pystray.Menu.SEPARATOR,pystray.MenuItem("Quit",lambda:self.on_quit()))
        self.icon=pystray.Icon("VoiceRefine",idle_img,"VoiceRefine - Idle",menu);self.running=True
        threading.Thread(target=self.icon.run,daemon=True).start()
    def set_state(self,state):
        if not self.icon: return
        cs={"idle":(100,100,100),"recording":(233,69,96),"thinking":(245,166,35),"done":(78,204,163),"error":(255,107,107)}
        ts={"idle":"VoiceRefine - Ready","recording":"VoiceRefine - Recording...","thinking":"VoiceRefine - Refining...","done":"VoiceRefine - Copied!","error":"VoiceRefine - Error"}
        img=create_tray_icon_image(cs.get(state,cs["idle"]))
        if img: self.icon.icon=img
        self.icon.title=ts.get(state,ts["idle"])
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
        tip=tk.Frame(af,bg=self._theme["panel2"],highlightbackground=self._theme["border"],highlightthickness=1,padx=14,pady=12);tip.grid(row=6,column=0,columnspan=3,sticky="ew",pady=(18,0))
        tk.Label(tip,text="First run flow",fg=self._theme["accent"],bg=self._theme["panel2"],font=("Segoe UI",10,"bold")).pack(anchor="w")
        tk.Label(tip,text="1. Create or copy an OpenAI API key.  2. Paste it here.  3. Save and VoiceRefine starts cleanly.",fg=self._theme["subtle"],bg=self._theme["panel2"],font=("Segoe UI",9),wraplength=650,justify="left").pack(anchor="w",pady=(4,0))
        if self.first_run: root.after(250,api_entry.focus_set)

        pf=ttk.Frame(nb,style="Custom.TFrame",padding=22);nb.add(pf,text="Prompt")
        self._label(pf,"System prompt for polish").pack(anchor="w",pady=(0,8))
        prompt_text=tk.Text(pf,width=60,height=13,wrap="word",bg=self._theme["input_bg"],fg=self._theme["input_fg"],insertbackground=self._theme["fg"],relief="flat",highlightthickness=1,highlightbackground=self._theme["border"],highlightcolor=self._theme["accent"],font=("Consolas",10) if sys.platform=="win32" else ("Courier",10),padx=10,pady=10)
        prompt_text.pack(fill="both",expand=True);prompt_text.insert("1.0",self.config.get("prompt",DEFAULT_CONFIG["prompt"]))
        prf=tk.Frame(pf,bg=self._theme["panel"]);prf.pack(fill="x",pady=(10,0))
        tk.Label(prf,text="Presets",bg=self._theme["panel"],fg=self._theme["subtle"],font=("Segoe UI",9,"bold")).pack(side="left",padx=(0,8))
        presets={"Clean Up":"Fix grammar, punctuation, and spelling. Keep the original tone. Return only the corrected text.","Professional":"Rewrite in a professional tone. Fix all errors. Return only the improved text.","Casual":"Clean up but keep it casual. Fix obvious errors. Return only the text.","Summary":"Summarize into concise bullet points. Return only the summary.","Email":"Turn into a well-formatted email with greeting and sign-off. Return only the email."}
        for n in presets:
            def sp(name=n): prompt_text.delete("1.0","end");prompt_text.insert("1.0",presets[name])
            self._button(prf,n,sp).pack(side="left",padx=3)

        hf=ttk.Frame(nb,style="Custom.TFrame",padding=22);nb.add(hf,text="Hotkey")
        hf.columnconfigure(1,weight=1)
        self._label(hf,"Hold-to-record hotkey").grid(row=0,column=0,sticky="w",pady=8)
        hotkey_var=tk.StringVar(value=self.config.get("hotkey","<cmd>+<alt>"))
        self._entry(hf,textvariable=hotkey_var,width=32).grid(row=0,column=1,sticky="w",padx=(12,0),pady=8,ipady=7)
        self._subtle(hf,"Use <cmd>, <alt>, <ctrl>, <shift>, or add one letter like <ctrl>+<alt>+r.",wraplength=620,justify="left").grid(row=1,column=0,columnspan=2,sticky="w",pady=(0,16))
        r=2
        for combo,label in [("<cmd>+<alt>","Win + Alt"),("<ctrl>+<shift>+r","Ctrl + Shift + R"),("<ctrl>+<alt>","Ctrl + Alt")]:
            self._button(hf,label,lambda c=combo:hotkey_var.set(c)).grid(row=r,column=0,columnspan=2,sticky="w",pady=3);r+=1
        auto_paste_var=tk.BooleanVar(value=self.config.get("auto_paste",False))
        ttk.Checkbutton(hf,text="Auto-paste after copying with Ctrl+V",variable=auto_paste_var,style="Custom.TCheckbutton").grid(row=r+1,column=0,columnspan=2,sticky="w",pady=(20,4))

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

        bf=tk.Frame(shell,bg=self._theme["bg"]);bf.pack(fill="x",pady=(12,0))
        status=tk.Label(bf,text="",bg=self._theme["bg"],fg=self._theme["subtle"],font=("Segoe UI",9));status.pack(side="left")
        def on_save():
            self.config.update({"openai_api_key":api_var.get().strip(),"model":model_var.get().strip(),"whisper_model":whisper_var.get().strip(),"hotkey":hotkey_var.get().strip(),"prompt":prompt_text.get("1.0","end").strip(),"show_overlay":overlay_var.get(),"overlay_position":pos_var.get(),"overlay_duration":dur_var.get(),"window_opacity":round(float(opacity_var.get()),2),"auto_paste":auto_paste_var.get(),"theme":theme_var.get()})
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
        self.config=load_config();self.recorder=AudioRecorder(self.config.get("sample_rate",16000))
        self.processor=None;self.hotkey_mgr=None;self.overlay=None;self.tray=None;self.processing=False
        try: self.processor=VoiceProcessor(self.config)
        except ValueError as e:
            print(f"\n{'='*60}\n  SETUP NEEDED: {e}\n  Opening the VoiceRefine setup window.\n{'='*60}\n")
            if HAS_TK:
                saved={"value":False}
                def after_save(cfg):
                    self.config=cfg;saved["value"]=has_api_key(cfg)
                SettingsWindow(self.config,after_save,first_run=True).show()
                tk.mainloop()
                if saved["value"]:
                    self.config=load_config();self.recorder=AudioRecorder(self.config.get("sample_rate",16000));self.processor=VoiceProcessor(self.config);return
            sys.exit(0)
    def _on_hotkey_press(self):
        if self.processing: return
        print("  Recording...");self.recorder.start()
        if self.overlay: self.overlay.show("recording","Recording... 0.0s")
        if self.tray: self.tray.set_state("recording")
        self._update_recording()
    def _update_recording(self):
        if not self.recorder.recording: return
        d=self.recorder.get_duration();l=self.recorder.get_level()
        if self.overlay: self.overlay.update_recording(d,l)
        if self.overlay and self.overlay.root: self.overlay.root.after(100,self._update_recording)
    def _on_hotkey_release(self):
        if self.processing: return
        self.processing=True;threading.Thread(target=self._process,daemon=True).start()
    def _process(self):
        try:
            audio=self.recorder.stop()
            if audio is None or len(audio)<1600:
                print("  Too short.");
                if self.overlay: self.overlay.show("error","Too short, try again")
                if self.tray: self.tray.set_state("idle")
                return
            duration=len(audio)/self.config.get("sample_rate",16000);print(f"  Recorded {duration:.1f}s")
            if self.overlay: self.overlay.show("thinking","Refining...");self.overlay.animate_thinking()
            if self.tray: self.tray.set_state("thinking")
            wav_bytes=self.recorder.to_wav_bytes(audio);raw_text=self.processor.transcribe(wav_bytes)
            if not raw_text:
                if self.overlay: self.overlay.show("error","No speech detected")
                if self.tray: self.tray.set_state("idle")
                return
            print(f"  Raw: {raw_text}");improved=self.processor.improve(raw_text);print(f"  Improved: {improved}")
            pyperclip.copy(improved);print("  Copied!")
            preview=improved[:60]+("..." if len(improved)>60 else "")
            if self.overlay: self.overlay.show("done",f"Copied: {preview}")
            if self.tray: self.tray.set_state("done")
            if self.config.get("auto_paste"):
                time.sleep(0.2);from pynput.keyboard import Controller,Key;kb=Controller();kb.press(Key.ctrl);kb.press("v");kb.release("v");kb.release(Key.ctrl)
            history=load_history()
            history.append({"timestamp":datetime.datetime.now().isoformat(timespec="seconds"),"raw":raw_text,"improved":improved,"duration":round(duration,1),"model":self.config.get("model","gpt-4o-mini")})
            if len(history)>self.config.get("max_history",100): history=history[-self.config.get("max_history",100):]
            save_history(history)
            def rt(): time.sleep(3);self.tray and self.tray.set_state("idle")
            threading.Thread(target=rt,daemon=True).start()
        except Exception as e:
            print(f"  Error: {e}")
            if self.overlay: self.overlay.show("error",f"Error: {str(e)[:50]}")
            if self.tray: self.tray.set_state("error")
        finally: self.processing=False
    def _open_settings(self):
        sw=SettingsWindow(self.config,lambda c:setattr(self,'config',c))
        if self.overlay and self.overlay.root: self.overlay.root.after(0,sw.show)
        else: sw.show()
    def _open_history(self):
        hw=HistoryWindow(self.config)
        if self.overlay and self.overlay.root: self.overlay.root.after(0,hw.show)
        else: hw.show()
    def run(self):
        hk=self.config.get("hotkey","<cmd>+<alt>")
        print(f"\n VoiceRefine v{APP_VERSION}\n Hotkey: {hk} | Model: {self.config.get('model','gpt-4o-mini')} | Overlay: {'On' if self.config.get('show_overlay') else 'Off'}\n Hold hotkey to record, release to process. Right-click tray for settings.\n")
        self.hotkey_mgr=HotkeyManager(hk,self._on_hotkey_press,self._on_hotkey_release);self.hotkey_mgr.start()
        self.tray=TrayIcon(self._open_settings,self._open_history,self._quit);self.tray.start()
        self.overlay=StatusOverlay(self.config)
        try: self.overlay.run_loop()
        except KeyboardInterrupt: self._quit()
    def _quit(self):
        print("\nShutting down...")
        if self.hotkey_mgr: self.hotkey_mgr.stop()
        if self.tray: self.tray.stop()
        if self.overlay: self.overlay.quit()
        sys.exit(0)

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
        config=load_config();SettingsWindow(config,None).show()
        if HAS_TK: tk.mainloop()
    elif len(sys.argv)>1 and sys.argv[1]=="--history":
        config=load_config();HistoryWindow(config).show()
        if HAS_TK: tk.mainloop()
    else: VoiceRefine().run()
