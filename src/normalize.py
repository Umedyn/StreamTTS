import re
import unicodedata

_TRANS = str.maketrans({
    "‘": "'", "’": "'", "ʼ": "'", "′": "'",
    "“": '"', "”": '"', "″": '"',
    "–": ", ", "—": ", ", "…": "...", " ": " ",
})

def clean_text(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.translate(_TRANS)
    s = re.sub(r"(?<=\w)\s*'\s*(?=\w)", "'", s)      # I ' m -> I'm
    s = s.replace('"', '')
    s = re.sub(r"\s*-{2,}\s*", ", ", s)
    s = re.sub(r"\s-\s", ", ", s)
    s = re.sub(r"(?s)\*{1,2}([^*]+)\*{1,2}", r"\1", s)   # strip markdown emphasis
    s = re.sub(r"_([^_]+)_", r"\1", s)
    s = re.sub(r"[^\w\s\.,!?;:()\-']+", " ", s)          # drop symbols TTS reads literally
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([\.,!?;:])", r"\1", s)
    return s.strip()