from jobalerts import notifier
from jobalerts.decide import Decision
from jobalerts.digest import short_code
from jobalerts.models import Job
from jobalerts.restore import restore_job
from jobalerts.store import SeenStore

JOB = Job(source="greenhouse", company="Upstart", job_id="7", title="Software Engineer",
          location="Remote US", url="https://example.com/7")


def test_restore_sends_to_maybe(monkeypatch):
    sent = []
    monkeypatch.setattr(notifier, "send", lambda job, channel, *args: sent.append(channel))
    store = SeenStore(":memory:")
    store.save_decision(JOB, Decision(channel="drop", reason="3+ years"))

    reply = restore_job(store, "#" + short_code(JOB.key))

    assert sent == ["maybe"]
    assert store.channel_for(JOB.key) == "maybe"
    assert reply.startswith("♻️ Restored")


def test_unknown_code():
    assert restore_job(SeenStore(":memory:"), "zzzzzz").startswith("No filtered job")