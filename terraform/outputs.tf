# Output values after deployment

output "api_url" {
  description = "Base URL of the API"
  value       = aws_lambda_function_url.api_url.function_url
}

output "api_ingest_url" {
  description = "Full URL for /ingest endpoint"
  value       = "${aws_lambda_function_url.api_url.function_url}ingest"
}

output "api_health_url" {
  description = "Full URL for /health endpoint"
  value       = "${aws_lambda_function_url.api_url.function_url}health"
}

output "sqs_queue_url" {
  description = "SQS Queue URL"
  value       = aws_sqs_queue.main_queue.url
}

output "sqs_dlq_url" {
  description = "Dead Letter Queue URL"
  value       = aws_sqs_queue.dead_letter_queue.url
}

output "dynamodb_table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.processed_logs.name
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}
