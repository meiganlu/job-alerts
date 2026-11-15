"""Opens the chosen store. DynamoDB is the default, so laptop & AWS share one memory."""
from jobalerts.dynamo_store import DynamoStore
from jobalerts.store import SeenStore


def open_store(kind: str = "dynamo"):
    return SeenStore("seen.db") if kind == "sqlite" else DynamoStore()