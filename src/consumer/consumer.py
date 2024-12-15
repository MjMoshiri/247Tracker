import pika
import json
import threading
import queue
import time
import logging
import boto3
from openai import OpenAI
from pydantic import BaseModel
import os
import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Environment variables
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER")
RABBITMQ_PASS = os.getenv("RABBITMQ_PASS")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME")
AWS_REGION = os.getenv("AWS_REGION")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Constants
QUEUE_MAX_SIZE = 1000
HEARTBEAT_INTERVAL = 600
BLOCKED_CONNECTION_TIMEOUT = 300
PREFETCH_COUNT = 1
RETRY_DELAY = 2

# Clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
sns_client = boto3.client("sns", region_name=AWS_REGION)
dynamodb_client = boto3.client("dynamodb", region_name=AWS_REGION)

# Queues with max size 1000
openai_queue = queue.Queue(maxsize=QUEUE_MAX_SIZE)
sns_queue = queue.Queue(maxsize=QUEUE_MAX_SIZE)
dynamodb_queue = queue.Queue(maxsize=QUEUE_MAX_SIZE)

# User data and models
user_data = f"""
You will be given a job description. Review the job description and return a JSON object with two keys:
1. 'reasoning': A string providing a detailed explanation of why the job is or is not qualified based on the given conditions.
2. 'is_qualified': A boolean indicating if the job is qualified.

The qualification criteria are as follows:
- A PhD is not required.
- The role is not a management position or senior position. Which means no Senior, Director, Manager, Staff, etc. in the title.
- If a minimum experience is required, it must be less than 5 years.
- If there is a date in the job posting, it should not be more than a week ago from today. Today is : {datetime.datetime.now().strftime('%B %d, %Y')}.

Please assess the job description carefully and ensure the reasoning covers all aspects of the criteria provided. Keep in mind that the job description may not contain all the information needed to make a decision. Therefore, You are safe to ignore any criteria that are not present in the job description.

"""


class JobEvaluation(BaseModel):
    reasoning: str
    is_qualified: bool


def openai_worker():
    while True:
        job = openai_queue.get()
        if job is None:
            break
        job_title = job["title"]
        job_description = job["description"]
        prompt = (
            f"{user_data}\n ## JOB INFO ## Job Title: {job_title}\n"
            f'Job Description: "{job_description} "\n ## END OF JOB INFO ##'
        )
        try:
            response = openai_client.beta.chat.completions.parse(
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
            job["evaluation"] = evaluation.dict()
            if evaluation.is_qualified:
                sns_queue.put(job)
                dynamodb_queue.put(job)
                logger.info(f'Job ID: {job["id"]} added to SNS and DynamoDB queues.')
            else:
                logger.info(
                    f'Job ID: {job["id"]} is not qualified. Reason: {evaluation.reasoning}'
                )
        except Exception as e:
            logger.error(f'Failed to evaluate job ID {job["id"]}: {e}')
            time.sleep(RETRY_DELAY)
            openai_queue.put(job)
        finally:
            openai_queue.task_done()


def sns_worker():
    while True:
        job = sns_queue.get()
        if job is None:
            break
        try:
            sns_client.publish(TopicArn=SNS_TOPIC_ARN, Message=json.dumps(job, default=str))
            logger.info(f'Job ID: {job["id"]} sent to SNS.')
        except Exception as e:
            logger.error(f'Failed to send job ID {job["id"]} to SNS: {e}')
            time.sleep(RETRY_DELAY)
            sns_queue.put(job)
        finally:
            sns_queue.task_done()


def dynamodb_worker():
    while True:
        job = dynamodb_queue.get()
        if job is None:
            break
        evaluation = job.get("evaluation", {})
        try:
            dynamodb_client.put_item(
                TableName=DYNAMODB_TABLE_NAME,
                Item={
                    "JobID": {"S": job["id"]},
                    "JobTitle": {"S": job["title"]},
                    "JobDescription": {"S": job["description"]},
                    "Link": {"S": job["link"]},
                    "Company": {"S": job["company"]},
                    "Reasoning": {"S": evaluation.get("reasoning", "")},
                    "IsQualified": {"BOOL": evaluation.get("is_qualified", False)},
                    "DateAdded": {"N": str(int(datetime.datetime.now().timestamp()))},
                    "Processed": {"S": "No"},
                },
            )
            logger.info(f'Job ID: {job["id"]} stored in DynamoDB.')
        except Exception as e:
            logger.error(f'Failed to store job ID {job["id"]} in DynamoDB: {e}')
            time.sleep(RETRY_DELAY)
            dynamodb_queue.put(job)
        finally:
            dynamodb_queue.task_done()


def callback(ch, method, _, body):
    job = json.loads(body)
    if openai_queue.full():
        openai_queue.get_nowait()
        logger.warning(
            "OpenAI queue is full. Dropping the oldest job to add the new job."
        )
    openai_queue.put_nowait(job)
    logger.info(f'Job ID: {job["id"]} added to OpenAI queue.')
    ch.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Main function to start the consumer."""
    logger.info("Consumer is starting...")
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=HEARTBEAT_INTERVAL,
        blocked_connection_timeout=BLOCKED_CONNECTION_TIMEOUT,
    )

    connection = None
    while connection is None:
        try:
            connection = pika.BlockingConnection(parameters)
        except pika.exceptions.AMQPConnectionError as e:
            logger.error(
                f"Failed to connect to RabbitMQ: {e}. Retrying in {RETRY_DELAY} seconds..."
            )
            time.sleep(RETRY_DELAY)

    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    channel.basic_qos(prefetch_count=PREFETCH_COUNT)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)

    openai_thread = threading.Thread(target=openai_worker)
    sns_thread = threading.Thread(target=sns_worker)
    dynamodb_thread = threading.Thread(target=dynamodb_worker)

    for t in [openai_thread, sns_thread, dynamodb_thread]:
        t.daemon = True
        t.start()

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        pass
    finally:
        openai_queue.put(None)
        sns_queue.put(None)
        dynamodb_queue.put(None)
        for q in [openai_queue, sns_queue, dynamodb_queue]:
            q.join()
        connection.close()


if __name__ == "__main__":
    main()
