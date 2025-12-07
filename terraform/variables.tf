variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "robust-data-processor"
}

# SQS Config

variable "sqs_visibility_timeout" {
  description = "SQS visibility timeout in seconds (must be > Lambda timeout)"
  type        = number
  default     = 900 # 15 minutes
}

variable "sqs_message_retention" {
  description = "How long messages stay in queue (seconds)"
  type        = number
  default     = 1209600 # 14 days
}

variable "sqs_max_receive_count" {
  description = "Max retries before sending to DLQ"
  type        = number
  default     = 3
}

# Lambda Config

variable "api_lambda_timeout" {
  description = "API Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "api_lambda_memory" {
  description = "API Lambda memory in MB"
  type        = number
  default     = 256
}

variable "worker_lambda_timeout" {
  description = "Worker Lambda timeout in seconds"
  type        = number
  default     = 600 # 10 minutes for heavy processing
}

variable "worker_lambda_memory" {
  description = "Worker Lambda memory in MB"
  type        = number
  default     = 512
}

variable "worker_batch_size" {
  description = "Number of SQS messages per Lambda invocation"
  type        = number
  default     = 1 # Process one at a time for reliability
}

# DynamoDB Config

variable "dynamodb_billing_mode" {
  description = "DynamoDB billing mode (PAY_PER_REQUEST or PROVISIONED)"
  type        = string
  default     = "PAY_PER_REQUEST" # Serverless, scales to zero
}