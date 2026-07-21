# IAM roles: task execution + app role (Secrets Manager read, S3 evidence, CloudHSM). SCAFFOLDING.
resource "aws_iam_role" "task" {
  name               = "${local.name}-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
  tags = local.tags
}
