from jobalerts import notifier
from jobalerts.digest import build_digest_lines, chunk
from tests.test_digest import ROWS

for message in chunk(build_digest_lines(ROWS)):
    notifier.send_text("filtered_out", message)
print("Sample digest sent to #filtered-out")