import json
import os
import re
import time
import logging
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError, BotoCoreError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(DYNAMODB_TABLE) if DYNAMODB_TABLE else None

def get_current_timestamp():
    return datetime.now(timezone.utc).isoformat()

def redact_sensitive_data(text):
    if not text:
        return text
    
    redacted = text

    # Phone numbers
    phone_patterns = [
        r'\+\d{1,2}[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',  # +1-555-555-0199
        r'\(\d{3}\)\s*\d{3}[-.\s]?\d{4}',                   # (555) 555-0199
        r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',               # 555-555-0199 or 1234567890
        r'\b\d{3}[-.\s]?\d{4}\b',                           # 555-0199 (7 digits)
    ]
    for pattern in phone_patterns:
        redacted = re.sub(pattern, '[REDACTED]', redacted)

    # SSN (XXX-XX-XXXX)
    ssn_pattern = r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
    redacted = re.sub(ssn_pattern, '[REDACTED]', redacted)

    # Email addresses
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    redacted = re.sub(email_pattern, '[REDACTED]', redacted)
    
    # Credit card (16 digits)
    cc_pattern = r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'
    redacted = re.sub(cc_pattern, '[REDACTED]', redacted)
    
    return redacted

def simulate_heavy_processing(text):
    if not text:
        return
    
    text_length = len(text)
    processing_time = text_length * 0.05

    logger.info(f"Simulating processing: {text_length} chars = {processing_time:.2f}s")
    
    time.sleep(processing_time)

def save_to_dynamodb(tenant_id, log_id, original_text, modified_data, source):
    if not table:
        return False, "DynamoDB table not configured"
    
    item = {
        "tenant_id": tenant_id,
        "log_id": log_id,
        "source": source,
        "original_text": original_text,
        "modified_data": modified_data,
        "processed_at": get_current_timestamp()
    }

    try:
        table.put_item(Item=item)
        logger.info(f"Saved to DynamoDB: tenant={tenant_id}, log={log_id}")
        return True, None
    
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error(f"DynamoDB ClientError: {error_code} - {error_msg}")
        return False, f"DynamoDB error: {error_code}"
        
    except BotoCoreError as e:
        logger.error(f"DynamoDB BotoCoreError: {str(e)}")
        return False, f"AWS SDK error: {str(e)}"
        
    except Exception as e:
        logger.exception("Unexpected DynamoDB error")
        return False, f"Unexpected error: {str(e)}"
    
def process_message(message_body):
    try:
        # Parse message
        if isinstance(message_body, str):
            payload = json.loads(message_body)
        else:
            payload = message_body
        
        tenant_id = payload.get("tenant_id")
        log_id = payload.get("log_id")
        text = payload.get("text", "")
        source = payload.get("source", "unknown")
        
        # Validate required fields
        if not tenant_id:
            return False, "Missing tenant_id"
        if not log_id:
            return False, "Missing log_id"
        
        logger.info(f"Processing: tenant={tenant_id}, log={log_id}, length={len(text)}")
        
        # Simulate heavy processing
        simulate_heavy_processing(text)
        
        # Redact sensitive data
        modified_data = redact_sensitive_data(text)
        
        # Save to DynamoDB
        success, db_error = save_to_dynamodb(
            tenant_id=tenant_id,
            log_id=log_id,
            original_text=text,
            modified_data=modified_data,
            source=source
        )
        
        if not success:
            return False, db_error
        
        logger.info(f"Success: tenant={tenant_id}, log={log_id}")
        return True, None
    
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    
    except Exception as e:
        logger.exception(f"Unexpected processing error: {str(e)}")
        return False, f"Processing error: {str(e)}"

def handler(event, context):
    records = event.get("Records", [])
    logger.info(f"Received {len(records)} messages")

    batch_item_failures = []

    for record in records:
        message_id = record.get("messageId")
        body = record.get("body")

        logger.info(f"Processing message: {message_id}")

        success, error = process_message(body)

        if not success:
            logger.error(f"Failed message {message_id}: {error}")
            batch_item_failures.append({"itemIdentifier": message_id})
    
    # Return partial batch response
    result = {"batchItemFailures": batch_item_failures}

    success_count = len(records) - len(batch_item_failures)

    logger.info(f"Batch complete: {success_count} success, {len(batch_item_failures)} failures")

    return result