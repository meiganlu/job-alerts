from jobalerts.text import html_to_text, trim_boilerplate


def test_escaped_html_becomes_text():
    raw = "&lt;p&gt;Build APIs&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Python&lt;/li&gt;&lt;/ul&gt;"
    assert html_to_text(raw) == "Build APIs\nPython"


def test_empty_input():
    assert html_to_text("") == ""


POSTING = """About Acme
Benefits are mentioned up here, before qualifications.
Qualifications
- 2+ years of Python
Benefits
Health insurance, 401k
Equal Opportunity Employer
We welcome everyone."""


def test_cuts_sections_after_qualifications():
    trimmed = trim_boilerplate(POSTING)
    assert "2+ years of Python" in trimmed
    assert "Health insurance" not in trimmed
    assert "Equal Opportunity" not in trimmed


def test_keeps_everything_before_qualifications():
    assert "Benefits are mentioned up here" in trim_boilerplate(POSTING)


def test_no_end_sections_means_no_change():
    text = "Qualifications\n- Python"
    assert trim_boilerplate(text) == text