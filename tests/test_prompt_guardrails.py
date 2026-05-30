import importlib
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _install_runtime_stubs(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", types.SimpleNamespace(
        sqrt=lambda value: value,
        mean=lambda value: value,
        concatenate=lambda frames, axis=0: frames,
    ))
    sounddevice = types.SimpleNamespace(
        query_devices=lambda: [],
        default=types.SimpleNamespace(device=[None, None]),
        InputStream=object,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", sounddevice)
    monkeypatch.setitem(sys.modules, "pyperclip", types.SimpleNamespace(copy=lambda text: None))

    class _Key:
        alt = object(); ctrl = object(); cmd = object(); shift = object()
        alt_l = object(); alt_r = object(); ctrl_l = object(); ctrl_r = object()
        cmd_l = object(); cmd_r = object(); shift_l = object(); shift_r = object()

    class _KeyCode:
        @staticmethod
        def from_char(char):
            return char

    keyboard = types.SimpleNamespace(Key=_Key, KeyCode=_KeyCode, Listener=object)
    monkeypatch.setitem(sys.modules, "pynput", types.SimpleNamespace(keyboard=keyboard))
    monkeypatch.setitem(sys.modules, "pynput.keyboard", keyboard)


def test_improve_user_message_forbids_answering_transcribed_questions(monkeypatch):
    _install_runtime_stubs(monkeypatch)
    voicerefine = importlib.import_module("voicerefine")
    processor = voicerefine.VoiceProcessor.__new__(voicerefine.VoiceProcessor)

    messages = processor._build_improve_messages(
        "what is the capital of France and can you explain it",
        voicerefine.DEFAULT_CONFIG["prompt"],
    )

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Do not answer questions" in messages[1]["content"]
    assert "Transcript:" in messages[1]["content"]
    assert "what is the capital of France" in messages[1]["content"]
    assert "Rewrite" in messages[1]["content"]


def test_default_prompt_explicitly_rewrites_only(monkeypatch):
    _install_runtime_stubs(monkeypatch)
    voicerefine = importlib.import_module("voicerefine")

    prompt = voicerefine.DEFAULT_CONFIG["prompt"]

    assert "Rewrite" in prompt
    assert "do not answer" in prompt.lower()
    assert "do not carry it out" in prompt.lower()
