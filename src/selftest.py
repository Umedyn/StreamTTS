import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VC_REDIST = "https://aka.ms/vs/17/release/vc_redist.x64.exe"


def _load_config():
    path = os.path.join(_ROOT, "config.toml")
    if not os.path.exists(path):
        print(f"    [warn] no config.toml at {path}; using defaults")
        return {}
    try:
        import tomllib
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"    [warn] failed to read config.toml: {e}")
        return {}


def _device_from(cfg):
    d = int(cfg.get("audio", {}).get("output_device", -1))
    return None if d < 0 else d


# ---------------------------------------------------------------- checks

def check_python():
    print("[1/5] Python version")
    print(f"    {sys.version.split()[0]} @ {sys.executable}")
    ok = sys.version_info >= (3, 11)
    print("    [ok] 3.11+ (tomllib present)" if ok
          else "    [FAIL] need 3.11+ for tomllib")
    return ok


def check_deps():
    print("[2/5] Dependencies")
    targets = [
        ("numpy",        lambda: __import__("numpy"),                 None),
        ("sounddevice",  lambda: __import__("sounddevice"),           None),
        ("onnxruntime",  lambda: __import__("onnxruntime"),
         f"onnxruntime failed to load — usually a missing MSVC runtime.\n"
         f"           Install the VC++ Redistributable: {VC_REDIST}"),
        ("piper",        lambda: (__import__("piper.voice",
                                            fromlist=["PiperVoice"])), None),
    ]
    ok = True
    for name, imp, hint in targets:
        try:
            imp()
            print(f"    [ok] {name}")
        except Exception as e:
            ok = False
            print(f"    [FAIL] {name}: {e}")
            if hint:
                print(f"           {hint}")
    return ok


def check_audio(cfg):
    print("[3/5] Audio output (440 Hz tone)")
    try:
        import numpy as np
        import sounddevice as sd
    except Exception as e:
        print(f"    [FAIL] cannot import audio libs: {e}")
        return False
    dev = _device_from(cfg)
    print(f"    device index: {dev if dev is not None else 'system default'}")
    try:
        sr = 48000
        t = np.linspace(0, 0.8, int(sr * 0.8), endpoint=False)
        tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        sd.play(tone, samplerate=sr, device=dev)
        sd.wait()
    except Exception as e:
        print(f"    [FAIL] playback error: {e}")
        print("           Run `run.bat --list-devices` and set audio.output_device.")
        return False
    ans = input("    Did you hear the tone? [y/N] ").strip().lower()
    ok = ans == "y"
    print("    [ok] audio device works" if ok
          else "    [FAIL] no sound — check output_device and Windows volume/mixer")
    return ok


def check_tts(cfg):
    print("[4/5] Piper synthesis")
    try:
        import sounddevice as sd
        from voices import VoicePool
        from tts import PiperEngine
    except Exception as e:
        print(f"    [FAIL] import error: {e}")
        return False

    vcfg = cfg.get("voices", {})
    folder = os.path.join(_ROOT, vcfg.get("folder", "voices"))
    try:
        pool = VoicePool(folder=folder,
                         default=vcfg.get("default", ""),
                         mode=vcfg.get("mode", "default"))
    except Exception as e:
        print(f"    [FAIL] voice pool: {e}")
        print(f"           Put matching .onnx + .onnx.json pairs in {folder}")
        return False

    print(f"    {len(pool.voices)} voice(s) found; using {os.path.basename(pool.default)}")
    engine = PiperEngine(length_scale=float(vcfg.get("length_scale", 0.95)),
                         pitch_semitones=float(vcfg.get("pitch_semitones", 0.0)))
    samples, sr = engine.render(
        "Stream T T S test. If you can hear this, Piper is working.", pool.default)
    if samples is None:
        print("    [FAIL] synthesis returned no audio")
        return False
    try:
        sd.play(samples, samplerate=sr, device=_device_from(cfg))
        sd.wait()
    except Exception as e:
        print(f"    [FAIL] playback error: {e}")
        return False
    ans = input("    Did you hear the spoken line? [y/N] ").strip().lower()
    ok = ans == "y"
    print("    [ok] Piper end-to-end works" if ok
          else "    [FAIL] synthesized but no audio — recheck device")
    return ok


def check_twitch(cfg, channel_override=None):
    print("[5/5] Twitch IRC connection")
    try:
        from twitch import TwitchChat
    except Exception as e:
        print(f"    [FAIL] import error: {e}")
        return False

    channel = channel_override or cfg.get("twitch", {}).get("channel", "")
    if not channel or channel == "your_channel_name":
        print("    [warn] no real channel set. Set [twitch] channel in config.toml,")
        print("           or run: python src\\selftest.py twitch <channel>")
        print("           Tip: use a large, currently-LIVE channel for a real test.")
        return None

    print(f"    connecting anonymously, joining #{channel} ...")
    state = {"lines": 0, "privmsgs": 0}

    tw = TwitchChat(channel=channel, on_event=lambda ev: None)

    orig_handle = tw._handle
    def tapped_handle(line):
        state["lines"] += 1
        orig_handle(line)
    tw._handle = tapped_handle

    orig_privmsg = tw._privmsg
    def tapped_privmsg(tags, source, text):
        state["privmsgs"] += 1
        user = tags.get("display-name") or (source.split("!", 1)[0])
        print(f"    chat > {user}: {text[:60]}")
        orig_privmsg(tags, source, text)
    tw._privmsg = tapped_privmsg

    tw.start()
    connected = False
    deadline = time.time() + 20
    while time.time() < deadline:
        if state["lines"] > 0 and not connected:
            connected = True
            print("    [ok] server responded — connection established")
        if state["privmsgs"] >= 3:
            break
        time.sleep(0.3)
    tw.stop()

    if not connected:
        print("    [FAIL] no response in 20s — check network/firewall (TLS 6697),")
        print("           DNS, or that irc.chat.twitch.tv is reachable.")
        return False
    if state["privmsgs"] == 0:
        print("    [warn] connected, but saw no chat. Channel may be offline/quiet.")
        print("           Re-run against a busy live channel to confirm parsing.")
        return None
    print(f"    [ok] received {state['privmsgs']} chat message(s) — parser works")
    return True


# ---------------------------------------------------------------- runner

def main():
    args = [a.lower() for a in sys.argv[1:]]
    cfg = _load_config()

    # allow: selftest.py twitch <channel>
    twitch_channel = None
    if "twitch" in args:
        i = args.index("twitch")
        if i + 1 < len(args):
            twitch_channel = args[i + 1]

    only = {a for a in args if a in ("python", "deps", "audio", "tts", "twitch")}
    run = (lambda name: name in only) if only else (lambda name: True)

    print("=" * 48)
    print(" StreamTTS self-test")
    print("=" * 48)

    results = {}
    if run("python"): results["python"] = check_python(); print()
    if run("deps"):   results["deps"]   = check_deps();   print()
    if run("audio"):  results["audio"]  = check_audio(cfg); print()
    if run("tts"):    results["tts"]    = check_tts(cfg);   print()
    if run("twitch"): results["twitch"] = check_twitch(cfg, twitch_channel); print()

    print("=" * 48)
    for k, v in results.items():
        tag = "PASS" if v is True else ("WARN/SKIP" if v is None else "FAIL")
        print(f"  {k:<8} {tag}")
    print("=" * 48)

    if any(v is False for v in results.values()):
        input("\nSome checks failed. Press Enter to close.")
        sys.exit(1)
    input("\nPress Enter to close.")


if __name__ == "__main__":
    main()