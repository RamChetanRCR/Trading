"""Optional push alerts. Credentials come from environment variables only — never the config file.

* ntfy.sh  : set NEWSSCAN_NTFY_TOPIC (free phone push via the ntfy app)
* Telegram : set NEWSSCAN_TELEGRAM_TOKEN and NEWSSCAN_TELEGRAM_CHAT_ID
"""

from __future__ import annotations

import os

import requests


def send(title: str, body: str) -> list[str]:
    """Send to every configured channel. Returns the channels that succeeded."""
    sent = []
    topic = os.getenv("NEWSSCAN_NTFY_TOPIC")
    if topic:
        server = os.getenv("NEWSSCAN_NTFY_SERVER", "https://ntfy.sh")
        try:
            requests.post(f"{server}/{topic}", data=body.encode(), headers={"Title": title}, timeout=10)
            sent.append("ntfy")
        except requests.RequestException:
            pass
    token, chat = os.getenv("NEWSSCAN_TELEGRAM_TOKEN"), os.getenv("NEWSSCAN_TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": f"{title}\n\n{body}"}, timeout=10)
            sent.append("telegram")
        except requests.RequestException:
            pass
    return sent
