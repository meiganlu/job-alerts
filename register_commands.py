"""Registers Katara's slash commands in my server."""
import os

import httpx

from jobalerts import config  # noqa: F401 (importing loads .env)

COMMANDS = [{
    "name": "restore",
    "description": "Send a filtered job from the digest to #maybe",
    "options": [{"type": 3, "name": "code", "required": True,
                 "description": "The #code from the digest, e.g. a3f9c1"}],
}]

url = (f"https://discord.com/api/v10/applications/{os.environ['DISCORD_APP_ID']}"
       f"/guilds/{os.environ['DISCORD_GUILD_ID']}/commands")
response = httpx.put(url, json=COMMANDS, timeout=10,
                     headers={"Authorization": f"Bot {os.environ['DISCORD_BOT_TOKEN']}"})
response.raise_for_status()
print("Registered:", ["/" + command["name"] for command in response.json()])