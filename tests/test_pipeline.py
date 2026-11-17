from collections import Counter

from jobalerts import pipeline
from jobalerts.models import Job


class FakeStore:
    def __init__(self):
        self.forgotten = []

    def applied_at(self, title_key):
        return None

    def save_decision(self, job, decision):
        pass

    def forget(self, key, fingerprint=None):
        self.forgotten.append(key)


def test_failed_alert_is_retried_next_run(monkeypatch):
    def discord_down(*args, **kwargs):
        raise RuntimeError("Discord said 503")

    monkeypatch.setattr(pipeline.notifier, "send", discord_down)
    monkeypatch.setattr(pipeline, "second_opinion", lambda job, decision, store: decision)
    job = Job(source="greenhouse", company="Acme", job_id="1", title="Software Engineer, New Grad",
              location="Remote US", url="https://example.com/1")
    store, counts = FakeStore(), Counter()
    assert pipeline.process(job, store, counts) is False
    assert store.forgotten == [job.key]
    assert counts["failed"] == 1
