import json
import os
import uuid
import time
import re
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configuring environment variables
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
AWS_REGION = os.getenv("AWS_REGION")

# Initialize SQS client with retry config
sqs_client = None
if SQS_QUEUE_URL:
    sqs_client = boto3.client(
        "sqs",
        region_name=AWS_REGION,
        config=boto3.session.Config(
            retries = {
                "max_attempts": 3,
                "mode": "adaptive",
            }
        )
    )

# Helper functions

def generate_log_id():
    return str(uuid.uuid4())

def get_current_timestamp():
    return datetime.now(timezone.utc).isoformat()

def validate_tenant_id(tenant_id):
    """
    Valid tenant ID rules: 
    - must be non-empty
    - only alphanumeric, hyphens, and underscores
    - max 64 characters in length
    """

    if not tenant_id:
        return False, "tenant_id is required"

    if not isinstance(tenant_id, str):
        return False, "tenant_id must be a string"

    tenant_id = tenant_id.strip()
    if len(tenant_id) == 0:
        return False, "tenant_id cannot be empty"
    
    if len(tenant_id) > 64:
        return False, "tenant_id must be less than 64 characters"

    if not re.match(r"^[a-zA-Z0-9-_]+$", tenant_id):
        return False, "tenant_id must only contain alphanumeric characters, hyphens, or underscores"

    return True, None

# Normalize any input into unified internal format
def normalize_payload(tenant_id, log_id, text, source):
    return {
        "tenant_id": tenant_id.strip(),
        "log_id": log_id,
        "text" : text if text else "",
        "source": source,
        "received_at": get_current_timestamp(),
        "text_length": len(text) if text else 0
    }

# Send message to SQS queue with retries
def send_to_sqs(payload, max_retries=3):
    # Check if SQS is configured
    if not SQS_QUEUE_URL:
        logger.warning("SQS_QUEUE_URL not configured - running in local mode")
        # In local mode, just log and return success
        logger.info(f"[LOCAL MODE] Would send to SQS: {json.dumps(payload)}")
        return True, f"local-{generate_log_id()}", None
    
    if not sqs_client:
        return False, None, "SQS client not initialized"
    
    for attempt in range(max_retries):
        try:
            # Send message to SQS
            response = sqs_client.send_message(
                QueueUrl=SQS_QUEUE_URL,
                MessageBody=json.dumps(payload),
                MessageAttributes={
                    "tenant_id": {
                        "DataType": "String",
                        "StringValue": payload["tenant_id"]
                    },
                    "source": {
                        "DataType": "String",
                        "StringValue": payload["source"]
                    }
                }
            )
            
            message_id = response.get("MessageId")
            logger.info(f"Message sent to SQS: {message_id}")
            return True, message_id, None
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            
            logger.error(f"SQS ClientError (attempt {attempt + 1}): {error_code} - {error_msg}")
            
            # Don't retry on validation errors
            if error_code in ["InvalidParameterValue", "ValidationError", "AccessDenied"]:
                return False, None, f"SQS validation error: {error_msg}"
            
            # Retry on transient errors with exponential backoff
            if attempt < max_retries - 1:
                sleep_time = 0.1 * (2 ** attempt)  # 0.1s, 0.2s, 0.4s
                time.sleep(sleep_time)
                continue
            
            return False, None, f"SQS error after {max_retries} attempts: {error_msg}"
            
        except BotoCoreError as e:
            logger.error(f"SQS BotoCoreError (attempt {attempt + 1}): {str(e)}")
            
            if attempt < max_retries - 1:
                time.sleep(0.1 * (2 ** attempt))
                continue
            
            return False, None, f"AWS SDK error: {str(e)}"
        
        except Exception as e:
            logger.exception("Unexpected error sending to SQS")
            return False, None, f"Unexpected error: {str(e)}"
    
    return False, None, "Max retries exceeded"

