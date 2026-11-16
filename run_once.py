"""Runs the job-alert pipeline once locally (same as one Lambda run)."""
import argparse

from jobalerts.dynamo_store import DynamoStore
from jobalerts.pipeline import run

parser = argparse.ArgumentParser(description="Run the job-alert pipeline once.")
parser.add_argument("--limit", type=int, default=25,
                    help="max new jobs to process this run (default 25)")
args = parser.parse_args()

print("\nSummary:", dict(run(DynamoStore(), limit=args.limit)))