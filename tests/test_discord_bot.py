import json

from nacl.signing import SigningKey

from jobalerts import discord_bot
from jobalerts.decide import Decision
from jobalerts.dedupe import title_key
from jobalerts.models import Job
from jobalerts.store import SeenStore


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


def test_button_click_is_acknowledged(monkeypatch):
    monkeypatch.setenv("DISCORD_PUBLIC_KEY", PUBLIC)
    started = []
    click = {"type": 3, "data": {"custom_id": "applied:x"}}
    response = discord_bot.handle_request(signed_event(click), start_work=started.append)
    assert json.loads(response["body"]) == {"type": 6}
    assert started == [click]


def test_click_records_and_greys_out_button():
    store = SeenStore(":memory:")
    job = Job(source="greenhouse", company="Affirm", job_id="1", title="Software Engineer (SF)",
              location="San Francisco", url="https://example.com/1")
    store.save_decision(job, Decision(channel="apply_now", reason="x"))
    button = discord_bot.click_applied(store, f"applied:{job.key}")[0]["components"][0]
    assert button["disabled"] is True
    assert button["label"].startswith("🍀 Applied ")
    assert store.applied_at(title_key(job)) is not None