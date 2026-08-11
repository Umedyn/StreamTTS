# StreamTTS

A lightweight, portable Twitch chat text-to-speech tool for streamers. It listens
to a channel's chat and speaks subs, resubs, gift subs, Prime subs, raids, cheers,
and configurable chat commands out loud through your audio device using
[Piper](https://github.com/OHF-Voice/piper1-gpl) — fully local, no cloud, no API keys
for the core features.

Set your channel, add a voice, run it. Works on Windows, macOS, and Linux.

---

## Contents

- [Install](#install)
- [Getting Voices](#getting-voices)
- [Configuration](#configuration)
- [What Gets Spoken](#what-gets-spoken)
- [Commands](#commands)
- [Channel Point Redeems](#channel-point-redeems-optional)
- [Testing Your Setup](#testing-your-setup)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

---

## Install

### Windows — the easy way (recommended)

Download the **Release `.zip`**, not the source code. The release already contains
the bundled `python\` folder, so there's nothing to install.

1. **Unzip** anywhere (Desktop is fine).
2. **Add a voice** — see [Getting Voices](#getting-voices).
3. **Set your channel** — open `config.toml`, change `channel = "your_channel_name"`.
4. **Double-click `run.bat`.**

### Windows — from source

If you cloned or downloaded the **source repo** instead of a release, the `python\`
folder won't be there — it's too large to host in the repo and is excluded from it.
You need to build it once:

1. **Run `build.bat`.** It downloads a portable Python, installs the dependencies,
   and creates the `python\` folder. This takes a few minutes and only needs to be
   done once (re-run it if you change `requirements.txt`).
2. Then follow the easy-way steps above (`run.bat` from there on).

> **In short:** using a release? Just `run.bat`. Using the source repo? `build.bat`
> once, then `run.bat`.

### macOS & Linux

There's no bundled Python on these platforms (Python doesn't ship a portable
embeddable build for them), so the launcher uses your system Python and sets itself
up on first run. You need **Python 3.11 or newer** installed.

1. Make the launcher executable once: `chmod +x run.sh`
2. **Add a voice** and **set your channel** (as above).
3. Run it: `./run.sh`

On first run it creates a `.venv` and installs dependencies automatically.

**If Python 3.11+ isn't installed:**

| OS | Install |
|----|---------|
| macOS | `brew install python@3.12` |
| Debian / Ubuntu | `sudo apt install python3 python3-venv libportaudio2` |
| Fedora | `sudo dnf install python3 portaudio` |
| Arch | `sudo pacman -S python portaudio` |

> **Linux users:** the `libportaudio2` / `portaudio` package is required — audio
> playback won't import without it. This is the Linux equivalent of the Windows
> VC++ step below.

### One dependency note (Windows)

Piper's audio backend (onnxruntime) needs the Microsoft Visual C++ Redistributable.
Most PCs already have it. If the tool fails on startup with an onnxruntime import
error, install it from <https://aka.ms/vs/17/release/vc_redist.x64.exe> and retry.

---

## Getting Voices

Voices aren't included (they're large and everyone wants a different one). Download
them free from the official Piper voice library:

**<https://huggingface.co/rhasspy/piper-voices/tree/main>**

Preview every voice first here:
**<https://rhasspy.github.io/piper-samples/>**

### The one rule that matters

**Every voice is two files, and you need both.** Piper refuses to load a voice if
the `.onnx.json` is missing — this is the most common setup mistake.

- `something.onnx`      ← the model
- `something.onnx.json` ← the config (must sit right next to the `.onnx`)

Put **both** directly inside `voices/`, unrenamed, together.

### Library layout & quality tiers

Files are nested by language → locale → voice → quality, e.g.
`en/en_US/lessac/medium/en_US-lessac-medium.onnx`.

| Quality  | Size    | Notes                              |
|----------|---------|------------------------------------|
| `x_low`  | ~10 MB  | Tiny, robotic. Weak hardware only. |
| `low`    | ~20 MB  | Fast, rough.                       |
| `medium` | ~40–60 MB | **Recommended.** Good balance.   |
| `high`   | ~100+ MB | Best quality, heaviest CPU.       |

### Downloading a single voice

Click into the folder on Hugging Face and use the download button, or grab it
directly by URL. Example for `en_US-lessac-medium`:

```
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

> Don't `git clone` the whole repo — it's ~11.6 GB. Grab only the voices you want.

### Good English starter voices

All single-speaker `medium` quality:

| Voice file                 | Style                    |
|----------------------------|--------------------------|
| `en_US-lessac-medium`      | Clear, neutral (classic) |
| `en_US-amy-medium`         | Warm female              |
| `en_US-ryan-medium`        | Male                     |
| `en_US-hfc_female-medium`  | Natural female           |
| `en_US-hfc_male-medium`    | Natural male             |
| `en_GB-alba-medium`        | British female           |

> Drop as many voice pairs into `voices/` as you like and pick how the tool chooses
> between them via `[voices] mode` (see below). Multi-speaker voices (e.g. `libritts`)
> use speaker 0 only.

---

## Configuration

Everything lives in `config.toml`, editable in any text editor.

### Channel & audio

```toml
[twitch]
channel = "your_channel_name"   # your Twitch name, no leading '#'

[audio]
# -1 = system default. List devices with: run.bat --list-devices  (or ./run.sh --list-devices)
output_device = -1
```

### Voices

```toml
[voices]
folder = "voices"
default = ""            # a filename in voices/; "" = first found
mode = "default"        # "default" | "random" | "per_user"
length_scale = 0.95     # >1.0 slower, <1.0 faster
pitch_semitones = 0.0   # naive shift — also changes speed. Leave at 0 normally.
```

- **`default`** — always the default voice.
- **`random`** — a random voice per message.
- **`per_user`** — each chatter is consistently mapped to the same voice.

### Filters

```toml
[filters]
max_chars = 300
ignore_users = ["nightbot", "streamelements", "moobot", "streamlabs"]
```

---

## What Gets Spoken

Each event has an on/off switch and an editable template. `{placeholders}` fill in
automatically.

| Event            | Trigger                       | Placeholders                        |
|------------------|-------------------------------|-------------------------------------|
| `sub`            | New subscription              | `{user}` `{tier}` `{message}`       |
| `resub`          | Resubscription                | `{user}` `{tier}` `{months}` `{message}` |
| `prime`          | Sub/resub via Prime (override)| `{user}`                            |
| `subgift`        | Gifting a sub to one person   | `{user}` `{tier}` `{recipient}`     |
| `submysterygift` | Gifting subs to the community | `{user}` `{tier}` `{count}`         |
| `cheer`          | Bits / cheers                 | `{user}` `{bits}` `{message}`       |
| `raid`           | Incoming raid                 | `{user}` `{count}`                  |

```toml
[events.resub]
enabled = true
template = "{user} resubscribed for {months} months at {tier}. {message}"
```

Set `enabled = false` on any event to silence just that type.

---

## Commands

Viewers can trigger TTS with a chat command. Commands are **off by default** — the
map ships as commented suggestions. Uncomment one to enable it.

```toml
[commands]
prefix = "!"
cooldown = 30          # seconds, per command. 0 = no cooldown.

# Suggested commands — uncomment and edit to enable. {user} and {message} available.
[commands.map]
# tts = "{user} says: {message}"
# say = "{message}"
```

With `tts` enabled, a viewer typing `!tts hello everyone` gets it spoken. The
`cooldown` throttles each command so nobody can flood the audio queue — by default a
command fires at most once every 30 seconds. Set `cooldown = 0` to disable.

---

## Channel Point Redeems (optional)

Unlike everything above, channel point redemptions are **not** available anonymously
— Twitch gates channel point data behind your own account. Reading them requires a
**one-time login** with your Twitch account (via EventSub). This is the only feature
that isn't zero-auth; if you don't set up the login, redeems simply won't fire and
everything else keeps working.

Rewards are matched by **title**:

```toml
[redeems]
enabled = true

[[redeems.reward]]
title = "Ask Sophia a Question"   # matched case-insensitively
template = "{user} asks: {message}"
```

### Picking a voice per redeem

A viewer can choose a voice by starting their message with `[voicename]`:

- `[amy] what's your favorite game?` → speaks in the `amy` voice
- `what's your favorite game?` → speaks in a **random** voice

The name matches against your voice filenames (e.g. `amy` matches
`en_US-amy-medium`).

---

## Testing Your Setup

A self-test checks each part in isolation so a failure tells you exactly what broke:

```
# Windows
python\python.exe src\selftest.py

# macOS / Linux
./.venv/bin/python src/selftest.py
```

Test one layer at a time:

```
selftest.py deps          dependencies load (catches the VC++ / PortAudio issue)
selftest.py audio         play a test tone through your device
selftest.py tts           synthesize + play a real Piper line
selftest.py twitch xqc    connect to a live channel and read chat
```

Run `deps` first on any new machine — it's the fastest way to catch a missing
runtime before anything else.

---

## Troubleshooting

**"Missing python bundle" on Windows.**
You're using the source repo, not a release. Run `build.bat` once, then `run.bat`.

**onnxruntime / DLL load error (Windows).**
Install the VC++ Redistributable: <https://aka.ms/vs/17/release/vc_redist.x64.exe>

**Import error mentioning PortAudio (Linux).**
Install it: `sudo apt install libportaudio2` (or your distro's `portaudio` package).

**No sound.**
List devices (`run.bat --list-devices` / `./run.sh --list-devices`), set the right
index under `[audio] output_device`, and check the OS volume/mixer for the app.

**"No .onnx voices found" or a voice won't load.**
Both the `.onnx` and its `.onnx.json` must be in `voices/`, together, unrenamed. A
missing `.onnx.json` is the usual cause.

**Connects but never speaks.**
If the channel is offline or quiet, there's nothing to read. Confirm the channel
name and try while live. Remember: ordinary chat isn't spoken — only commands and
sub/cheer/raid events.

**macOS won't open it ("unidentified developer").**
The files aren't signed. Allow it via System Settings → Privacy & Security → **Open
Anyway**, or run `xattr -d com.apple.quarantine run.sh` once.

**Windows SmartScreen warns on first run.**
Unsigned files trigger this. Click **More info → Run anyway** (only for a copy you
trust).

### Routing TTS into OBS

To send TTS to OBS instead of your speakers, install a virtual audio device and set
its index as `output_device`:

| OS | Virtual device |
|----|----------------|
| Windows | VB-Cable |
| macOS | BlackHole |
| Linux | PulseAudio / PipeWire null sink |

---

## Limitations

- **Cash donations** (Streamlabs / StreamElements / Ko-fi) aren't supported. They
  don't come through Twitch chat and need a separate connection with your own token.
- **Channel point redeems** require the one-time EventSub login described above;
  they're the only non-anonymous feature.
- **All-chat mode** (reading every message) is off by design — only commands and
  events are spoken.
- **Multi-speaker voices** use speaker 0 only.

---

## Project Layout

```
StreamTTS/
├─ run.bat            Windows launcher
├─ run.sh             macOS / Linux launcher
├─ build.bat          Windows: builds the python\ bundle (source installs only)
├─ requirements.txt
├─ config.toml
├─ python\            Windows bundle — in the RELEASE zip, not in the source repo
├─ voices\            your .onnx + .onnx.json pairs
└─ src\
   ├─ main.py
   ├─ twitch.py
   ├─ events.py
   ├─ voices.py
   ├─ tts.py
   ├─ cooldown.py
   ├─ normalize.py
   └─ selftest.py
```

`python\` (Windows) and `.venv/` (macOS/Linux) are generated locally and are not
part of the source repo — that's why source installs run `build.bat` / `run.sh`
first.

---

## Credits & License

- **[Piper](https://github.com/OHF-Voice/piper1-gpl)** — local TTS engine.
- **[Piper Voices](https://huggingface.co/rhasspy/piper-voices)** by Rhasspy /
  Michael Hansen — MIT-licensed voice models.
- Connects to Twitch chat anonymously over IRC (read-only) for core events; channel
  point redeems use Twitch EventSub with a one-time login.

Built by Umedyn.
