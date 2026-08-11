import random
import hashlib
from pathlib import Path


class VoicePool:
    def __init__(self, folder: str, default: str = "", mode: str = "default"):
        self.folder = Path(folder)
        self.mode = (mode or "default").lower()
        self.voices = sorted(str(p) for p in self.folder.glob("*.onnx"))
        if not self.voices:
            raise RuntimeError(f"No .onnx voices found in {self.folder.resolve()}")

        self.default = ""
        if default:
            cand = self.folder / default
            if cand.exists():
                self.default = str(cand)
        if not self.default:
            self.default = self.voices[0]

    def pick(self, user: str = "") -> str:
        if self.mode == "random":
            return random.choice(self.voices)
        if self.mode == "per_user" and user:
            h = int(hashlib.md5(user.lower().encode()).hexdigest(), 16)
            return self.voices[h % len(self.voices)]
        return self.default

    def random_voice(self) -> str:
        return random.choice(self.voices)

    def find(self, name: str):
        if not name:
            return None
        needle = name.strip().lower()
        for v in self.voices:                      # exact stem: "en_US-amy-medium"
            if Path(v).stem.lower() == needle:
                return v
        for v in self.voices:                      # substring: "amy" -> en_US-amy-medium
            if needle in Path(v).stem.lower():
                return v
        return None