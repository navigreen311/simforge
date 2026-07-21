# ECS Fargate services: web, api, workers (multi-AZ, blue/green). Blueprint §J.3. SCAFFOLDING.
resource "aws_ecs_cluster" "main" {
  name = local.name
  tags = local.tags
}
# WEEK 9: task definitions + services for web/api/workers, ALB, target groups,
# blue/green (CodeDeploy), autoscaling. See docs/deploy.md.
