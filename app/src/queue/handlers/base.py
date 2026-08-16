from typing import Protocol

from src.queue.types import Job


class JobHandler(Protocol):
    def handle(self, job: Job) -> None:
        ...
