"""Re-sends a filtered job to #maybe from Terminal. Usage: python restore.py a3f9c1
(In Discord, /restore a3f9c1 does the same.)"""
import argparse

from jobalerts.restore import restore_job
from jobalerts.stores import open_store

parser = argparse.ArgumentParser(description="Restore a job from the daily digest.")
parser.add_argument("code", help="the #code shown in the digest, e.g. a3f9c1")
parser.add_argument("--store", choices=["dynamo", "sqlite"], default="dynamo")
args = parser.parse_args()

print(restore_job(open_store(args.store), args.code))