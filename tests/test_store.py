from jobalerts.decide import Decision
from jobalerts.models import Job
from jobalerts.store import SeenStore

JOB = Job(source="greenhouse", company="Affirm", job_id="1", title="Software Engineer",
          location="Remote US", url="https://example.com/1")


def test_decision_is_saved_and_read_back():
    store = SeenStore(":memory:")
    store.save_decision(JOB, Decision(channel="maybe", reason="test"))
    assert store.channel_for(JOB.key) == "maybe"


def test_forget_removes_key_and_fingerprint():
    store = SeenStore(":memory:")
    store.add_key(JOB.key)
    store.add_fingerprint("abc123", JOB.key)
    store.forget(JOB.key)
    assert not store.has_key(JOB.key)
    assert store.first_key_for("abc123") is None