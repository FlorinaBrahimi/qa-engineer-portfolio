"""Pluggable storage for submissions.

* ``MemoryStore``: default, used in-process and in Docker.
* ``DynamoStore``: used on AWS Lambda, where instances come and go so state must live
  outside the process. Selected with ``STORAGE_BACKEND=dynamodb`` + ``SUBMISSIONS_TABLE``.

Both expose the same five methods so the Flask app does not care which one it has.
"""
from __future__ import annotations

import os
import threading
from decimal import Decimal


class MemoryStore:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}
        self._lock = threading.Lock()

    def put(self, submission: dict) -> None:
        with self._lock:
            self._items[submission["id"]] = submission

    def get(self, submission_id: str) -> dict | None:
        return self._items.get(submission_id)

    def delete(self, submission_id: str) -> bool:
        with self._lock:
            return self._items.pop(submission_id, None) is not None

    def list(self) -> list[dict]:
        with self._lock:
            items = list(self._items.values())
        return sorted(items, key=lambda s: s["created_at"], reverse=True)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def count(self) -> int:
        return len(self._items)


class DynamoStore:
    """DynamoDB-backed store. Floats are stored as Decimal (DynamoDB requirement) and
    converted back on read so API responses are identical to the memory backend."""

    def __init__(self, table_name: str, dynamodb_resource=None) -> None:
        import boto3

        resource = dynamodb_resource or boto3.resource("dynamodb")
        self.table = resource.Table(table_name)

    @staticmethod
    def _to_ddb(item: dict) -> dict:
        return {k: Decimal(str(v)) if isinstance(v, float) else v for k, v in item.items()}

    @staticmethod
    def _from_ddb(item: dict) -> dict:
        out = {}
        for k, v in item.items():
            if isinstance(v, Decimal):
                out[k] = int(v) if v == v.to_integral_value() and k == "word_count" else float(v)
            else:
                out[k] = v
        return out

    def put(self, submission: dict) -> None:
        self.table.put_item(Item=self._to_ddb(submission))

    def get(self, submission_id: str) -> dict | None:
        item = self.table.get_item(Key={"id": submission_id}).get("Item")
        return self._from_ddb(item) if item else None

    def delete(self, submission_id: str) -> bool:
        resp = self.table.delete_item(Key={"id": submission_id}, ReturnValues="ALL_OLD")
        return "Attributes" in resp

    def list(self) -> list[dict]:
        items, kwargs = [], {}
        while True:
            page = self.table.scan(**kwargs)
            items.extend(self._from_ddb(i) for i in page.get("Items", []))
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return sorted(items, key=lambda s: s["created_at"], reverse=True)

    def clear(self) -> None:
        for item in self.list():
            self.delete(item["id"])

    def count(self) -> int:
        return len(self.list())


def build_store():
    backend = os.environ.get("STORAGE_BACKEND", "memory").lower()
    if backend == "dynamodb":
        return DynamoStore(os.environ["SUBMISSIONS_TABLE"])
    return MemoryStore()
