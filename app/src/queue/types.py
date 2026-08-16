from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum


class JobType(str, Enum):
    GRAPHQL_PAGINATION = "graphql_pagination"
    REST_PAGINATION = "rest_pagination"


@dataclass
class Job:
    type: JobType
    payload: dict
    attempt: int = 0

    def to_bytes(self) -> bytes:
        return json.dumps(
            {"type": self.type.value, "payload": self.payload, "attempt": self.attempt}
        ).encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> Job:
        raw = json.loads(data.decode("utf-8"))
        return cls(
            type=JobType(raw["type"]),
            payload=raw["payload"],
            attempt=raw["attempt"],
        )
