import re
import ssl
import time
import socket
import random
import threading

from events import SpeakEvent, TIER_NAMES

HOST = "irc.chat.twitch.tv"
PORT = 6697
CHEER_TOKEN = re.compile(r"\bCheer\d+\b", re.IGNORECASE)


def _unescape(v: str) -> str:
    return (v.replace(r"\s", " ").replace(r"\:", ";")
             .replace(r"\r", "\r").replace(r"\n", "\n").replace("\\\\", "\\"))


def parse_line(line: str):
    tags, rest = {}, line
    if rest.startswith("@"):
        tag_str, rest = rest[1:].split(" ", 1)
        for kv in tag_str.split(";"):
            k, _, val = kv.partition("=")
            tags[k] = _unescape(val)
    source = ""
    if rest.startswith(":"):
        source, rest = rest[1:].split(" ", 1)
    head, _, trailing = rest.partition(" :")
    parts = head.split()
    command = parts[0] if parts else ""
    return tags, source, command, parts[1:], trailing


class TwitchChat(threading.Thread):
    def __init__(self, channel, on_event, ignore_users=None, max_chars=300, command_prefix="!"):
        super().__init__(daemon=True, name="twitch_irc")
        self.channel = channel.lower().lstrip("#")
        self.on_event = on_event
        self.ignore = {u.lower() for u in (ignore_users or [])}
        self.max_chars = int(max_chars)
        self.prefix = command_prefix or "!"
        self._stop = threading.Event()
        self.sock = None
        self._gift_origins = {}   # origin_id -> expiry; suppresses individual gifts of a mass gift

    def stop(self):
        self._stop.set()
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def _send(self, line: str):
        self.sock.sendall((line + "\r\n").encode("utf-8"))

    def _connect(self):
        raw = socket.create_connection((HOST, PORT), timeout=30)
        self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=HOST)
        nick = f"justinfan{random.randint(10000, 99999)}"
        self._send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        self._send(f"NICK {nick}")
        self._send(f"JOIN #{self.channel}")
        print(f"[Twitch] Connected as {nick}, joined #{self.channel}")

    def run(self):
        while not self._stop.is_set():
            try:
                self._connect()
                self._read_loop()
            except Exception as e:
                if self._stop.is_set():
                    break
                print(f"[Twitch] connection error: {e}; reconnecting in 5s")
                time.sleep(5)

    def _read_loop(self):
        buf = ""
        self.sock.settimeout(1.0)
        while not self._stop.is_set():
            try:
                data = self.sock.recv(4096)
            except socket.timeout:
                continue
            if not data:
                raise ConnectionError("socket closed")
            buf += data.decode("utf-8", errors="replace")
            while "\r\n" in buf:
                line, buf = buf.split("\r\n", 1)
                self._handle(line)

    def _from_mass_gift(self, origin):
            if not origin:
                return False
            now = time.time()
            self._gift_origins = {k: v for k, v in self._gift_origins.items() if v > now}
            return origin in self._gift_origins

    def _handle(self, line: str):
        tags, source, command, args, trailing = parse_line(line)
        if command == "PING":
            self._send(f"PONG :{trailing}")
        elif command == "RECONNECT":
            raise ConnectionError("server requested reconnect")
        elif command == "PRIVMSG":
            self._privmsg(tags, source, trailing)
        elif command == "USERNOTICE":
            self._usernotice(tags, trailing)

    @staticmethod
    def _login(source: str) -> str:
        return source.split("!", 1)[0] if "!" in source else source

    def _emit(self, ev: SpeakEvent):
        try:
            self.on_event(ev)
        except Exception as e:
            print(f"[Twitch] handler error: {e}")

    def _privmsg(self, tags, source, text):
        login = (tags.get("login") or self._login(source)).lower()
        if login in self.ignore:
            return
        user = tags.get("display-name") or self._login(source)
        text = (text or "").strip()

        bits = int(tags.get("bits") or 0)
        if bits > 0:
            msg = CHEER_TOKEN.sub("", text).strip()
            self._emit(SpeakEvent("cheer", user=user, message=msg[:self.max_chars], bits=bits))
            return

        if text.startswith(self.prefix):
            body = text[len(self.prefix):]
            cmd, _, rest = body.partition(" ")
            self._emit(SpeakEvent("command", user=user, command=cmd.lower(),
                                  message=rest.strip()[:self.max_chars]))
        # plain chat is ignored in v1 (see notes for an all-chat toggle)

    def _usernotice(self, tags, trailing):
        msg_id = (tags.get("msg-id") or "").lower()
        user = tags.get("display-name") or tags.get("login") or "Someone"
        plan = tags.get("msg-param-sub-plan") or ""
        tier = TIER_NAMES.get(plan, plan or "Tier 1")
        user_msg = (trailing or "").strip()[:self.max_chars]
        origin = tags.get("msg-param-origin-id") or ""

        if msg_id in ("sub", "resub"):
            months = int(tags.get("msg-param-cumulative-months")
                         or tags.get("msg-param-months") or 0)
            self._emit(SpeakEvent(msg_id, user=user, tier=tier, months=months, message=user_msg))
        elif msg_id in ("submysterygift", "anonsubmysterygift"):
            count = int(tags.get("msg-param-mass-gift-count") or 0)
            if origin:
                self._gift_origins[origin] = time.time() + 20   # mute its individual gifts
            self._emit(SpeakEvent("submysterygift", user=user, tier=tier, count=count))
        elif msg_id in ("subgift", "anonsubgift"):
            if self._from_mass_gift(origin):
                return                                          # already announced en masse
            recipient = (tags.get("msg-param-recipient-display-name")
                         or tags.get("msg-param-recipient-user-name") or "someone")
            self._emit(SpeakEvent("subgift", user=user, tier=tier, recipient=recipient))
        elif msg_id == "raid":
            raider = tags.get("msg-param-displayName") or user
            count = int(tags.get("msg-param-viewerCount") or 0)
            self._emit(SpeakEvent("raid", user=raider, count=count))
        # giftpaidupgrade / ritual / bitsbadgetier intentionally ignored