from dataclasses import dataclass

TIER_NAMES = {"Prime": "Prime", "1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}

import re
_VOICE_PREFIX = re.compile(r"^\s*\[([^\]]{1,32})\]\s*(.*)$", re.DOTALL)

def parse_voice_prefix(message: str):
    """'[amy] hello' -> ('amy', 'hello');  'hello' -> (None, 'hello')"""
    m = _VOICE_PREFIX.match(message or "")
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, (message or "").strip()

@dataclass
class SpeakEvent:
    kind: str            # sub | resub | subgift | submysterygift | cheer | raid | command
    user: str = ""
    message: str = ""
    tier: str = ""
    months: int = 0
    recipient: str = ""
    count: int = 0
    bits: int = 0
    command: str = ""
    reward_title: str = ""
    reward_id: str = ""


def to_line(ev: SpeakEvent, config: dict):
    events = config.get("events", {})
    fmt = {
        "user": ev.user, "message": strip_sfx((ev.message or "").strip()),
        "tier": ev.tier, "months": ev.months, "recipient": ev.recipient,
        "count": ev.count, "bits": ev.bits, "command": ev.command,
    }

    if ev.kind == "command":
        tmpl = config.get("commands", {}).get("map", {}).get(ev.command)
        return _fmt(tmpl, fmt)

    # Prime override for sub/resub
    if ev.kind in ("sub", "resub") and ev.tier == "Prime":
        prime = events.get("prime")
        if prime and prime.get("enabled", False):
            return _fmt(prime.get("template", ""), fmt)

    ev_cfg = events.get(ev.kind)
    if not ev_cfg or not ev_cfg.get("enabled", False):
        return None
    return _fmt(ev_cfg.get("template", ""), fmt)


def _fmt(tmpl, fmt):
    if not tmpl:
        return None
    out = tmpl
    for k, v in fmt.items():
        out = out.replace("{" + k + "}", str(v))
    return " ".join(out.split()).strip() or None

_SFX_TAG = re.compile(r'\{sfx\s+"([^"]+)"\}')

def strip_sfx(text):
    """Remove {sfx "..."} tags — sanitizes viewer-supplied text so it can't trigger sounds."""
    return _SFX_TAG.sub("", text or "")

def split_sfx(text):
    """Split a line into ordered ('text', str) / ('sfx', filename) parts."""
    parts, last = [], 0
    for m in _SFX_TAG.finditer(text or ""):
        pre = text[last:m.start()].strip()
        if pre:
            parts.append(("text", pre))
        parts.append(("sfx", m.group(1)))
        last = m.end()
    tail = (text or "")[last:].strip()
    if tail:
        parts.append(("text", tail))
    return parts or [("text", "")]