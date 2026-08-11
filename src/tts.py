from __future__ import annotations
import os
import queue
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import sounddevice as sd

from piper.voice import PiperVoice
from piper import SynthesisConfig


def _ensure_espeak_data_path():
    if os.environ.get("ESPEAK_DATA_PATH"):
        return
    try:
        import piper
        espeak_dir = Path(piper.__file__).resolve().parent / "espeak-ng-data"
        if espeak_dir.exists():
            os.environ["ESPEAK_DATA_PATH"] = str(espeak_dir)
    except Exception as e:
        print(f"[TTS] Could not set ESPEAK_DATA_PATH: {e}")


class PiperEngine:
    def __init__(self, length_scale: float = 0.95, pitch_semitones: float = 0.0):
        _ensure_espeak_data_path()
        self.length_scale = float(length_scale)
        self.pitch_semitones = float(pitch_semitones)
        self._cache: dict[str, PiperVoice] = {}
        self._lock = threading.Lock()

    def preload(self, paths):
        """Load every voice now so there's no first-use hitch mid-stream."""
        ok = 0
        for p in paths:
            if self._get_voice(p) is not None:
                ok += 1
        print(f"[TTS] Preloaded {ok}/{len(paths)} voice(s).")
        return ok

    def _get_voice(self, onnx_path: str) -> Optional[PiperVoice]:
        key = str(onnx_path)
        with self._lock:
            v = self._cache.get(key)
            if v is None:
                if not Path(key).exists():
                    print(f"[TTS] Voice not found: {key}")
                    return None
                try:
                    v = PiperVoice.load(key)
                    self._cache[key] = v
                    print(f"[TTS] Loaded voice: {Path(key).name}")
                except Exception as e:
                    print(f"[TTS] Failed to load {key}: {e}")
                    return None
            return v

    def render(self, text: str, onnx_path: str):
        """Return (int16 mono samples, sample_rate) or (None, 0)."""
        text = (text or "").strip()
        if not text:
            return None, 0
        voice = self._get_voice(onnx_path)
        if voice is None:
            return None, 0

        cfg = SynthesisConfig(length_scale=self.length_scale, volume=1.0, normalize_audio=True)
        chunks, sr = [], 22050
        try:
            for ch in voice.synthesize(text, syn_config=cfg):
                b = getattr(ch, "audio_int16_bytes", None)
                if b:
                    chunks.append(np.frombuffer(b, dtype=np.int16))
                    sr = getattr(ch, "sample_rate", sr)
        except Exception as e:
            print(f"[TTS] synth error: {e}")
            return None, 0

        if not chunks:
            return None, 0
        samples = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        if abs(self.pitch_semitones) > 1e-3:
            sr = int(sr * (2.0 ** (self.pitch_semitones / 12.0)))  # NB: shifts speed too
        return samples, sr


class Speaker:
    def __init__(self, engine, output_device=-1, gap_ms=120, sfx_dir="sfx", max_queue=0):
        self.engine = engine
        self.device = None if output_device is None or output_device < 0 else int(output_device)
        self.gap_ms = int(gap_ms)
        self.sfx_dir = Path(sfx_dir)
        self.max_queue = int(max_queue)
        self._q = queue.Queue(maxsize=self.max_queue) if self.max_queue > 0 else queue.Queue()
        self._alive = threading.Event(); self._alive.set()
        self._t = threading.Thread(target=self._loop, name="tts_speaker", daemon=True)
        self._t.start()

    def enqueue(self, text, onnx_path):
        self.enqueue_sequence([("text", text)], onnx_path)

    def enqueue_sequence(self, parts, onnx_path):
        item = (parts, onnx_path)
        if self.max_queue > 0:
            try:
                self._q.put_nowait(item)
            except queue.Full:
                try: self._q.get_nowait()          # drop oldest to stay current
                except queue.Empty: pass
                try: self._q.put_nowait(item)
                except queue.Full: pass
        else:
            self._q.put(item)

    def _loop(self):
        while self._alive.is_set():
            try:
                parts, onnx = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            for kind, val in parts:
                if not self._alive.is_set():
                    break
                if kind == "text":
                    self._play_tts(val, onnx)
                elif kind == "sfx":
                    self._play_sfx(val)
            time.sleep(self.gap_ms / 1000.0)

    def _play_tts(self, text, onnx):
        samples, sr = self.engine.render(text, onnx)
        if samples is None:
            return
        try:
            sd.play(samples, samplerate=sr, device=self.device); sd.wait()
        except Exception as e:
            print(f"[TTS] playback error: {e}")

    def _play_sfx(self, filename):
        path = self.sfx_dir / Path(filename).name     # .name blocks ../ path traversal
        if not path.exists():
            print(f"[SFX] not found: {path}")
            return
        try:
            import soundfile as sf
            data, sr = sf.read(str(path), dtype="float32")
            sd.play(data, samplerate=sr, device=self.device); sd.wait()
        except Exception as e:
            print(f"[SFX] play error ({filename}): {e}")

    def stop(self):
        self._alive.clear()