"""Optional push alerts. Credentials come from environment variables only — never the config file.

* ntfy.sh  : set NEWSSCAN_NTFY_TOPIC (free phone push via the ntfy app)
* Telegram : set NEWSSCAN_TELEGRAM_TOKEN and NEWSSCAN_TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import os
import sys
from urllib.parse import quote

import requests


def _fail(channel: str, err: Exception | str) -> None:
    # Never print the URL: for Telegram it contains the bot token.
    msg = f"{type(err).__name__}" if isinstance(err, Exception) else err
    if isinstance(err, requests.HTTPError) and err.response is not None:
        msg = f"HTTP {err.response.status_code}"
    print(f"warning: {channel} alert failed ({msg})", file=sys.stderr)


def send(title: str, body: str) -> list[str]:
    """Send to every configured channel. Returns only the channels that confirmed delivery."""
    sent = []
    topic = os.getenv("NEWSSCAN_NTFY_TOPIC")
    if topic:
        server = os.getenv("NEWSSCAN_NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        if not server.startswith("https://"):
            _fail("ntfy", "NEWSSCAN_NTFY_SERVER must be an https:// URL")
        else:
            try:
                r = requests.post(f"{server}/{quote(topic, safe='')}", data=body.encode("utf-8"),
                                  headers={"Title": title.encode("ascii", "ignore").decode()}, timeout=10)
                r.raise_for_status()
                sent.append("ntfy")
            except requests.RequestException as e:
                _fail("ntfy", e)
    token, chat = os.getenv("NEWSSCAN_TELEGRAM_TOKEN"), os.getenv("NEWSSCAN_TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                              json={"chat_id": chat, "text": f"{title}\n\n{body}"}, timeout=10)
            r.raise_for_status()
            if not r.json().get("ok"):
                raise ValueError("Telegram returned ok=false")
            sent.append("telegram")
        except (requests.RequestException, ValueError) as e:
            _fail("telegram", e)
    return sent
