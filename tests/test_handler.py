import pytest

from jobalerts import handler


def test_crash_is_reported_and_still_fails(monkeypatch):
    posted = []
    monkeypatch.setattr(handler.notifier, "send_text", lambda channel, text: posted.append((channel, text)))

    with pytest.raises(RuntimeError):
        handler.poll({"test_crash": True}, None)

    assert posted[0][0] == "system_health"
    assert "poller failed" in posted[0][1]


def test_report_never_hides_the_original_error(monkeypatch):
    def broken_discord(channel, text):
        raise ConnectionError("Discord is down")
    monkeypatch.setattr(handler.notifier, "send_text", broken_discord)

    with pytest.raises(RuntimeError):  # the original crash, not ConnectionError
        handler.poll({"test_crash": True}, None)