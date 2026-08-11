import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from voices import VoicePool
from tts import PiperEngine, Speaker
from twitch import TwitchChat
from events import to_line
from normalize import clean_text
from cooldown import Cooldown

cmd_cooldown = Cooldown(float(cfg.get("commands", {}).get("cooldown", 0)))


def main():
    if "--list-devices" in sys.argv:
        import sounddevice as sd
        print(sd.query_devices())
        return

    root = Path(__file__).resolve().parent.parent
    with open(root / "config.toml", "rb") as f:
        cfg = tomllib.load(f)

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

    filters = cfg.get("filters", {})

    def on_event(ev):
        line = to_line(ev, cfg)
        if not line:
            return
        if ev.kind == "command" and not cmd_cooldown.ready(ev.command):
            print(f"[Command] '{ev.command}' on cooldown ({cmd_cooldown.remaining(ev.command):.0f}s)")
            return
        line = clean_text(line)
        if not line:
            return
        voice = pool.pick(user=ev.user)
        speaker.enqueue(line, voice)
        print(f"[Speak] ({ev.kind}) {line}")

    tw = TwitchChat(
        channel=cfg["twitch"]["channel"],
        on_event=on_event,
        ignore_users=filters.get("ignore_users", []),
        max_chars=int(filters.get("max_chars", 300)),
        command_prefix=cfg.get("commands", {}).get("prefix", "!"),
    )
    tw.start()
    print("[Main] Running. Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] Shutting down.")
        tw.stop()
        speaker.stop()


if __name__ == "__main__":
    main()