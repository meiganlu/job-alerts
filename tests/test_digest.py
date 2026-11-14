from jobalerts.digest import build_digest_lines, chunk

ROWS = [
    (7, "Upstart", "Software Engineer", "https://example.com/7", "drop",
     '3+ years required: "+ 3 years of experience"'),
    (9, "Zscaler", "Production Engineer", "https://example.com/9", "digest",
     "meets 20% of required qualifications"),
]


def test_empty_digest_says_so():
    assert build_digest_lines([]) == ["✅ Nothing filtered in the last 24 hours."]


def test_jobs_are_numbered_and_grouped():
    text = "\n".join(build_digest_lines(ROWS))
    assert "🔇 Dropped" in text and "📋 Low match" in text
    assert "`#7` [Upstart: Software Engineer]" in text
    assert text.index("#7") < text.index("📋")  # drops listed before low matches


def test_chunk_respects_discord_limit():
    lines = ["x" * 500] * 10  # 5,000+ characters total
    messages = chunk(lines)
    assert len(messages) > 1
    assert all(len(m) <= 1900 for m in messages)