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


def test_decisions_since_returns_dicts():
    store = SeenStore(":memory:")
    store.save_decision(JOB, Decision(channel="drop", reason="3+ years"))
    rows = store.decisions_since("2000-01-01", ("drop",))
    assert rows[0]["job_key"] == JOB.key



def test_add_keys():
    store = SeenStore(":memory:")
    store.add_keys(["a", "b", "a"])
    assert store.has_key("a") and store.has_key("b")


def test_applied_tag_on_similar_title():
    from jobalerts.dedupe import title_key
    from jobalerts.pipeline import applied_tag
    store = SeenStore(":memory:")
    nyc = JOB.model_copy(update={"title": "Software Engineer (NYC)"})
    sf = JOB.model_copy(update={"job_id": "2", "title": "Software Engineer (SF)"})
    assert applied_tag(sf, store) == []
    store.mark_applied(title_key(nyc), nyc.key)
    assert applied_tag(sf, store)[0].startswith("🍀 You applied to a similar role on")