# Handle JSON payload ingestion
def handle_json_payload(data):
    tenant_id = data.get("tenant_id")
    valid, error = validate_tenant_id(tenant_id)
    if not valid:
        return None, {"error": "Invalid tenant_id", "details": error}, 400
    
    # validate text field
    text = data.get("text")
    if text is None:
        return None, {"error": "Missing text", "details": "text field is required"}, 400
    
    if not isinstance(text, str):
        return None, {"error": "Invalid text", "details": "text must be a string"}, 400
    
    # Use provided log_id or generate a new one
    log_id = data.get("log_id")
    if log_id:
        if not isinstance(log_id, str):
            return None, {"error": "Invalid log_id", "details": "log_id must be a string"}, 400
        log_id = log_id.strip()
    
    if not log_id:
        log_id = generate_log_id()
    
    normalized = normalize_payload(
        tenant_id = tenant_id,
        log_id = log_id,
        text = text,
        source = "json_upload"
    )

    return normalized, None, None

# Handle text payload ingestion
def handle_text_payload(raw_text, headers):
    # Extract tenant from header (case-insensitive)
    tenant_id = headers.get("X-Tenant-ID") or headers.get("x-tenant-id")
    
    valid, error = validate_tenant_id(tenant_id)
    if not valid:
        return None, {
            "error": "Missing or invalid X-Tenant-ID header",
            "details": error or "X-Tenant-ID header is required for text/plain content"
        }, 400
    
    # Extract optional log_id from header
    log_id = headers.get("X-Log-ID") or headers.get("x-log-id")
    if not log_id:
        log_id = generate_log_id()
    
    # Normalize the payload
    normalized = normalize_payload(
        tenant_id=tenant_id,
        log_id=log_id,
        text=raw_text or "",
        source="text_upload"
    )

    return normalized, None, None

# API Endpoints

# Health check endpoint for monitoring and load balancers
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": get_current_timestamp(),
        "service": "robust-data-processor-api",
        "config": {
            "sqs_configured": bool(SQS_QUEUE_URL),
            "region": AWS_REGION
        }
    }), 200

# Ingest API
@app.route("/ingest", methods=["POST"])
def ingest():
    content_type = request.content_type or ""
    try:
        # Routing based on content type
        if "application/json" in content_type:
            try:
                data = request.get_json(force=False)
                if data is None:
                    return jsonify({
                        "error": "Invalid JSON",
                        "details": "Request body myst be valid JSON"
                    }), 400
            except Exception as e:
                logger.error(f"JSON parse error: {str(e)}")
                return jsonify({
                    "error": "JSON parse error",
                    "details": str(e)
                }), 400
            
            normalized, error_response, status_code = handle_json_payload(data)
        
        elif "text/plain" in content_type:
            # Get raw text body
            raw_text = request.get_data(as_text=True)
            normalized, error_response, status_code = handle_text_payload(raw_text, request.headers)
        
        else:
            # Unsupported content type
            return jsonify({
                "error": "Unsupported Content-Type",
                "details": f"Expected 'application/json' or 'text/plain', got '{content_type}'",
                "supported_types": ["application/json", "text/plain"]
            }), 415
        
        # Return validation errors if any
        if error_response:
            return jsonify(error_response), status_code
        
        # Send to SQS
        success, message_id, sqs_error = send_to_sqs(normalized)

        if not success:
            logger.error(f"SQS send failed for log_id={normalized["log_id"]}: {sqs_error}")
            return jsonify({
                "error": "Queue unavailable",
                "message": "Please retry your request",
                "retry_after": 5,
                "details": sqs_error
            }), 500
        
        logger.info(f"Accepted: tenant={normalized['tenant_id']}, log={normalized['log_id']}")

        return jsonify({
            "status": "accepted",
            "log_id": normalized["log_id"],
            "tenant_id": normalized["tenant_id"],
            "message": "Processing queued successfully",
            "message_id": message_id
        }), 202

    except Exception as e:
        # Catch-all for unexpected errors
        logger.exception(f"Unexpected error in /ingest endpoint: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please retry.",
            "details": str(e),
            "retry_after": 5
        }), 500

# Error handlers

@app.errorhandler(404)
def not_found(e):
    """Handle 404 Not Found errors."""
    return jsonify({
        "error": "Not Found",
        "message": "The requested endpoint does not exist",
        "available_endpoints": ["GET /health", "POST /ingest"]
    }), 404


@app.errorhandler(405)
def method_not_allowed(e):
    """Handle 405 Method Not Allowed errors."""
    return jsonify({
        "error": "Method Not Allowed",
        "message": f"The {request.method} method is not allowed for this endpoint"
    }), 405


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 Internal Server errors."""
    logger.exception("Internal server error")
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred",
        "retry_after": 5
    }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)