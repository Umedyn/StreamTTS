# StreamTTS

A lightweight, portable Twitch chat text-to-speech tool for streamers. It listens
to a channel's chat and speaks subs, resubs, gift subs, Prime subs, raids, cheers,
and configurable chat commands out loud through your audio device using
[Piper](https://github.com/OHF-Voice/piper1-gpl) — fully local, no cloud, no API keys.

Unzip it, add a voice, set your channel, double-click `run.bat`. That's it.

---

## Requirements

- **Windows 10 (build 1803+) or Windows 11**, 64-bit.
- **A Piper voice** (one `.onnx` + `.onnx.json` pair — see [Getting Voices](#getting-voices)).
- Python is **already bundled** in the `python\` folder. You do not need to install anything.

> **One possible gotcha:** Piper's audio backend (onnxruntime) needs the Microsoft
> Visual C++ Redistributable. Most PCs already have it (games and common apps install it).
> If the tool fails on startup with an onnxruntime import error, install it from
> <https://aka.ms/vs/17/release/vc_redist.x64.exe> and try again.

---

## Quick Start

1. **Unzip** the whole folder anywhere (Desktop is fine).
2. **Add a voice.** Download a Piper voice and drop both files into the `voices\`
   folder (see below). You need the `.onnx` **and** the matching `.onnx.json`.
3. **Set your channel.** Open `config.toml` in Notepad and change:
   ```toml
   [twitch]
   channel = "your_channel_name"   # your Twitch name, no leading '#'
   ```
4. **Run it.** Double-click `run.bat`. A console window opens and starts reading chat.
   Close the window (or press `Ctrl+C`) to stop.

To pick a specific speaker/headphones/virtual cable as output, see
[Audio Device](#audio-device).

---

## Getting Voices

Voices are **not** included (they're large and everyone wants a different one).
Download them free from the official Piper voice library:

**<https://huggingface.co/rhasspy/piper-voices/tree/main>**

You can **preview every voice first** here before downloading:
**<https://rhasspy.github.io/piper-samples/>**

### How the library is organized

Files are nested by language → locale → voice → quality:

```
en/  en_US/  lessac/  medium/  en_US-lessac-medium.onnx
                              en_US-lessac-medium.onnx.json
```

Quality tiers trade file size and CPU for clarity:

| Quality  | Size (approx) | Notes                                  |
|----------|---------------|----------------------------------------|
| `x_low`  | ~10 MB        | Tiny, robotic. Weak PCs only.          |
| `low`    | ~20 MB        | Fast, rough.                           |
| `medium` | ~40–60 MB     | **Recommended.** Good balance.         |
| `high`   | ~100+ MB      | Best quality, heaviest CPU load.       |

### The one rule that matters

**Every voice is two files, and you need both.** Piper will refuse to load a voice
if the `.onnx.json` is missing — this is the single most common setup mistake.

- `something.onnx`      ← the model
- `something.onnx.json` ← the config (must sit right next to the .onnx)

Put **both** directly inside `voices\`. Don't rename them and don't separate them.

### Downloading a single voice

On the Hugging Face page, click into the language/voice/quality folder, click a
file, then use the **download** button. Or grab it directly by URL using the
`resolve` path. For example, the popular `en_US-lessac-medium` voice:

```
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

> Don't `git clone` the whole repo — it's ~11.6 GB. You only need the one or few
> voices you actually want.

### A few good English starter voices

All single-speaker `medium` quality, safe defaults:

| Voice file name              | Style                    |
|------------------------------|--------------------------|
| `en_US-lessac-medium`        | Clear, neutral (classic) |
| `en_US-amy-medium`           | Warm female              |
| `en_US-ryan-medium`          | Male                     |
| `en_US-hfc_female-medium`    | Natural female           |
| `en_US-hfc_male-medium`      | Natural male             |
| `en_GB-alba-medium`          | British female           |

> **Note on multi-speaker voices** (e.g. `libritts`): the tool uses the default
> speaker (id 0) only — you can't pick a sub-voice from the config yet. Stick to
> single-speaker voices above unless you're fine with speaker 0.

### Using multiple voices

Drop as many voice pairs into `voices\` as you like, then set how the tool chooses
between them in `config.toml` under `[voices] mode` — see [Voice Modes](#voice-modes).

---

## Configuration

Everything lives in `config.toml`, edited in any text editor.

### Channel

```toml
[twitch]
channel = "your_channel_name"
```

### Audio Device

Leave `-1` for your Windows default output. To send TTS to a specific device
(headphones, a second output, or a virtual audio cable for OBS), first list the
devices:

```
run.bat --list-devices
```

Then set the index number you want:

```toml
[audio]
output_device = 7
```

### Voices

```toml
[voices]
folder = "voices"
default = ""            # a filename in voices/; "" = first one found
mode = "default"        # "default" | "random" | "per_user"
length_scale = 0.95     # >1.0 slower speech, <1.0 faster
pitch_semitones = 0.0   # naive shift — also changes speed. Leave at 0 unless experimenting.
```

#### Voice Modes

- **`default`** — always uses the `default` voice (or the first one found).
- **`random`** — picks a random voice from `voices\` for every message.
- **`per_user`** — each chatter is consistently mapped to the same voice, so a given
  person always sounds the same. Great for giving regulars a recognizable voice.

### Filters

```toml
[filters]
max_chars = 300                              # truncate long messages
ignore_users = ["nightbot", "streamelements", "moobot", "streamlabs"]
```

---

## What Gets Spoken

Each event type has an on/off switch and an editable template. Placeholders in
`{curly braces}` get filled in automatically.

| Event              | What triggers it                     | Placeholders available            |
|--------------------|--------------------------------------|-----------------------------------|
| `sub`              | New subscription                     | `{user}` `{tier}` `{message}`     |
| `resub`            | Resubscription                       | `{user}` `{tier}` `{months}` `{message}` |
| `prime`            | Sub/resub using Prime (optional override) | `{user}`                     |
| `subgift`          | Gifting a sub to one person          | `{user}` `{tier}` `{recipient}`   |
| `submysterygift`   | Gifting subs to the community        | `{user}` `{tier}` `{count}`       |
| `cheer`            | Bits / cheers                        | `{user}` `{bits}` `{message}`     |
| `raid`             | Incoming raid                        | `{user}` `{count}`                |

Example:

```toml
[events.resub]
enabled = true
template = "{user} resubscribed for {months} months at {tier}. {message}"
```

Set `enabled = false` on any event to silence just that type.

### Commands

Viewers can trigger TTS with a chat command. Define a prefix and a set of commands:

```toml
[commands]
prefix = "!"

[commands.map]
tts = "{user} says: {message}"
say = "{message}"
```

With the above, a chatter typing `!tts hello everyone` gets `Umedyn says: hello everyone`
spoken aloud. Add or remove commands freely; `{user}` and `{message}` are available.

> By default, ordinary chat messages are **not** read — only commands, so a busy
> chat doesn't turn into wall-to-wall noise.

---

## Testing Your Setup

A self-test checks each part in isolation so you know exactly what's wrong if
something doesn't work:

```
python\python.exe src\selftest.py
```

Or test one layer at a time:

```
python\python.exe src\selftest.py deps          check dependencies load (catches the VC++ issue)
python\python.exe src\selftest.py audio          play a test tone through your device
python\python.exe src\selftest.py tts            synthesize + play a real Piper line
python\python.exe src\selftest.py twitch xqc     connect to a live channel and read chat
```

---

## Troubleshooting

**"Missing python bundle" when I run it.**
The `python\` folder didn't come through. Re-unzip the full download without leaving
anything out.

**onnxruntime / DLL load error on startup.**
Install the Visual C++ Redistributable: <https://aka.ms/vs/17/release/vc_redist.x64.exe>

**No sound.**
Run `run.bat --list-devices`, confirm the right output index, set it under
`[audio] output_device`, and check Windows volume/mixer isn't muting the console app.

**"No .onnx voices found" or a voice won't load.**
Make sure both the `.onnx` and its `.onnx.json` are in `voices\`, together, unrenamed.
A missing `.onnx.json` is the usual cause.

**Connects but never speaks.**
If your channel is offline or quiet, there's nothing to read. Confirm the channel
name is spelled right and try while live. Remember: normal chat isn't spoken —
only commands and sub/cheer/raid events.

**Windows SmartScreen warns on first run.**
Because the files aren't code-signed, Windows may show a "protected your PC" prompt.
Click **More info → Run anyway**. (Only do this for a copy you trust.)

---

## Current Limitations

- **Cash donations** (Streamlabs / StreamElements / Ko-fi) are **not** supported yet.
  Those don't come through Twitch chat and need a separate connection with your own
  token — planned as an add-on.
- **All-chat mode** (reading every message) is off by design. Only commands and
  events are spoken.
- **Multi-speaker voices** use speaker 0 only.

---

## Credits & License

- **[Piper](https://github.com/OHF-Voice/piper1-gpl)** — the local TTS engine.
- **[Piper Voices](https://huggingface.co/rhasspy/piper-voices)** by Rhasspy /
  Michael Hansen — MIT licensed voice models.
- Connects to Twitch chat anonymously over IRC (read-only); no account or OAuth needed.

Built by Umedyn.
