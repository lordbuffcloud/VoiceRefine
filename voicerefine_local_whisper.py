#!/usr/bin/env python3
"""Optional local Whisper backend using faster-whisper.

Lazy-imported on first use so the package isn't a hard dependency of VoiceRefine.
Install with: pip install faster-whisper
"""
import io
import wave


class LocalWhisperUnavailable(RuntimeError):
    """Raised when the faster-whisper package is not installed."""


class LocalWhisperBackend:
    """Wraps a faster-whisper WhisperModel. One backend per process; loads on demand."""

    _model_cache = {}

    def __init__(self, model_size="base", device="auto", compute_type="auto"):
        self.model_size = model_size or "base"
        self.device = device or "auto"
        self.compute_type = compute_type or "auto"
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model
        key = (self.model_size, self.device, self.compute_type)
        if key in self._model_cache:
            self._model = self._model_cache[key]
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise LocalWhisperUnavailable(
                "faster-whisper is not installed. Install with: pip install faster-whisper"
            ) from exc
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
        )
        self._model_cache[key] = self._model
        return self._model

    def transcribe(self, wav_bytes_io, language=None):
        """Transcribe a WAV BytesIO and return cleaned text.

        Raises LocalWhisperUnavailable if the package is missing.
        """
        model = self._load()
        wav_bytes_io.seek(0)
        # faster-whisper accepts a file-like object or path; BytesIO works.
        segments, _info = model.transcribe(
            wav_bytes_io,
            language=language,
            beam_size=1,
            vad_filter=False,
        )
        text = " ".join(seg.text.strip() for seg in segments if seg.text)
        return text.strip()


def is_available():
    """Cheap probe — returns True if faster-whisper can be imported."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
