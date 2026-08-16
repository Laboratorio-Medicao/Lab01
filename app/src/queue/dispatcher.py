import logging

from src.queue.types import Job, JobType

logger = logging.getLogger(__name__)


class JobDispatcher:
    def __init__(self, handlers: dict[JobType, object]):
        self._handlers = handlers

    def dispatch(self, job: Job) -> None:
        handler = self._handlers.get(job.type)
        if handler is None:
            raise ValueError(
                f"nenhum handler registrado para job type: {job.type.value!r}"
            )
        logger.debug("despachando job type=%s para %s", job.type, type(handler).__name__)
        handler.handle(job)
