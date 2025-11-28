import json
from logging import getLogger
from typing import Any

import boto3

from app.config import settings
from app.integrations.celery.tasks.process_upload_task import process_uploaded_file
from celery import shared_task

QUEUE_URL: str = settings.sqs_queue_url

sqs = boto3.client("sqs", region_name=settings.aws_region)

logger = getLogger(__name__)


@shared_task()
def poll_sqs_messages() -> dict[str, Any]:
    try:
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5,
            MessageAttributeNames=["All"],
        )

        messages = response.get("Messages", [])
        processed_count = 0
        failed_count = 0

        logger.info(f"[poll_sqs_messages] Received {len(messages)} messages from SQS")

        for message in messages:
            receipt_handle = message["ReceiptHandle"]
            message_id = message["MessageId"]

            try:
                message_body = message["Body"]
                logger.info(f"[poll_sqs_messages] Processing message {message_id}")

                # Parse JSON string if necessary
                if isinstance(message_body, str):
                    try:
                        message_body = json.loads(message_body)
                    except json.JSONDecodeError:
                        logger.info(
                            f"[poll_sqs_messages] Message {message_id} is not valid JSON, skipping: {message_body[:100]}",
                        )
                        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
                        failed_count += 1
                        continue

                # Check if this is an S3 event
                if "Records" not in message_body:
                    sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
                    failed_count += 1
                    continue

                # Process S3 records
                for record in message_body["Records"]:
                    if record.get("eventSource") == "aws:s3":
                        bucket_name = record["s3"]["bucket"]["name"]
                        object_key = record["s3"]["object"]["key"]

                        # Enqueue Celery task
                        process_uploaded_file.delay(bucket_name, object_key)
                        processed_count += 1

                # Delete message from queue after processing
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)

            except Exception as e:
                logger.info(f"[poll_sqs_messages] Error processing message {message_id}: {str(e)}")
                failed_count += 1
                continue

        result = {
            "messages_processed": processed_count,
            "messages_failed": failed_count,
            "total_messages": len(messages),
        }
        return result

    except Exception as e:
        return {"status": "error", "error": str(e)}


@shared_task()
def poll_sqs_task(expiration_seconds: int, iterations_done: int = 0):
    num_polls = expiration_seconds // 20

    if iterations_done >= num_polls:
        return {"polls_completed": num_polls}

    poll_sqs_messages()

    # Schedule next iteration
    poll_sqs_task.apply_async(
        args=[expiration_seconds, iterations_done + 1],
        countdown=20,
    )