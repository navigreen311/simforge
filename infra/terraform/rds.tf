# RDS Postgres 15 (Multi-AZ + read replica). Blueprint §J.3. SCAFFOLDING.
resource "aws_db_instance" "primary" {
  identifier            = "${local.name}-pg"
  engine                = "postgres"
  engine_version        = "15"
  instance_class        = "db.r6g.large"
  allocated_storage     = 100
  multi_az              = true
  storage_encrypted     = true
  backup_retention_period = 30
  deletion_protection   = true
  username              = "simforge"
  password              = "REPLACE_VIA_SECRETS_MANAGER" # never commit real secrets
  tags                  = local.tags
}
