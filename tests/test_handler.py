import pytest

from jobalerts import handler


def test_crash_is_reported_with_a_ping(monkeypatch):
    posted = []
    monkeypatch.setattr(handler.notifier, "send_text",
                        lambda channel, text, ping=False: posted.append((channel, text, ping)))

    with pytest.raises(RuntimeError):
        handler.poll({"test_crash": True}, None)

    channel, text, ping = posted[0]
    assert channel == "system_health"
    assert "poller failed" in text
    assert ping is True


def test_report_never_hides_the_original_error(monkeypatch):
    def broken_discord(channel, text, ping=False):
        raise ConnectionError("Discord is down")
    monkeypatch.setattr(handler.notifier, "send_text", broken_discord)

    with pytest.raises(RuntimeError):  # the original crash, not ConnectionError
        handler.poll({"test_crash": True}, None)