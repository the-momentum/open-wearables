import os
import json
import time
from pathlib import Path

from dotenv import load_dotenv
import boto3
from celery import shared_task

from app.integrations.celery.tasks.process_upload_task import process_uploaded_file
from app.database import DbSession


load_dotenv(Path(__file__).resolve().parents[4] / "config" / ".env")

QUEUE_URL: str = "https://sqs.eu-north-1.amazonaws.com/539516441427/owear-queue"
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")

sqs = boto3.client("sqs", region_name=AWS_REGION)

@shared_task()
def poll_sqs_messages(user_id: str):
    try:
        response = sqs.receive_message(
            QueueUrl=QUEUE_URL,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=5,
            MessageAttributeNames=['All']
        )

        messages = response.get('Messages', [])
        processed_count = 0
        failed_count = 0
        
        print(f"[poll_sqs_messages] Received {len(messages)} messages from SQS")

        for message in messages:
            receipt_handle = message['ReceiptHandle']
            message_id = message['MessageId']
            
            try:
                message_body = message['Body']
                print(f"[poll_sqs_messages] Processing message {message_id}")
                
                # Parse JSON string if necessary
                if isinstance(message_body, str):
                    try:
                        message_body = json.loads(message_body)
                    except json.JSONDecodeError:
                        print(f"[poll_sqs_messages] Message {message_id} is not valid JSON, skipping: {message_body[:100]}")
                        # Delete non-JSON messages and continue
                        sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
                        failed_count += 1
                        continue

                # Check if this is an S3 event
                if 'Records' not in message_body:
                    print(f"[poll_sqs_messages] Message {message_id} has no 'Records' key, skipping")
                    sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)
                    failed_count += 1
                    continue

                # Process S3 records
                for record in message_body['Records']:
                    if record.get('eventSource') == 'aws:s3':
                        bucket_name = record['s3']['bucket']['name']
                        object_key = record['s3']['object']['key']
                        print(f"[poll_sqs_messages] Queuing file upload task: s3://{bucket_name}/{object_key}")

                        # Enqueue Celery task
                        task = process_uploaded_file.delay(bucket_name, object_key, user_id)
                        print(f"[poll_sqs_messages] Queued task {task.id}")
                        processed_count += 1

                # Delete message from queue after processing
                sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=receipt_handle)

            except Exception as e:
                print(f"[poll_sqs_messages] Error processing message {message_id}: {str(e)}")
                failed_count += 1
                # Don't delete the message on error - let it be retried
                continue

        result = {
            "messages_processed": processed_count,
            "messages_failed": failed_count,
            "total_messages": len(messages),
        }
        print(f"[poll_sqs_messages] Result: {result}")
        return result

    except Exception as e:
        print(f"[poll_sqs_messages] Fatal error: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }




@shared_task()
def poll_sqs_task(expiration_seconds: int, user_id: str):
    """
    Poll SQS messages for file uploads at regular intervals.
    Polls every 20 seconds for expiration_seconds // 20 iterations.
    
    Args:
        expiration_seconds: Total time to poll for (in seconds)
    """
    
    num_polls = expiration_seconds // 20
    print(f"[poll_sqs_task] Starting with {num_polls} polls (every 20 seconds)")
    
    for i in range(num_polls):
        print(f"[poll_sqs_task] Poll {i+1}/{num_polls}")
        poll_sqs_messages(user_id=user_id)
        
        if i < num_polls - 1:
            time.sleep(20)
    
    print(f"[poll_sqs_task] Completed {num_polls} polls")
    return {"polls_completed": num_polls}
