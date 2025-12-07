# Install dependencies and package Lambda

resource "null_resource" "worker_lambda_dependencies" {
  provisioner "local-exec" {
    command = "cd ${path.module}/../src/worker && pip install -r requirements.txt -t . --upgrade --quiet"
  }

  triggers = {
    requirements = filemd5("${path.module}/../src/worker/requirements.txt")
  }
}

data "archive_file" "worker_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/worker"
  output_path = "${path.module}/../dist/worker_lambda.zip"

  depends_on = [null_resource.worker_lambda_dependencies]
}

# Worker Lambda Function

resource "aws_lambda_function" "worker" {
  filename         = data.archive_file.worker_lambda_zip.output_path
  function_name    = "${var.project_name}-worker"
  role             = aws_iam_role.worker_lambda_role.arn
  handler          = "handler.handler"
  runtime          = "python3.11"
  source_code_hash = data.archive_file.worker_lambda_zip.output_base64sha256
  timeout          = var.worker_lambda_timeout
  memory_size      = var.worker_lambda_memory

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.processed_logs.name
    }
  }

  tags = {
    Name = "${var.project_name}-worker"
  }
}

# SQS Event Source Mapping (Trigger)

resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.main_queue.arn
  function_name    = aws_lambda_function.worker.arn
  enabled          = true

  batch_size                         = var.worker_batch_size
  maximum_batching_window_in_seconds = 0 # Process immediately

  # Report individual failures (partial batch response)
  function_response_types = ["ReportBatchItemFailures"]

  scaling_config {
    maximum_concurrency = 100
  }
}

# CloudWatch Log Group

resource "aws_cloudwatch_log_group" "worker_logs" {
  name              = "/aws/lambda/${aws_lambda_function.worker.function_name}"
  retention_in_days = 14
}