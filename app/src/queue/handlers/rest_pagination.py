import logging

from src.queue.types import Job

logger = logging.getLogger(__name__)


class RestPaginationHandler:
    def handle(self, job: Job) -> None:
        logger.warning(
            "RestPaginationHandler não implementado; job ignorado (payload=%s)", job.payload
        )
