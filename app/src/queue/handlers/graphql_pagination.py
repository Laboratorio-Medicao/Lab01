import logging

from src.collector import collect_page
from src.queue.types import Job, JobType
from src.storage import get_collection_state, get_connection

logger = logging.getLogger(__name__)


class GraphQLPaginationHandler:
    def __init__(self, client, publisher):
        self._client = client
        self._publisher = publisher

    def handle(self, job: Job) -> None:
        target_total = job.payload["target_total"]
        per_page = job.payload["per_page"]

        connection = get_connection()
        try:
            state = get_collection_state(connection)
            if state["total_collected"] >= target_total:
                logger.info(
                    "meta já atingida (%s/%s); descartando job",
                    state["total_collected"],
                    target_total,
                )
                return

            page_size = min(per_page, target_total - state["total_collected"])
            collect_page(self._client, connection, page_size)

            new_state = get_collection_state(connection)
            if new_state["total_collected"] < target_total:
                next_job = Job(type=JobType.GRAPHQL_PAGINATION, payload=job.payload)
                self._publisher.publish(next_job)
                logger.info(
                    "próximo job enfileirado (total_collected=%s/%s)",
                    new_state["total_collected"],
                    target_total,
                )
            else:
                logger.info(
                    "coleta concluída: %s/%s repositórios",
                    new_state["total_collected"],
                    target_total,
                )
        finally:
            connection.close()
