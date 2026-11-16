"""One-time: Katara creates a webhook in each channel. Prints .env lines to copy."""
import os

import httpx

from jobalerts import config  # noqa: F401 (importing loads .env)

API = "https://discord.com/api/v10"
HEADERS = {"Authorization": f"Bot {os.environ['DISCORD_BOT_TOKEN']}"}
CHANNELS = {  # channel name → (webhook name, .env setting)
    "apply-now": ("Aang", "DISCORD_WEBHOOK_APPLY_NOW"),
    "maybe": ("Sokka", "DISCORD_WEBHOOK_MAYBE"),
    "filtered-out": ("Zuko", "DISCORD_WEBHOOK_FILTERED_OUT"),
    "system-health": ("Toph", "DISCORD_WEBHOOK_SYSTEM_HEALTH"),
}

channels = httpx.get(f"{API}/guilds/{os.environ['DISCORD_GUILD_ID']}/channels",
                     headers=HEADERS, timeout=10)
channels.raise_for_status()
for channel in channels.json():
    if channel["name"] in CHANNELS:
        name, setting = CHANNELS[channel["name"]]
        hook = httpx.post(f"{API}/channels/{channel['id']}/webhooks", headers=HEADERS,
                          json={"name": name}, timeout=10)
        hook.raise_for_status()
        webhook = hook.json()
        print(f"{setting}=https://discord.com/api/webhooks/{webhook['id']}/{webhook['token']}")