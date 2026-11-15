from jobalerts.digest import build_digest_lines, chunk, short_code

ROWS = [
    {"job_key": "greenhouse:Upstart:7", "company": "Upstart", "title": "Software Engineer",
     "url": "https://example.com/7", "location": "Remote US", "channel": "drop",
     "reason": '3+ years required: "+ 3 years of experience"', "tags": "[]"},
    {"job_key": "greenhouse:Zscaler:9", "company": "Zscaler", "title": "Production Engineer",
     "url": "https://example.com/9", "location": "San Jose, CA", "channel": "digest",
     "reason": "meets 20% of required qualifications", "tags": "[]"},
]


def test_empty_digest_says_so():
    assert build_digest_lines([]) == ["✅ Nothing filtered in the last 24 hours."]


def test_jobs_have_codes_and_are_grouped():
    text = "\n".join(build_digest_lines(ROWS))
    code = short_code("greenhouse:Upstart:7")
    assert f"`#{code}` [Upstart: Software Engineer]" in text
    assert text.index("🔇 Dropped") < text.index("📋 Low match")


def test_short_code_is_stable():
    assert short_code("greenhouse:Upstart:7") == short_code("greenhouse:Upstart:7")
    assert len(short_code("greenhouse:Upstart:7")) == 6


def test_chunk_respects_discord_limit():
    messages = chunk(["x" * 500] * 10)
    assert len(messages) > 1
    assert all(len(m) <= 1900 for m in messages)