import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voices import VoicePool
from tts import PiperEngine, Speaker
from twitch import TwitchChat
from events import to_line, parse_voice_prefix
from normalize import clean_text
from cooldown import Cooldown
from auth import TwitchAuth


def main():
    if "--list-devices" in sys.argv:
        import sounddevice as sd
        print(sd.query_devices())
        return

    root = Path(__file__).resolve().parent.parent
    with open(root / "config.toml", "rb") as f:
        cfg = tomllib.load(f)

    if "--login" in sys.argv:                       # force re-auth / switch account
        TwitchAuth(str(root / "token.json")).ensure(force_login=True)
        return

    vcfg = cfg.get("voices", {})
    pool = VoicePool(
        folder=str((root / vcfg.get("folder", "voices")).resolve()),
        default=vcfg.get("default", ""),
        mode=vcfg.get("mode", "default"),
    )
    engine = PiperEngine(
        length_scale=float(vcfg.get("length_scale", 0.95)),
        pitch_semitones=float(vcfg.get("pitch_semitones", 0.0)),
    )
    speaker = Speaker(engine, output_device=int(cfg.get("audio", {}).get("output_device", -1)))

    cmd_cooldown = Cooldown(float(cfg.get("commands", {}).get("cooldown", 0)))
    filters = cfg.get("filters", {})

    def on_event(ev):
        # Channel point redeems: own template + [name] voice prefix, random fallback
        if ev.kind == "redeem":
            rewards = {r["title"].lower(): r
                       for r in cfg.get("redeems", {}).get("reward", [])}
            rd = rewards.get(ev.reward_title.lower())
            if not rd:
                print(f"[Redeem] '{ev.reward_title}' not configured for TTS — skipping")
                return
            vname, clean = parse_voice_prefix(ev.message)
            line = clean_text(rd.get("template", "{message}").format(
                user=ev.user, message=clean))
            if not line:
                return
            voice = pool.find(vname) or pool.random_voice()
            speaker.enqueue(line, voice)
            print(f"[Redeem] ({ev.reward_title}) voice={vname or 'random'} :: {line}")
            return

        # Subs / cheers / raids / commands go through the template router
        line = to_line(ev, cfg)
        if not line:
            return
        if ev.kind == "command" and not cmd_cooldown.ready(ev.command):
            print(f"[Command] '{ev.command}' on cooldown "
                  f"({cmd_cooldown.remaining(ev.command):.0f}s)")
            return
        line = clean_text(line)
        if not line:
            return
        voice = pool.pick(user=ev.user)
        speaker.enqueue(line, voice)
        print(f"[Speak] ({ev.kind}) {line}")

    # --- Twitch chat (anonymous IRC) ---
    tw = TwitchChat(
        channel=cfg["twitch"]["channel"],
        on_event=on_event,
        ignore_users=filters.get("ignore_users", []),
        max_chars=int(filters.get("max_chars", 300)),
        command_prefix=cfg.get("commands", {}).get("prefix", "!"),
    )
    tw.start()

    # --- Channel point redeems (EventSub, needs one-time login) ---
    es = None
    redeems_cfg = cfg.get("redeems", {})
    if redeems_cfg.get("enabled") and redeems_cfg.get("reward"):
        auth = TwitchAuth(str(root / "token.json"))
        if auth.ensure():
            from eventsub import EventSubClient
            es = EventSubClient(auth, on_event)
            es.start()
            print(f"[Redeems] listening for #{auth.login} (id {auth.user_id})")
        else:
            print("[Redeems] disabled — authorization not completed.")

    print("[Main] Running. Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] Shutting down.")
        tw.stop()
        if es:
            es.stop()
        speaker.stop()


if __name__ == "__main__":
    main()