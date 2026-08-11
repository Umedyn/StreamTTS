from __future__ import annotations
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

# Registered ONCE by the developer at https://dev.twitch.tv/console/apps
# Client Type must be "Public" (Device Code Flow). No client secret is used.
CLIENT_ID = "nmo40rz1ne53xxi5l30t57i0js5z25"          # <-- paste your app's Client ID here

SCOPES = ["channel:read:redemptions"]

_DEVICE_URL   = "https://id.twitch.tv/oauth2/device"
_TOKEN_URL    = "https://id.twitch.tv/oauth2/token"
_VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
_DCF_GRANT    = "urn:ietf:params:oauth:grant-type:device_code"


def _post_form(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def _get(url, headers):
    req = urllib.request.Request(url, method="GET")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


class TwitchAuth:
    def __init__(self, token_path, client_id="", scopes=None):
        self.client_id = (client_id or CLIENT_ID).strip()
        self.scopes = scopes or SCOPES
        self.token_path = Path(token_path)
        self.access_token = ""
        self.refresh_token = ""
        self.expires_at = 0.0
        self.user_id = ""
        self.login = ""
        self._load()

    # ---------- storage ----------
    def _load(self):
        if self.token_path.exists():
            try:
                d = json.loads(self.token_path.read_text())
                self.access_token = d.get("access_token", "")
                self.refresh_token = d.get("refresh_token", "")
                self.expires_at = float(d.get("expires_at", 0))
                self.user_id = d.get("user_id", "")
                self.login = d.get("login", "")
            except Exception as e:
                print(f"[Auth] could not read token file: {e}")

    def _save(self):
        try:
            self.token_path.write_text(json.dumps({
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at,
                "user_id": self.user_id,
                "login": self.login,
            }, indent=2))
        except Exception as e:
            print(f"[Auth] could not save token file: {e}")

    # ---------- public entry point ----------
    def ensure(self, force_login=False) -> bool:
        """Guarantee a valid access token. Returns True on success."""
        if not self.client_id:
            print("[Auth] No Client ID set. The developer must register a Twitch app "
                  "(Public client) and set CLIENT_ID in src/auth.py.")
            return False
        if force_login:
            return self._device_login()
        if self.access_token and self._validate():
            return True
        if self.refresh_token and self._refresh():
            return True
        return self._device_login()

    def get_access_token(self) -> str:
        return self.access_token

    # ---------- flows ----------
    def _validate(self) -> bool:
        status, d = _get(_VALIDATE_URL, {"Authorization": f"OAuth {self.access_token}"})
        if status == 200:
            self.user_id = d.get("user_id", self.user_id)
            self.login = d.get("login", self.login)
            self.expires_at = time.time() + int(d.get("expires_in", 0))
            self._save()
            return True
        return False

    def _refresh(self) -> bool:
        status, d = _post_form(_TOKEN_URL, {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
        })
        if status == 200 and d.get("access_token"):
            self.access_token = d["access_token"]
            # DCF refresh tokens are single-use — store the NEW one every time.
            self.refresh_token = d.get("refresh_token", self.refresh_token)
            self.expires_at = time.time() + int(d.get("expires_in", 0))
            self._save()
            self._validate()          # populate user_id / login
            print("[Auth] Token refreshed.")
            return True
        print(f"[Auth] Refresh failed ({status}); re-login required.")
        self.refresh_token = ""
        return False

    def _device_login(self) -> bool:
        status, d = _post_form(_DEVICE_URL, {
            "client_id": self.client_id,
            "scopes": " ".join(self.scopes),
        })
        if status != 200 or "device_code" not in d:
            print(f"[Auth] Could not start device login ({status}): {d}")
            return False

        device_code = d["device_code"]
        interval    = int(d.get("interval", 5))
        expires_in  = int(d.get("expires_in", 1800))
        user_code   = d.get("user_code", "")
        verify      = d.get("verification_uri", "https://www.twitch.tv/activate")

        print("\n" + "=" * 52)
        print(" Connect your Twitch account (channel point redeems)")
        print("=" * 52)
        print(f"  1. Go to:      {verify}")
        print(f"  2. Enter code: {user_code}")
        print("  Waiting for authorization...\n")

        deadline = time.time() + expires_in
        while time.time() < deadline:
            time.sleep(interval)
            status, t = _post_form(_TOKEN_URL, {
                "client_id": self.client_id,
                "scopes": " ".join(self.scopes),
                "device_code": device_code,
                "grant_type": _DCF_GRANT,
            })
            if status == 200 and t.get("access_token"):
                self.access_token = t["access_token"]
                self.refresh_token = t.get("refresh_token", "")
                self.expires_at = time.time() + int(t.get("expires_in", 0))
                self._save()
                self._validate()
                print(f"[Auth] Connected as {self.login}. You won't need to do this again.")
                return True
            if "slow" in (t.get("message") or "").lower():
                interval += 1     # server asked us to back off
            # otherwise authorization is still pending — keep polling
        print("[Auth] Device login timed out. Restart to try again.")
        return False