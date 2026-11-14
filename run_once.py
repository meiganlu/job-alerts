"""Runs the job-alert pipeline once. Examples:
  python run_once.py --baseline     # mark everything open now as seen, no alerts
  python run_once.py --limit 3      # process at most 3 new jobs
"""
import argparse

from jobalerts.pipeline import run
from jobalerts.store import SeenStore
from jobalerts.dynamo_store import DynamoStore

parser = argparse.ArgumentParser(description="Run the job-alert pipeline once.")
parser.add_argument("--baseline", action="store_true",
                    help="mark all current jobs as seen without alerting")
parser.add_argument("--limit", type=int, default=10,
                    help="max new jobs to send to the LLM this run (default 10)")
parser.add_argument("--store", choices=["sqlite", "dynamo"], default="sqlite",
                    help="where to remember seen jobs (default sqlite)")
args = parser.parse_args()

store = DynamoStore() if args.store == "dynamo" else SeenStore("seen.db")
counts = run(store, baseline=args.baseline, limit=args.limit)
print("\nSummary:", dict(counts))