"""Where the demo keeps its state: the approval queue and the ledger it records into.

In memory by default (tests, local runs). With FIRESTORE_DATABASE set, in Firestore, so call logs,
approvals and what the ledger learned survive the service scaling to zero. Documents hold the queue
item or the ledger as JSON; originals are never stored.
"""

import os
from functools import cache
from typing import Protocol

QUEUE = "payguard_queue"
LEDGER = "payguard_ledger"


class Backend(Protocol):
    def get(self, collection: str, key: str) -> dict | None: ...
    def put(self, collection: str, key: str, value: dict) -> None: ...
    def clear(self, collection: str) -> None: ...


class Memory:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict]] = {}

    def get(self, collection: str, key: str) -> dict | None:
        return self._data.get(collection, {}).get(key)

    def put(self, collection: str, key: str, value: dict) -> None:
        self._data.setdefault(collection, {})[key] = value

    def clear(self, collection: str) -> None:
        self._data.pop(collection, None)


class Firestore:
    def __init__(self, database: str) -> None:
        from google.cloud import firestore

        self._db = firestore.Client(project=os.environ.get("GOOGLE_CLOUD_PROJECT"), database=database)

    def get(self, collection: str, key: str) -> dict | None:
        return self._db.collection(collection).document(key).get().to_dict()

    def put(self, collection: str, key: str, value: dict) -> None:
        self._db.collection(collection).document(key).set(value)

    def clear(self, collection: str) -> None:
        for doc in self._db.collection(collection).list_documents():
            doc.delete()


@cache
def backend() -> Backend:
    database = os.environ.get("FIRESTORE_DATABASE")
    return Firestore(database) if database else Memory()
