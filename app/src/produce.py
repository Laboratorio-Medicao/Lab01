import argparse
import logging

from src.config import get_github_token
from src.queue.connection import get_channel
from src.queue.publisher import JobPublisher
from src.queue.types import Job, JobType
from src.storage import get_collection_state, get_connection, init_db

logger = logging.getLogger(__name__)

DEFAULT_TARGET_TOTAL = 1000
DEFAULT_PER_PAGE = 25


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Publica job inicial de coleta de repositórios na fila RabbitMQ."
    )
    parser.add_argument(
        "--total",
        type=int,
        default=DEFAULT_TARGET_TOTAL,
        help=f"quantidade total de repositórios a coletar (padrão: {DEFAULT_TARGET_TOTAL})",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=DEFAULT_PER_PAGE,
        help=f"repositórios por página (padrão: {DEFAULT_PER_PAGE})",
    )
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_arg_parser().parse_args()

    db_connection = get_connection()
    init_db(db_connection)
    state = get_collection_state(db_connection)
    db_connection.close()

    if state["total_collected"] >= args.total:
        logger.info(
            "meta já atingida (%s/%s); nenhum job publicado.",
            state["total_collected"],
            args.total,
        )
        return

    logger.info(
        "estado atual: total_collected=%s, cursor=%s",
        state["total_collected"],
        state["cursor"],
    )

    pika_connection, channel = get_channel()
    publisher = JobPublisher(channel)

    job = Job(
        type=JobType.GRAPHQL_PAGINATION,
        payload={"target_total": args.total, "per_page": args.per_page},
    )
    publisher.publish(job)
    pika_connection.close()

    logger.info(
        "job publicado: type=%s target_total=%s per_page=%s",
        job.type.value,
        args.total,
        args.per_page,
    )


if __name__ == "__main__":
    main()
