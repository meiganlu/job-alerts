"""Posts the last 24 hours of filtered jobs to #filtered-out (AWS runs it daily)."""
import argparse

from jobalerts.digest import send_daily_digest
from jobalerts.stores import open_store

parser = argparse.ArgumentParser(description="Send the daily digest.")
parser.add_argument("--store", choices=["dynamo", "sqlite"], default="dynamo")
args = parser.parse_args()

print(f"Digest sent: {send_daily_digest(open_store(args.store))} job(s)")