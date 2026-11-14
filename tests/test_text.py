from jobalerts.text import html_to_text


def test_escaped_html_becomes_text():
    raw = "&lt;p&gt;Build APIs&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;"
    assert html_to_text(raw) == "Build APIs\nPython"


def test_empty_input():
    assert html_to_text("") == ""