# Install dependencies and package Lambda

resource "null_resource" "api_lambda_dependencies" {
  provisioner "local-exec" {
    command = "cd ${path.module}/../src/api && pip install -r requirements.txt -t . --upgrade --quiet"
  }

  triggers = {
    requirements = filemd5("${path.module}/../src/api/requirements.txt")
  }
}

data "archive_file" "api_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src/api"
  output_path = "${path.module}/../dist/api_lambda.zip"

  depends_on = [null_resource.api_lambda_dependencies]
}

# API Lambda Function

resource "aws_lambda_function" "api" {
  filename         = data.archive_file.api_lambda_zip.output_path
  function_name    = "${var.project_name}-api"
  role             = aws_iam_role.api_lambda_role.arn
  handler          = "lambda_handler.handler"
  runtime          = "python3.11"
  source_code_hash = data.archive_file.api_lambda_zip.output_base64sha256
  timeout          = var.api_lambda_timeout
  memory_size      = var.api_lambda_memory

  environment {
    variables = {
      SQS_QUEUE_URL = aws_sqs_queue.main_queue.url
    }
  }

  tags = {
    Name = "${var.project_name}-api"
  }
}

# Lambda Function URL (Public Access)

resource "aws_lambda_function_url" "api_url" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE" # Public access as per requirements

  cors {
    allow_credentials = false
    allow_headers     = ["*"]
    allow_methods     = ["GET", "POST"]
    allow_origins     = ["*"]
    max_age           = 86400
  }
}


# CloudWatch Log Group

resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/lambda/${aws_lambda_function.api.function_name}"
  retention_in_days = 14
}