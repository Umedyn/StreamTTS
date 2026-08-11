from __future__ import annotations
import json
import ssl
import time
import threading
import urllib.request
import urllib.error

import websocket  # websocket-client

from events import SpeakEvent

WS_URL   = "wss://eventsub.wss.twitch.tv/ws"
SUB_URL  = "https://api.twitch.tv/helix/eventsub/subscriptions"
SUB_TYPE = "channel.channel_points_custom_reward_redemption.add"


class EventSubClient(threading.Thread):
    def __init__(self, auth, on_event, ws_url=WS_URL):
        super().__init__(daemon=True, name="eventsub")
        self.auth = auth
        self.on_event = on_event
        self.ws_url = ws_url
        self._stop = threading.Event()
        self.ws = None

    def stop(self):
        self._stop.set()
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass

    def run(self):
        backoff = 1
        url, resubscribe = self.ws_url, True
        while not self._stop.is_set():
            try:
                url, resubscribe = self._session(url, resubscribe)
                backoff = 1
            except Exception as e:
                if self._stop.is_set():
                    break
                print(f"[EventSub] connection error: {e}; retrying in {backoff}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                url, resubscribe = self.ws_url, True   # fresh session after an error
        print("[EventSub] stopped.")

    def _session(self, url, resubscribe):
        """Run one websocket session. Returns (next_url, next_resubscribe)."""
        self.ws = websocket.create_connection(
            url, timeout=15, sslopt={"cert_reqs": ssl.CERT_REQUIRED}
        )
        keepalive = 15
        subscribed = not resubscribe   # a migrated session already carries our sub

        while not self._stop.is_set():
            try:
                self.ws.settimeout(keepalive + 5)
                raw = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                raise ConnectionError("keepalive timeout")
            if not raw:
                raise ConnectionError("socket closed")

            msg     = json.loads(raw)
            mtype   = msg.get("metadata", {}).get("message_type", "")
            payload = msg.get("payload", {})

            if mtype == "session_welcome":
                session = payload.get("session", {})
                keepalive = int(session.get("keepalive_timeout_seconds") or 10)
                if not subscribed:
                    self._subscribe(session.get("id", ""))
                    subscribed = True

            elif mtype == "session_keepalive":
                pass

            elif mtype == "notification":
                self._handle_notification(payload)

            elif mtype == "session_reconnect":
                # Twitch is migrating us; connect to the new URL and DON'T re-subscribe.
                new_url = payload.get("session", {}).get("reconnect_url")
                if new_url:
                    try:
                        self.ws.close()
                    except Exception:
                        pass
                    return new_url, False

            elif mtype == "revocation":
                sub = payload.get("subscription", {})
                print(f"[EventSub] subscription revoked: {sub.get('status')}")
                self.auth.ensure()                       # token likely dead
                raise ConnectionError("revoked; reconnecting")

        try:
            self.ws.close()
        except Exception:
            pass
        return self.ws_url, True

    def _subscribe(self, session_id, _retry=True):
        body = json.dumps({
            "type": SUB_TYPE,
            "version": "1",
            "condition": {"broadcaster_user_id": self.auth.user_id},
            "transport": {"method": "websocket", "session_id": session_id},
        }).encode()
        req = urllib.request.Request(SUB_URL, data=body, method="POST")
        req.add_header("Client-Id", self.auth.client_id)
        req.add_header("Authorization", f"Bearer {self.auth.get_access_token()}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                if r.status in (200, 202):
                    print(f"[EventSub] subscribed to redemptions for #{self.auth.login}")
                    return True
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode()
            except Exception:
                pass
            if e.code == 401 and _retry and self.auth.ensure():
                print("[EventSub] token refreshed; retrying subscribe...")
                return self._subscribe(session_id, _retry=False)
            print(f"[EventSub] subscribe failed ({e.code}): {detail}")
        except Exception as e:
            print(f"[EventSub] subscribe error: {e}")
        return False

    def _handle_notification(self, payload):
        ev = payload.get("event", {})
        reward = ev.get("reward", {}) or {}
        speak = SpeakEvent(
            kind="redeem",
            user=ev.get("user_name") or ev.get("user_login") or "Someone",
            message=(ev.get("user_input") or "").strip(),
            reward_title=reward.get("title", ""),
            reward_id=reward.get("id", ""),
        )
        try:
            self.on_event(speak)
        except Exception as e:
            print(f"[EventSub] handler error: {e}")