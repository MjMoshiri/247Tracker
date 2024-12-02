import pika
import json
from ratelimit import limits, sleep_and_retry
import os
import time
import logging
import boto3
from openai import OpenAI
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")

RATE_LIMIT = int(os.getenv("CONSUMER_RATE_LIMIT_PER_MINUTE", 100))
TIME_PERIOD = 60
RETRY_ATTEMPTS = 5
RETRY_DELAY = 5

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

sns_client = boto3.client("sns", region_name= os.getenv("AWS_REGION"))


class JobEvaluation(BaseModel):
    reasoning: str
    is_qualified: bool


user_data = """
You will be given a job description. Review the job description and return a JSON object with two keys:
1. 'reasoning': A string providing a detailed explanation of why the job is or is not qualified based on the given conditions.
2. 'is_qualified': A boolean indicating if the job is qualified.

The qualification criteria are as follows:
- A PhD is not required.
- The role is not a management position or senior position. Which means no Senior, Director, Manager, Staff, etc. in the title.
- If a minimum experience is required, it must be less than 5 years.
- The job must be located in California or allow for remote work.

Please assess the job description carefully and ensure the reasoning covers all aspects of the criteria provided.
"""


@sleep_and_retry
@limits(calls=RATE_LIMIT, period=TIME_PERIOD)
def process_job(job):
    job_title = job["title"]
    job_description = job["description"]

    prompt = f'{user_data}\n ## JOB INFO ## Job Title: {job_title}\nJob Description: "{job_description} "\n ## END OF JOB INFO ##'

    try:
        response = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            response_format=JobEvaluation,
        )
        evaluation = response.choices[0].message.parsed
    except Exception as e:
        logger.error(f"Failed to evaluate job ID {job['id']}: {e}")
        return

    if evaluation.is_qualified:
        try:
            sns_client.publish(TopicArn=SNS_TOPIC_ARN, Message=json.dumps(job))
            logger.info(f"Job ID: {job['id']} qualified and sent to SNS.")
        except Exception as e:
            logger.error(f"Failed to publish job ID {job['id']} to SNS: {e}")
    else:
        logger.info(
            f"Job ID: {job['id']} is not qualified. Reason: {evaluation.reasoning}"
        )


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
