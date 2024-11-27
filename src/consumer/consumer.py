import pika
import json
from ratelimit import limits, sleep_and_retry
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE")

RATE_LIMIT = int(os.getenv("CONSUMER_RATE_LIMIT_PER_MINUTE", 100))
TIME_PERIOD = 60
RETRY_ATTEMPTS = 5
RETRY_DELAY = 5  


@sleep_and_retry
@limits(calls=RATE_LIMIT, period=TIME_PERIOD)
def process_job(job):
    logger.info(f"Job ID: {job['id']}")
    logger.info(f"Company: {job['company']}")
    logger.info(f"Description: {job['description']}")
    logger.info(f"Link: {job['link']}")
    logger.info(f"Title: {job['title']}")
    logger.info(f"Date: {job['date']}")
    logger.info("-" * 40)


def callback(ch, method, _, body):
    job = json.loads(body)
    process_job(job)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    logger.info("Consumer is starting...")

    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    connection = None

    for attempt in range(RETRY_ATTEMPTS):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials
                )
            )
            break
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                logger.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error("Max retry attempts reached. Exiting.")
                return

    if connection is None:
        return

    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    logger.info("Waiting for messages. To exit press CTRL+C")
    try:
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError as e:
        logger.error(f"Connection lost: {e}")
        connection.close()
        main()


if __name__ == "__main__":
    main()