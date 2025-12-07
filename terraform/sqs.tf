# Dead Letter Queue for failed messages after retries

resource "aws_sqs_queue" "dead_letter_queue" {
  name                      = "${var.project_name}-dlq"
  message_retention_seconds = var.sqs_message_retention

  # Server-side encryption
  sqs_managed_sse_enabled = true

  tags = {
    Name        = "${var.project_name}-dlq"
    Description = "Dead Letter Queue for failed messages"
  }
}

# Main SQS Queue

resource "aws_sqs_queue" "main_queue" {
  name                       = "${var.project_name}-queue"
  visibility_timeout_seconds = var.sqs_visibility_timeout
  message_retention_seconds  = var.sqs_message_retention
  delay_seconds              = 0
  receive_wait_time_seconds  = 20 # Long polling

  # Server-side encryption
  sqs_managed_sse_enabled = true

  # Redrive Policy - Send to DLQ after max retries
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter_queue.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })

  tags = {
    Name        = "${var.project_name}-queue"
    Description = "Main processing queue"
  }
}

# Allow main queue to send to DLQ
resource "aws_sqs_queue_redrive_allow_policy" "dlq_redrive_allow" {
  queue_url = aws_sqs_queue.dead_letter_queue.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.main_queue.arn]
  })
}