import logging

from src.client import GitHubGraphQLClient
from src.config import get_github_token
from src.queue.connection import QUEUE_NAME, get_channel
from src.queue.consumer import JobConsumer
from src.queue.dispatcher import JobDispatcher
from src.queue.handlers.graphql_pagination import GraphQLPaginationHandler
from src.queue.handlers.rest_pagination import RestPaginationHandler
from src.queue.publisher import JobPublisher
from src.queue.types import JobType


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    token = get_github_token()
    client = GitHubGraphQLClient(token)

    pika_connection, channel = get_channel()
    publisher = JobPublisher(channel)

    handlers = {
        JobType.GRAPHQL_PAGINATION: GraphQLPaginationHandler(client, publisher),
        JobType.REST_PAGINATION: RestPaginationHandler(),
    }
    dispatcher = JobDispatcher(handlers)
    consumer = JobConsumer(channel, dispatcher, publisher)

    try:
        consumer.start(QUEUE_NAME)
    except KeyboardInterrupt:
        pass
    finally:
        pika_connection.close()


if __name__ == "__main__":
    main()
