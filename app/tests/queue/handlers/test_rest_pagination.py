from src.queue.handlers.rest_pagination import RestPaginationHandler
from src.queue.types import Job, JobType


def test_rest_pagination_handler_handles_without_error():
    handler = RestPaginationHandler()
    job = Job(type=JobType.REST_PAGINATION, payload={})
    handler.handle(job)  # deve apenas logar e retornar, sem erro
