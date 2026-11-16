import json

from nacl.signing import SigningKey

from jobalerts import discord_bot

KEY = SigningKey.generate()
PUBLIC = KEY.verify_key.encode().hex()


def signed_event(payload: dict, key=KEY) -> dict:
    body, timestamp = json.dumps(payload), "1700000000"
    signature = key.sign((timestamp + body).encode()).signature.hex()
    return {"body": body, "headers": {"X-Signature-Ed25519": signature,
                                      "X-Signature-Timestamp": timestamp}}


def test_ping_gets_pong(monkeypatch):
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", PUBLIC)
    response = discord_bot.handle_request(signed_event({"type": 1}), start_work=None)
    assert json.loads(response["body"]) == {"type": 1}


def test_forged_request_is_rejected(monkeypatch):
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", PUBLIC)
    forged = signed_event({"type": 1}, key=SigningKey.generate())  # signed by someone else
    assert discord_bot.handle_request(forged, start_work=None)["statusCode"] == 401


def test_command_starts_work_and_says_thinking(monkeypatch):
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", PUBLIC)
    started = []
    command = {"type": 2, "data": {"name": "restore"}}
    response = discord_bot.handle_request(signed_event(command), start_work=started.append)
    assert json.loads(response["body"])["type"] == 5
    assert started == [command]