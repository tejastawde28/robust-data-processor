# DynamoDB Table with Multi-Tenant Isolation

resource "aws_dynamodb_table" "processed_logs" {
  name         = "${var.project_name}-processed-logs"
  billing_mode = var.dynamodb_billing_mode

  # Multi-Tenant Partition Strategy
  # tenant_id as partition key ensures physical data isolation
  hash_key  = "tenant_id" # Partition Key
  range_key = "log_id"    # Sort Key

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "log_id"
    type = "S"
  }

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name        = "${var.project_name}-processed-logs"
    Description = "Multi-tenant log storage"
  }
}