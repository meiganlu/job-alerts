"""Runs the job-alert pipeline once. Examples:
  python run_once.py --baseline     # mark everything open now as seen, no alerts
  python run_once.py --limit 3      # process at most 3 new jobs
"""
import argparse

from jobalerts.pipeline import run
from jobalerts.store import SeenStore

parser = argparse.ArgumentParser(description="Run the job-alert pipeline once.")
parser.add_argument("--baseline", action="store_true",
                    help="mark all current jobs as seen without alerting")
parser.add_argument("--limit", type=int, default=10,
                    help="max new jobs to send to the LLM this run (default 10)")
args = parser.parse_args()

counts = run(SeenStore("seen.db"), baseline=args.baseline, limit=args.limit)
print("\nSummary:", dict(counts))