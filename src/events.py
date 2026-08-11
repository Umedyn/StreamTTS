from dataclasses import dataclass

TIER_NAMES = {"Prime": "Prime", "1000": "Tier 1", "2000": "Tier 2", "3000": "Tier 3"}


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


def to_line(ev: SpeakEvent, config: dict):
    events = config.get("events", {})
    fmt = {
        "user": ev.user, "message": (ev.message or "").strip(),
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
    try:
        out = tmpl.format(**fmt)
    except Exception:
        out = tmpl
        for k, v in fmt.items():
            out = out.replace("{" + k + "}", str(v))
    return " ".join(out.split()).strip() or None